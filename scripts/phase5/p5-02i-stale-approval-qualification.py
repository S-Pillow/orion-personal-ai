#!/usr/bin/env python3
"""P5-02I I4 installed-runtime stale-state / approval-consumption probe.

Imports the installed Orion vault plugin and mutates only temporary disposable
roots. Uses the real pinned Hermes CLI approval gate. Every successful approval
in this probe must be human ALLOW ONCE. The public apply tool remains
fail-closed and the private disposable executor remains unregistered.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
import shutil
import socket
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


EXPECTED_TOOLS = {
    "orion_vault_preview_edit",
    "orion_vault_preview_move_draft",
    "orion_vault_recommend_destination",
    "orion_vault_apply_plan",
}
EXPECTED_HOOKS = {"pre_tool_call", "post_approval_response"}


class Context:
    def __init__(self):
        self.tools = {}
        self.hooks = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def call_mcp(self, *_args, **_kwargs):
        raise RuntimeError("MCP calls are forbidden in P5-02I I4")


def gateway_is_listening() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex(("127.0.0.1", 8642)) == 0


@contextmanager
def env_scope(values: dict[str, str | None]):
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def load_installed_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    if not plugin_file.is_file():
        raise RuntimeError(f"installed plugin missing: {plugin_file}")
    spec = importlib.util.spec_from_file_location(
        "orion_p5_02i_installed_i4_probe", plugin_file
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed plugin import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def expect_failure(result: dict, error: str, label: str) -> None:
    if result.get("success") is not False:
        raise RuntimeError(f"{label}: expected success=false: {result}")
    if result.get("error") != error:
        raise RuntimeError(
            f"{label}: expected error={error!r}, got {result.get('error')!r}: {result}"
        )
    if result.get("mutation_performed") is not False:
        raise RuntimeError(f"{label}: unexpected mutation_performed: {result}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument("--fixture-parent", type=Path, required=True)
    args = parser.parse_args()

    if gateway_is_listening():
        raise RuntimeError("Hermes gateway is running; I4 expects manual-off state")

    fixture_parent = args.fixture_parent.resolve()
    if not fixture_parent.is_dir():
        raise RuntimeError(f"fixture parent missing: {fixture_parent}")

    for name in (
        "ORION_P5_MUTATION_MODE",
        "ORION_P5_PRODUCTION_RECOVERY_ROOT",
        "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
        "ORION_P5_RECOVERY_ROOT",
    ):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"unexpected pre-existing process setting: {name}")

    plugin = load_installed_plugin(args.plugin_dir.resolve())
    ctx = Context()
    plugin.register(ctx)

    if set(ctx.tools) != EXPECTED_TOOLS:
        raise RuntimeError("installed tool registration mismatch")
    if set(ctx.hooks) != EXPECTED_HOOKS:
        raise RuntimeError("installed hook registration mismatch")
    if ctx.tools[plugin.APPLY_TOOL]["handler"] is not plugin.apply_plan_placeholder:
        raise RuntimeError("registered apply handler is not fail-closed placeholder")
    if plugin._execute_disposable_plan_candidate in {
        entry["handler"] for entry in ctx.tools.values()
    }:
        raise RuntimeError("private disposable executor unexpectedly registered")

    parameters = inspect.signature(
        plugin._execute_disposable_plan_candidate
    ).parameters
    if "require_fresh_approval" not in parameters:
        raise RuntimeError("installed plugin lacks P5-02I strict approval seam")

    mode = plugin._production_mutation_mode()
    if mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED or mode.get("mutation_allowed"):
        raise RuntimeError("production mutation mode is not disabled")

    fixture = Path(
        tempfile.mkdtemp(prefix="orion-p5-02i-i4-", dir=str(fixture_parent))
    )
    passed = False
    print(f"DISPOSABLE_FIXTURE={fixture}", flush=True)

    try:
        vault = fixture / "vault"
        inbox = fixture / "inbox"
        recovery = fixture / "recovery"
        (vault / "Projects").mkdir(parents=True)
        inbox.mkdir()
        recovery.mkdir()

        roots = {
            "ORION_VAULT_ROOT": str(vault),
            "ORION_INBOX_ROOT": str(inbox),
            plugin.RECOVERY_ROOT_ENV: str(recovery),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
            plugin.PRODUCTION_MUTATION_MODE_ENV: None,
            plugin.PRODUCTION_RECOVERY_ROOT_ENV: None,
            "HERMES_INTERACTIVE": "1",
            "HERMES_GATEWAY_SESSION": None,
            "HERMES_SESSION_PLATFORM": None,
            "HERMES_CRON_SESSION": None,
            "HERMES_SINGLE_QUERY_SESSION": None,
        }

        with env_scope(roots):
            from hermes_cli import lifecycle

            def route_hook(name, **fields):
                callback = ctx.hooks.get(name)
                if callback is None:
                    return []
                result = callback(**fields)
                return [] if result is None else [result]

            def fresh_once(plan_token: str, label: str) -> dict:
                print("", flush=True)
                print(label, flush=True)
                print("Choose ALLOW ONCE at the Hermes approval prompt.", flush=True)
                print("Do NOT choose session/always.", flush=True)
                with patch.object(lifecycle, "invoke_hook", side_effect=route_hook):
                    evidence = plugin._fresh_once_approval_evidence(plan_token)
                if evidence.get("approved") is not True:
                    raise RuntimeError(
                        f"{label}: fresh ALLOW ONCE not obtained: "
                        f"{evidence.get('error')}"
                    )
                if evidence.get("choice") != "once":
                    raise RuntimeError(f"{label}: approval choice is not once")
                if evidence.get("authorization_reusable") is not False:
                    raise RuntimeError(f"{label}: approval incorrectly reusable")
                return evidence

            # ------------------------------------------------------------
            # I4-A: mismatched evidence + stale edit consumption.
            # ------------------------------------------------------------
            note_a = vault / "stale-edit.md"
            note_b = vault / "mismatch-target.md"
            original_a = b"# stale edit\r\nbefore\r\n"
            external_a = b"# stale edit\r\nexternal change after approval\r\n"
            note_a.write_bytes(original_a)
            note_b.write_bytes(b"# mismatch\r\nuntouched\r\n")

            preview_a = json.loads(plugin.preview_edit({
                "target_relative_path": "stale-edit.md",
                "new_content": "# stale edit\r\napproved proposal\r\n",
            }))
            preview_b = json.loads(plugin.preview_edit({
                "target_relative_path": "mismatch-target.md",
                "new_content": "# mismatch\r\nshould never land\r\n",
            }))
            if preview_a.get("success") is not True or preview_b.get("success") is not True:
                raise RuntimeError("I4 edit preview creation failed")

            evidence_a = fresh_once(
                preview_a["plan_token"],
                "P5-02I I4-A EDIT STALE / MISMATCH APPROVAL",
            )

            mismatch = plugin._execute_disposable_plan_candidate(
                preview_b["plan_token"],
                approval_evidence=evidence_a,
                require_fresh_approval=True,
            )
            expect_failure(mismatch, "approval_evidence_invalid", "mismatched evidence")
            if note_b.read_bytes() != b"# mismatch\r\nuntouched\r\n":
                raise RuntimeError("mismatched evidence changed second note")
            if list(recovery.iterdir()):
                raise RuntimeError("mismatched evidence created recovery data")

            # Same evidence is still valid for its own exact plan until it is
            # consumed by an actual execution attempt.
            note_a.write_bytes(external_a)
            stale_edit = plugin._execute_disposable_plan_candidate(
                preview_a["plan_token"],
                approval_evidence=evidence_a,
                require_fresh_approval=True,
            )
            expect_failure(stale_edit, "stale_original_hash", "stale edit")
            if note_a.read_bytes() != external_a:
                raise RuntimeError("stale edit changed externally modified bytes")
            if list(recovery.iterdir()):
                raise RuntimeError("stale edit created recovery data")

            # Restore the pre-preview bytes; the already-used human once must
            # still be dead.
            note_a.write_bytes(original_a)
            stale_edit_replay = plugin._execute_disposable_plan_candidate(
                preview_a["plan_token"],
                approval_evidence=evidence_a,
                require_fresh_approval=True,
            )
            expect_failure(
                stale_edit_replay,
                "approval_evidence_already_consumed",
                "stale edit approval replay",
            )
            if note_a.read_bytes() != original_a:
                raise RuntimeError("stale edit replay mutated restored fixture")
            if list(recovery.iterdir()):
                raise RuntimeError("stale edit replay created recovery data")

            # ------------------------------------------------------------
            # I4-B: move target appears after approval; evidence consumed.
            # ------------------------------------------------------------
            source = inbox / "race-draft.md"
            target = vault / "Projects" / "race-draft.md"
            source_bytes = (
                b"---\r\n"
                b"orion_draft: true\r\n"
                b"status: draft\r\n"
                b"---\r\n"
                b"# race draft\r\n"
            )
            source.write_bytes(source_bytes)

            move_preview = json.loads(plugin.preview_move_draft({
                "source_draft": "race-draft.md",
                "target_relative_path": "Projects/race-draft.md",
            }))
            if move_preview.get("success") is not True:
                raise RuntimeError("I4 move preview creation failed")

            move_evidence = fresh_once(
                move_preview["plan_token"],
                "P5-02I I4-B MOVE TARGET-RACE APPROVAL",
            )

            target.write_bytes(b"concurrent target\r\n")
            move_race = plugin._execute_disposable_plan_candidate(
                move_preview["plan_token"],
                approval_evidence=move_evidence,
                require_fresh_approval=True,
            )
            expect_failure(move_race, "target_already_exists", "move target race")
            if source.read_bytes() != source_bytes:
                raise RuntimeError("move target race changed source")
            if target.read_bytes() != b"concurrent target\r\n":
                raise RuntimeError("move target race changed concurrent target")
            if list(recovery.iterdir()):
                raise RuntimeError("move target race created recovery data")

            target.unlink()
            move_replay = plugin._execute_disposable_plan_candidate(
                move_preview["plan_token"],
                approval_evidence=move_evidence,
                require_fresh_approval=True,
            )
            expect_failure(
                move_replay,
                "approval_evidence_already_consumed",
                "move race approval replay",
            )
            if source.read_bytes() != source_bytes or target.exists():
                raise RuntimeError("move race replay changed fixture state")
            if list(recovery.iterdir()):
                raise RuntimeError("move race replay created recovery data")

            # ------------------------------------------------------------
            # I4-C: a durable receipt is evidence, never authorization.
            # ------------------------------------------------------------
            receipt_note = vault / "receipt-origin.md"
            receipt_note.write_bytes(b"# receipt origin\r\nbefore\r\n")
            receipt_preview = json.loads(plugin.preview_edit({
                "target_relative_path": "receipt-origin.md",
                "new_content": "# receipt origin\r\nafter\r\n",
            }))
            if receipt_preview.get("success") is not True:
                raise RuntimeError("receipt-origin preview failed")

            receipt_evidence = fresh_once(
                receipt_preview["plan_token"],
                "P5-02I I4-C RECEIPT NON-AUTHORIZATION APPROVAL",
            )

            committed = plugin._execute_disposable_plan_candidate(
                receipt_preview["plan_token"],
                approval_evidence=receipt_evidence,
                require_fresh_approval=True,
            )
            if committed.get("success") is not True or committed.get("mutation_performed") is not True:
                raise RuntimeError(f"receipt-origin commit failed: {committed}")

            recovery_dir = Path(committed["recovery_dir"])
            receipt_path = recovery_dir / "receipt.json"
            if not receipt_path.is_file():
                raise RuntimeError("receipt-origin durable receipt missing")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt.get("state") != "committed":
                raise RuntimeError("receipt-origin receipt not committed")
            if receipt.get("approval", {}).get("authorization_reusable") is not False:
                raise RuntimeError("receipt-origin authorization incorrectly reusable")

            later = vault / "receipt-cannot-authorize.md"
            later_before = b"# later\r\nuntouched\r\n"
            later.write_bytes(later_before)
            later_preview = json.loads(plugin.preview_edit({
                "target_relative_path": "receipt-cannot-authorize.md",
                "new_content": "# later\r\nshould never land\r\n",
            }))
            if later_preview.get("success") is not True:
                raise RuntimeError("later preview failed")

            receipt_reuse = plugin._execute_disposable_plan_candidate(
                later_preview["plan_token"],
                approval_evidence=receipt.get("approval"),
                require_fresh_approval=True,
            )
            expect_failure(
                receipt_reuse,
                "approval_evidence_invalid",
                "durable receipt authorization attempt",
            )
            if later.read_bytes() != later_before:
                raise RuntimeError("durable receipt authorized later mutation")
            if (recovery / later_preview["plan_token"]).exists():
                raise RuntimeError("receipt reuse attempt created recovery record")

            # Public apply still cannot mutate the known committed plan.
            public_apply = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"]({
                    "plan_token": receipt_preview["plan_token"]
                })
            )
            if (
                public_apply.get("error") != "p5_01_mutation_not_authorized"
                or public_apply.get("mutation_performed") is not False
            ):
                raise RuntimeError("registered apply no longer fails closed")

            print("", flush=True)
            print("I4_MISMATCHED_EVIDENCE_REFUSED=true", flush=True)
            print("I4_STALE_EDIT_REFUSED=true", flush=True)
            print("I4_STALE_EDIT_APPROVAL_CONSUMED=true", flush=True)
            print("I4_MOVE_TARGET_RACE_REFUSED=true", flush=True)
            print("I4_MOVE_APPROVAL_CONSUMED=true", flush=True)
            print("I4_DURABLE_RECEIPT_NON_AUTHORIZING=true", flush=True)
            print("I4_REGISTERED_APPLY_FAIL_CLOSED=true", flush=True)
            print("I4_REAL_VAULT_INBOX_TOUCHED=false", flush=True)

        passed = True
        return 0
    finally:
        if passed:
            shutil.rmtree(fixture)
            print("DISPOSABLE_FIXTURE_CLEANED=true", flush=True)
            print("P5_02I_I4_QUALIFICATION=PASS", flush=True)
        else:
            print(
                f"P5_02I_I4_QUALIFICATION=FAIL; FIXTURE_PRESERVED={fixture}",
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("P5_02I_I4_QUALIFICATION=ABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(
            f"P5_02I_I4_QUALIFICATION=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
