#!/usr/bin/env python3
"""P5-02I I5 restart-safe recovery/receipt classification probe.

Imports the installed Orion vault plugin, commits one disposable edit and one
disposable move using real fresh Hermes ALLOW ONCE decisions, then clears all
relevant in-memory plan/approval/consumption caches to simulate a process
restart. Recovery and receipt state must still classify correctly from disk.

No restore/repair action is executed in I5.
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
        raise RuntimeError("MCP calls are forbidden in P5-02I I5")


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
        "orion_p5_02i_installed_i5_probe", plugin_file
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed plugin import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def assert_committed_recovery(result: dict, label: str) -> None:
    if result.get("success") is not True:
        raise RuntimeError(f"{label}: recovery inspection failed: {result}")
    if result.get("classification") != "committed":
        raise RuntimeError(
            f"{label}: expected recovery classification committed: {result}"
        )
    if result.get("recovery_required") is not False:
        raise RuntimeError(f"{label}: unexpected recovery_required: {result}")
    if result.get("mutation_performed") is not False:
        raise RuntimeError(f"{label}: inspector reported mutation: {result}")


def assert_committed_receipt(result: dict, label: str, attempt_id: str) -> None:
    if result.get("success") is not True:
        raise RuntimeError(f"{label}: receipt inspection failed: {result}")
    expected = {
        "correlation_valid": True,
        "authorization_reusable": False,
        "receipt_state": "committed",
        "receipt_finalized": True,
        "receipt_reconciliation_required": False,
        "final_classification": "committed",
        "current_classification": "committed",
        "approval_choice": "once",
    }
    for key, value in expected.items():
        if result.get(key) != value:
            raise RuntimeError(
                f"{label}: expected {key}={value!r}, got "
                f"{result.get(key)!r}: {result}"
            )
    if result.get("approval_attempt_id") != attempt_id:
        raise RuntimeError(f"{label}: approval attempt correlation mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument("--fixture-parent", type=Path, required=True)
    args = parser.parse_args()

    if gateway_is_listening():
        raise RuntimeError("Hermes gateway is running; I5 expects manual-off state")

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

    if "require_fresh_approval" not in inspect.signature(
        plugin._execute_disposable_plan_candidate
    ).parameters:
        raise RuntimeError("installed plugin lacks P5-02I strict approval seam")

    mode = plugin._production_mutation_mode()
    if mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED or mode.get("mutation_allowed"):
        raise RuntimeError("production mutation mode is not disabled")

    fixture = Path(
        tempfile.mkdtemp(prefix="orion-p5-02i-i5-", dir=str(fixture_parent))
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
            # Committed edit transaction.
            # ------------------------------------------------------------
            edit_note = vault / "restart-edit.md"
            edit_before = b"# restart edit\r\nbefore\r\n"
            edit_after_text = "# restart edit\r\nafter\r\n"
            edit_note.write_bytes(edit_before)

            edit_preview = json.loads(plugin.preview_edit({
                "target_relative_path": "restart-edit.md",
                "new_content": edit_after_text,
            }))
            if edit_preview.get("success") is not True:
                raise RuntimeError("I5 edit preview failed")

            edit_evidence = fresh_once(
                edit_preview["plan_token"],
                "P5-02I I5-A COMMITTED EDIT",
            )

            edit_result = plugin._execute_disposable_plan_candidate(
                edit_preview["plan_token"],
                approval_evidence=edit_evidence,
                require_fresh_approval=True,
            )
            if (
                edit_result.get("success") is not True
                or edit_result.get("mutation_performed") is not True
            ):
                raise RuntimeError(f"I5 edit commit failed: {edit_result}")
            if edit_note.read_bytes() != edit_after_text.encode("utf-8"):
                raise RuntimeError("I5 edit committed bytes mismatch")

            # ------------------------------------------------------------
            # Committed move transaction.
            # ------------------------------------------------------------
            move_source = inbox / "restart-move.md"
            move_target = vault / "Projects" / "restart-move.md"
            move_bytes = (
                b"---\r\n"
                b"orion_draft: true\r\n"
                b"status: draft\r\n"
                b"---\r\n"
                b"# restart move\r\n"
            )
            move_source.write_bytes(move_bytes)

            move_preview = json.loads(plugin.preview_move_draft({
                "source_draft": "restart-move.md",
                "target_relative_path": "Projects/restart-move.md",
            }))
            if move_preview.get("success") is not True:
                raise RuntimeError("I5 move preview failed")

            move_evidence = fresh_once(
                move_preview["plan_token"],
                "P5-02I I5-B COMMITTED MOVE",
            )

            move_result = plugin._execute_disposable_plan_candidate(
                move_preview["plan_token"],
                approval_evidence=move_evidence,
                require_fresh_approval=True,
            )
            if (
                move_result.get("success") is not True
                or move_result.get("mutation_performed") is not True
            ):
                raise RuntimeError(f"I5 move commit failed: {move_result}")
            if move_source.exists():
                raise RuntimeError("I5 move source still present")
            if move_target.read_bytes() != move_bytes:
                raise RuntimeError("I5 move target bytes mismatch")

            # Both durable records must exist before restart simulation.
            edit_recovery_dir = recovery / edit_preview["plan_token"]
            move_recovery_dir = recovery / move_preview["plan_token"]
            for label, directory in (
                ("edit", edit_recovery_dir),
                ("move", move_recovery_dir),
            ):
                if not directory.is_dir():
                    raise RuntimeError(f"I5 {label} recovery directory missing")
                if not (directory / "manifest.json").is_file():
                    raise RuntimeError(f"I5 {label} manifest missing")
                if not (directory / "receipt.json").is_file():
                    raise RuntimeError(f"I5 {label} receipt missing")

            # ------------------------------------------------------------
            # Simulate a full process restart by dropping all ephemeral
            # preview/approval/consumption state. Disk records must stand alone.
            # ------------------------------------------------------------
            plugin._PREVIEWS.clear()
            plugin._PREVIEW_TIMES.clear()
            plugin._APPROVAL_ATTEMPTS.clear()
            plugin._CANDIDATE_CONSUMED_PLANS.clear()
            plugin._CANDIDATE_CONSUMED_APPROVAL_ATTEMPTS.clear()

            if plugin._PREVIEWS or plugin._PREVIEW_TIMES or plugin._APPROVAL_ATTEMPTS:
                raise RuntimeError("I5 restart simulation did not clear plan caches")
            if (
                plugin._CANDIDATE_CONSUMED_PLANS
                or plugin._CANDIDATE_CONSUMED_APPROVAL_ATTEMPTS
            ):
                raise RuntimeError("I5 restart simulation did not clear consumption caches")

            edit_recovery = plugin._inspect_disposable_recovery_candidate(
                edit_preview["plan_token"]
            )
            edit_receipt = plugin._inspect_disposable_receipt_candidate(
                edit_preview["plan_token"]
            )
            move_recovery = plugin._inspect_disposable_recovery_candidate(
                move_preview["plan_token"]
            )
            move_receipt = plugin._inspect_disposable_receipt_candidate(
                move_preview["plan_token"]
            )

            assert_committed_recovery(edit_recovery, "edit")
            assert_committed_receipt(
                edit_receipt, "edit", edit_evidence["attempt_id"]
            )
            assert_committed_recovery(move_recovery, "move")
            assert_committed_receipt(
                move_receipt, "move", move_evidence["attempt_id"]
            )

            if edit_receipt.get("action") != "edit_note":
                raise RuntimeError("I5 edit receipt action mismatch")
            if move_receipt.get("action") != "move_draft":
                raise RuntimeError("I5 move receipt action mismatch")

            # No preview plan survives the restart simulation, so public apply
            # still refuses and cannot infer authority from disk receipts.
            public_edit = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"]({
                    "plan_token": edit_preview["plan_token"]
                })
            )
            public_move = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"]({
                    "plan_token": move_preview["plan_token"]
                })
            )
            for label, result in (("edit", public_edit), ("move", public_move)):
                if result != {
                    "success": False,
                    "error": "p5_01_mutation_not_authorized",
                    "plan_known": False,
                    "mutation_performed": False,
                }:
                    raise RuntimeError(
                        f"I5 {label} public apply after restart mismatch: {result}"
                    )

            print("", flush=True)
            print("I5_EDIT_COMMITTED_BEFORE_RESTART=true", flush=True)
            print("I5_MOVE_COMMITTED_BEFORE_RESTART=true", flush=True)
            print("I5_EPHEMERAL_STATE_CLEARED=true", flush=True)
            print("I5_EDIT_RECOVERY_CLASSIFICATION=committed", flush=True)
            print("I5_EDIT_RECEIPT_STATE=committed", flush=True)
            print("I5_EDIT_RECEIPT_CORRELATION_VALID=true", flush=True)
            print("I5_MOVE_RECOVERY_CLASSIFICATION=committed", flush=True)
            print("I5_MOVE_RECEIPT_STATE=committed", flush=True)
            print("I5_MOVE_RECEIPT_CORRELATION_VALID=true", flush=True)
            print("I5_AUTHORIZATION_REUSABLE=false", flush=True)
            print("I5_RESTART_RECEIPTS_NON_AUTHORIZING=true", flush=True)
            print("I5_REGISTERED_APPLY_FAIL_CLOSED_AFTER_RESTART=true", flush=True)
            print("I5_REAL_VAULT_INBOX_TOUCHED=false", flush=True)

        passed = True
        return 0
    finally:
        if passed:
            shutil.rmtree(fixture)
            print("DISPOSABLE_FIXTURE_CLEANED=true", flush=True)
            print("P5_02I_I5_QUALIFICATION=PASS", flush=True)
        else:
            print(
                f"P5_02I_I5_QUALIFICATION=FAIL; FIXTURE_PRESERVED={fixture}",
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("P5_02I_I5_QUALIFICATION=ABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(
            f"P5_02I_I5_QUALIFICATION=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
