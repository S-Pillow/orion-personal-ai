#!/usr/bin/env python3
"""P5-02I installed-runtime disposable move qualification."""
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
        raise RuntimeError("MCP calls are forbidden in P5-02I move qualification")


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
        "orion_p5_02i_installed_move_probe", plugin_file
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed plugin import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument("--fixture-parent", type=Path, required=True)
    args = parser.parse_args()

    if gateway_is_listening():
        raise RuntimeError("Hermes gateway is running; expected manual-off state")

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

    mode = plugin._production_mutation_mode()
    if mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED or mode.get("mutation_allowed"):
        raise RuntimeError("production mutation mode is not disabled")

    fixture = Path(tempfile.mkdtemp(prefix="orion-p5-02i-move-", dir=str(fixture_parent)))
    passed = False
    print(f"DISPOSABLE_FIXTURE={fixture}", flush=True)

    try:
        vault = fixture / "vault"
        inbox = fixture / "inbox"
        recovery = fixture / "recovery"
        folder = vault / "Projects"
        folder.mkdir(parents=True)
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

        source_bytes = (
            b"---\r\n"
            b"orion_draft: true\r\n"
            b"status: draft\r\n"
            b"---\r\n"
            b"# Disposable draft\r\n"
            b"move qualification\r\n"
        )

        with env_scope(roots):
            from hermes_cli import lifecycle

            def route_hook(name, **fields):
                callback = ctx.hooks.get(name)
                if callback is None:
                    return []
                result = callback(**fields)
                return [] if result is None else [result]

            # DENY control.
            deny_source = inbox / "deny-draft.md"
            deny_target = vault / "Projects" / "deny-draft.md"
            deny_source.write_bytes(source_bytes)

            deny_preview = json.loads(plugin.preview_move_draft({
                "source_draft": "deny-draft.md",
                "target_relative_path": "Projects/deny-draft.md",
            }))
            if deny_preview.get("success") is not True:
                raise RuntimeError("DENY move preview creation failed")
            if deny_preview.get("mutation_performed") is not False:
                raise RuntimeError("DENY move preview unexpectedly mutated")

            print("", flush=True)
            print("P5-02I MOVE DENY CONTROL", flush=True)
            print("At the Hermes approval prompt choose DENY.", flush=True)
            print("Source must remain present; target/recovery must remain absent.", flush=True)

            with patch.object(lifecycle, "invoke_hook", side_effect=route_hook):
                denied = plugin._fresh_once_approval_evidence(
                    deny_preview["plan_token"]
                )

            if denied.get("approved") is True:
                raise RuntimeError("DENY unexpectedly produced approval evidence")
            if deny_source.read_bytes() != source_bytes:
                raise RuntimeError("DENY changed disposable source")
            if deny_target.exists():
                raise RuntimeError("DENY created disposable target")
            if list(recovery.iterdir()):
                raise RuntimeError("DENY created recovery data")

            # ALLOW ONCE uses distinct source/path and fresh plan.
            source = inbox / "draft.md"
            target = vault / "Projects" / "draft.md"
            source.write_bytes(source_bytes)

            allow_preview = json.loads(plugin.preview_move_draft({
                "source_draft": "draft.md",
                "target_relative_path": "Projects/draft.md",
            }))
            if allow_preview.get("success") is not True:
                raise RuntimeError("ALLOW move preview creation failed")
            if allow_preview.get("mutation_performed") is not False:
                raise RuntimeError("ALLOW move preview unexpectedly mutated")
            if os.name == "nt" and not allow_preview.get("plan", {}).get("source_file_id"):
                raise RuntimeError("Windows move preview missing source_file_id")

            print("", flush=True)
            print("P5-02I DISPOSABLE MOVE", flush=True)
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
            if evidence.get("choice") != "once":
                raise RuntimeError("approval choice is not once")
            if evidence.get("authorization_reusable") is not False:
                raise RuntimeError("approval evidence marked reusable")

            result = plugin._execute_disposable_plan_candidate(
                allow_preview["plan_token"],
                approval_evidence=evidence,
            )
            if result.get("success") is not True:
                raise RuntimeError("disposable move failed: " + str(result.get("error")))
            if result.get("mutation_performed") is not True:
                raise RuntimeError("disposable move did not report mutation")

            if source.exists():
                raise RuntimeError("source still exists after committed move")
            if target.read_bytes() != source_bytes:
                raise RuntimeError("target bytes do not match approved source")

            recovery_dir = Path(result["recovery_dir"]).resolve()
            try:
                recovery_dir.relative_to(recovery.resolve())
            except ValueError as exc:
                raise RuntimeError("recovery record escaped disposable root") from exc

            backup = recovery_dir / "source.bin"
            manifest_path = recovery_dir / "manifest.json"
            receipt_path = recovery_dir / "receipt.json"
            if not all(p.is_file() for p in (backup, manifest_path, receipt_path)):
                raise RuntimeError("move recovery artifacts missing")
            if backup.read_bytes() != source_bytes:
                raise RuntimeError("move recovery backup mismatch")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if manifest.get("state") != "committed":
                raise RuntimeError("move manifest not committed")
            if manifest.get("action") != "move_draft":
                raise RuntimeError("move manifest action mismatch")
            if receipt.get("state") != "committed":
                raise RuntimeError("move receipt not committed")
            if receipt.get("approval", {}).get("choice") != "once":
                raise RuntimeError("move receipt approval choice mismatch")
            if receipt.get("approval", {}).get("authorization_reusable") is not False:
                raise RuntimeError("move receipt authorization reusable")
            if receipt.get("approval", {}).get("attempt_id") != evidence.get("attempt_id"):
                raise RuntimeError("move receipt approval correlation mismatch")

            inspected = plugin._inspect_disposable_recovery_candidate(
                allow_preview["plan_token"]
            )
            if (
                inspected.get("success") is not True
                or inspected.get("classification") != "committed"
            ):
                raise RuntimeError(
                    "move recovery inspection failed: "
                    + json.dumps(inspected, sort_keys=True)
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
                    "move receipt inspection failed: "
                    + json.dumps(receipt_inspected, sort_keys=True)
                )

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
                    "move replay did not fail closed: "
                    + json.dumps(replay, sort_keys=True)
                )
            if source.exists() or target.read_bytes() != source_bytes:
                raise RuntimeError("move replay altered committed state")

            public_apply = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"]({
                    "plan_token": allow_preview["plan_token"]
                })
            )
            if (
                public_apply.get("error") != "p5_01_mutation_not_authorized"
                or public_apply.get("mutation_performed") is not False
            ):
                raise RuntimeError("registered apply no longer fails closed")

            print("", flush=True)
            print("P5_02I_MOVE_DENY_CONTROL=PASS", flush=True)
            print("P5_02I_MOVE_FRESH_ONCE=PASS", flush=True)
            print("DISPOSABLE_MOVE_MUTATION_PERFORMED=true", flush=True)
            print(f"MOVE_SOURCE_SHA256={sha256(source_bytes)}", flush=True)
            print("MOVE_SOURCE_ABSENT=true", flush=True)
            print("MOVE_TARGET_BYTES_MATCH=true", flush=True)
            print("WINDOWS_SOURCE_FILE_ID_BOUND=true" if os.name == "nt" else "WINDOWS_SOURCE_FILE_ID_BOUND=not_applicable", flush=True)
            print("MOVE_RECOVERY_CLASSIFICATION=committed", flush=True)
            print("MOVE_RECEIPT_STATE=committed", flush=True)
            print("MOVE_AUTHORIZATION_REUSABLE=false", flush=True)
            print("MOVE_PLAN_REPLAY_REFUSED=true", flush=True)
            print("REGISTERED_APPLY_FAIL_CLOSED=true", flush=True)
            print("REAL_VAULT_INBOX_TOUCHED=false", flush=True)

        passed = True
        return 0
    finally:
        if passed:
            shutil.rmtree(fixture)
            print("DISPOSABLE_FIXTURE_CLEANED=true", flush=True)
            print("P5_02I_MOVE_QUALIFICATION=PASS", flush=True)
        else:
            print(
                f"P5_02I_MOVE_QUALIFICATION=FAIL; FIXTURE_PRESERVED={fixture}",
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("P5_02I_MOVE_QUALIFICATION=ABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(
            f"P5_02I_MOVE_QUALIFICATION=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
