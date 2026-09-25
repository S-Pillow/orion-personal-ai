#!/usr/bin/env python3
"""P5-02I installed-runtime disposable edit qualification.

This operator probe imports the *installed* Orion vault plugin supplied on the
command line, creates temporary disposable vault/inbox/recovery roots, and uses
the installed Hermes approval engine for real human DENY / ALLOW ONCE choices.

The private disposable executor remains unregistered. The public apply handler
must remain the fail-closed placeholder. No real Orion vault/inbox path is used.

On PASS the disposable fixture is deleted. On failure it is preserved and its
path is printed for investigation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
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
        raise RuntimeError("MCP calls are forbidden in P5-02I edit qualification")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
        "orion_p5_02i_installed_edit_probe", plugin_file
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed plugin import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def expect_error(fn, expected: str) -> None:
    try:
        fn()
    except Exception as exc:
        if str(exc) != expected:
            raise AssertionError(
                f"expected {expected!r}, got {str(exc)!r}"
            ) from exc
    else:
        raise AssertionError(f"expected refusal {expected!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument(
        "--fixture-parent",
        type=Path,
        required=True,
        help="Existing neutral parent for disposable roots (for example D:\\Orion)",
    )
    args = parser.parse_args()

    fixture_parent = args.fixture_parent.resolve()
    if not fixture_parent.is_dir():
        raise RuntimeError(f"fixture parent missing: {fixture_parent}")

    if gateway_is_listening():
        raise RuntimeError(
            "Hermes gateway is listening on 127.0.0.1:8642; "
            "P5-02I edit probe expects accepted manual-off state"
        )

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
        raise RuntimeError(
            "installed tool registration mismatch: " + repr(sorted(ctx.tools))
        )
    if set(ctx.hooks) != EXPECTED_HOOKS:
        raise RuntimeError(
            "installed hook registration mismatch: " + repr(sorted(ctx.hooks))
        )
    if ctx.tools[plugin.APPLY_TOOL]["handler"] is not plugin.apply_plan_placeholder:
        raise RuntimeError("registered apply handler is not fail-closed placeholder")
    registered_handlers = {entry["handler"] for entry in ctx.tools.values()}
    if plugin._execute_disposable_plan_candidate in registered_handlers:
        raise RuntimeError("private disposable executor is unexpectedly registered")

    mode = plugin._production_mutation_mode()
    if (
        not mode.get("valid")
        or mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED
        or mode.get("mutation_allowed")
    ):
        raise RuntimeError("production mutation mode is not disabled")

    fixture = Path(
        tempfile.mkdtemp(
            prefix="orion-p5-02i-edit-",
            dir=str(fixture_parent),
        )
    )
    passed = False
    print(f"DISPOSABLE_FIXTURE={fixture}", flush=True)

    try:
        vault = fixture / "vault"
        inbox = fixture / "inbox"
        recovery = fixture / "recovery"
        vault.mkdir()
        inbox.mkdir()
        recovery.mkdir()

        roots = {
            "ORION_VAULT_ROOT": str(vault),
            "ORION_INBOX_ROOT": str(inbox),
            plugin.RECOVERY_ROOT_ENV: str(recovery),
        }

        # I1: opt-in is mandatory.
        with env_scope({
            **roots,
            plugin.DISPOSABLE_MUTATION_FLAG: None,
            plugin.PRODUCTION_MUTATION_MODE_ENV: None,
            plugin.PRODUCTION_RECOVERY_ROOT_ENV: None,
        }):
            expect_error(
                plugin._candidate_disposable_roots,
                "disposable_mutation_not_enabled",
            )

        # I1: even with disposable opt-in, a live default-root overlap is refused
        # before any mutation/recovery action.
        with env_scope({
            **roots,
            "ORION_VAULT_ROOT": plugin.DEFAULT_VAULT_ROOT,
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
            plugin.PRODUCTION_MUTATION_MODE_ENV: None,
            plugin.PRODUCTION_RECOVERY_ROOT_ENV: None,
        }):
            expect_error(
                plugin._candidate_disposable_roots,
                "live_vault_root_overlap_rejected",
            )

        note = vault / "note.md"
        before_bytes = b"# Disposable\r\nbefore\r\n"
        after_text = "# Disposable\r\nafter approved edit\r\n"
        after_bytes = after_text.encode("utf-8")
        note.write_bytes(before_bytes)

        with env_scope({
            **roots,
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
            plugin.PRODUCTION_MUTATION_MODE_ENV: None,
            plugin.PRODUCTION_RECOVERY_ROOT_ENV: None,
            # Bare scripts are fail-closed by Hermes unless they explicitly
            # declare an interactive human CLI. Keep this process-scoped and
            # clear gateway/cron/single-query routing markers so the real
            # approval engine uses its bounded stdin prompt.
            "HERMES_INTERACTIVE": "1",
            "HERMES_GATEWAY_SESSION": None,
            "HERMES_SESSION_PLATFORM": None,
            "HERMES_CRON_SESSION": None,
            "HERMES_SINGLE_QUERY_SESSION": None,
        }):
            resolved = plugin._candidate_disposable_roots()
            if tuple(path.resolve() for path in resolved) != (
                vault.resolve(), inbox.resolve(), recovery.resolve()
            ):
                raise RuntimeError("disposable root resolution mismatch")

            from hermes_cli import lifecycle

            def route_hook(name, **fields):
                callback = ctx.hooks.get(name)
                if callback is None:
                    return []
                result = callback(**fields)
                return [] if result is None else [result]

            # DENY control gets its own fresh preview nonce/plan.
            deny_preview = json.loads(plugin.preview_edit({
                "target_relative_path": "note.md",
                "new_content": after_text,
            }))
            if (
                deny_preview.get("success") is not True
                or deny_preview.get("mutation_performed") is not False
            ):
                raise RuntimeError("deny preview creation failed")

            print("", flush=True)
            print("P5-02I DENY CONTROL", flush=True)
            print("At the Hermes approval prompt choose DENY.", flush=True)
            print("The disposable note must remain unchanged.", flush=True)

            with patch.object(lifecycle, "invoke_hook", side_effect=route_hook):
                denied = plugin._fresh_once_approval_evidence(
                    deny_preview["plan_token"]
                )

            if denied.get("approved") is True:
                raise RuntimeError("DENY control unexpectedly produced approval evidence")
            if note.read_bytes() != before_bytes:
                raise RuntimeError("DENY control changed disposable note")
            if list(recovery.iterdir()):
                raise RuntimeError("DENY control created recovery data")

            # ALLOW ONCE uses a new plan so no decision can be carried forward.
            allow_preview = json.loads(plugin.preview_edit({
                "target_relative_path": "note.md",
                "new_content": after_text,
            }))
            if (
                allow_preview.get("success") is not True
                or allow_preview.get("mutation_performed") is not False
            ):
                raise RuntimeError("ALLOW ONCE preview creation failed")
            if allow_preview["plan_token"] == deny_preview["plan_token"]:
                raise RuntimeError("fresh preview nonce did not produce a new plan token")

            print("", flush=True)
            print("P5-02I DISPOSABLE EDIT", flush=True)
            print("At the Hermes approval prompt choose ALLOW ONCE.", flush=True)
            print("Do NOT choose session/always.", flush=True)

            with patch.object(lifecycle, "invoke_hook", side_effect=route_hook):
                evidence = plugin._fresh_once_approval_evidence(
                    allow_preview["plan_token"]
                )

            if evidence.get("approved") is not True:
                raise RuntimeError(
                    "fresh ALLOW ONCE evidence not obtained: "
                    + str(evidence.get("error"))
                )
            if (
                evidence.get("choice") != "once"
                or evidence.get("authorization_reusable") is not False
                or evidence.get("plan_token") != allow_preview["plan_token"]
            ):
                raise RuntimeError("fresh approval evidence contract mismatch")

            result = plugin._execute_disposable_plan_candidate(
                allow_preview["plan_token"],
                approval_evidence=evidence,
            )
            if result.get("success") is not True:
                raise RuntimeError(
                    "disposable edit failed: " + str(result.get("error"))
                )
            if result.get("mutation_performed") is not True:
                raise RuntimeError("disposable edit did not report mutation")
            if note.read_bytes() != after_bytes:
                raise RuntimeError("disposable edit bytes do not match approved proposal")

            recovery_dir = Path(result["recovery_dir"]).resolve()
            recovery_real = recovery.resolve()
            try:
                recovery_dir.relative_to(recovery_real)
            except ValueError as exc:
                raise RuntimeError("recovery record escaped disposable root") from exc

            manifest_path = recovery_dir / "manifest.json"
            receipt_path = recovery_dir / "receipt.json"
            backup_path = recovery_dir / "original.bin"
            if not all(path.is_file() for path in (
                manifest_path, receipt_path, backup_path
            )):
                raise RuntimeError("committed edit recovery artifacts missing")
            if backup_path.read_bytes() != before_bytes:
                raise RuntimeError("edit recovery backup mismatch")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if manifest.get("state") != "committed":
                raise RuntimeError("edit recovery manifest not committed")
            if receipt.get("state") != "committed":
                raise RuntimeError("edit receipt not committed")
            if receipt.get("approval", {}).get("choice") != "once":
                raise RuntimeError("receipt approval choice is not once")
            if receipt.get("approval", {}).get("authorization_reusable") is not False:
                raise RuntimeError("receipt incorrectly marks authorization reusable")
            if receipt.get("approval", {}).get("attempt_id") != evidence.get("attempt_id"):
                raise RuntimeError("receipt approval attempt correlation mismatch")

            inspected = plugin._inspect_disposable_recovery_candidate(
                allow_preview["plan_token"]
            )
            if (
                inspected.get("success") is not True
                or inspected.get("classification") != "committed"
            ):
                raise RuntimeError(
                    "recovery inspection failed: " + json.dumps(inspected, sort_keys=True)
                )

            receipt_inspected = plugin._inspect_disposable_receipt_candidate(
                allow_preview["plan_token"]
            )
            if (
                receipt_inspected.get("success") is not True
                or receipt_inspected.get("correlation_valid") is not True
                or receipt_inspected.get("receipt_state") != "committed"
                or receipt_inspected.get("authorization_reusable") is not False
            ):
                raise RuntimeError(
                    "receipt inspection failed: "
                    + json.dumps(receipt_inspected, sort_keys=True)
                )

            # A consumed plan cannot mutate a second time.
            replay = plugin._execute_disposable_plan_candidate(
                allow_preview["plan_token"],
                approval_evidence=evidence,
            )
            if (
                replay.get("success") is not False
                or replay.get("error") != "plan_already_consumed"
                or replay.get("mutation_performed") is not False
            ):
                raise RuntimeError(
                    "plan replay did not fail closed: "
                    + json.dumps(replay, sort_keys=True)
                )
            if note.read_bytes() != after_bytes:
                raise RuntimeError("replay altered committed disposable bytes")

            # Public apply remains fail-closed even for the known committed plan.
            public_apply = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"]({
                    "plan_token": allow_preview["plan_token"]
                })
            )
            if (
                public_apply.get("error") != "p5_01_mutation_not_authorized"
                or public_apply.get("mutation_performed") is not False
            ):
                raise RuntimeError(
                    "registered apply no longer fails closed: "
                    + json.dumps(public_apply, sort_keys=True)
                )

            print("", flush=True)
            print("P5_02I_I1_GUARDS=PASS", flush=True)
            print("P5_02I_DENY_CONTROL=PASS", flush=True)
            print("P5_02I_FRESH_ONCE=PASS", flush=True)
            print("DISPOSABLE_EDIT_MUTATION_PERFORMED=true", flush=True)
            print(f"EDIT_BEFORE_SHA256={sha256(before_bytes)}", flush=True)
            print(f"EDIT_AFTER_SHA256={sha256(after_bytes)}", flush=True)
            print("RECOVERY_CLASSIFICATION=committed", flush=True)
            print("RECEIPT_STATE=committed", flush=True)
            print("AUTHORIZATION_REUSABLE=false", flush=True)
            print("PLAN_REPLAY_REFUSED=true", flush=True)
            print("REGISTERED_APPLY_FAIL_CLOSED=true", flush=True)
            print("REAL_VAULT_INBOX_TOUCHED=false", flush=True)

        passed = True
        return 0
    finally:
        if passed:
            shutil.rmtree(fixture)
            print("DISPOSABLE_FIXTURE_CLEANED=true", flush=True)
            print("P5_02I_EDIT_QUALIFICATION=PASS", flush=True)
        else:
            print(
                f"P5_02I_EDIT_QUALIFICATION=FAIL; FIXTURE_PRESERVED={fixture}",
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("P5_02I_EDIT_QUALIFICATION=ABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(
            f"P5_02I_EDIT_QUALIFICATION=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
