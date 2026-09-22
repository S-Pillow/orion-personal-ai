#!/usr/bin/env python3
"""P5-02I I7 controlled failure classification qualification.

Disposable roots only. Uses two real human ALLOW ONCE decisions:
- pre-mutation interruption after durable recovery/receipt preparation;
- post-mutation interruption after protected edit replacement but before
  transaction finalization.

The probe clears in-memory state before inspection so classification must be
restart-safe and disk-derived. It never auto-retries or auto-recovers.
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
        raise RuntimeError("MCP calls are forbidden in P5-02I I7")


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


def clear_ephemeral(plugin) -> None:
    plugin._PREVIEWS.clear()
    plugin._PREVIEW_TIMES.clear()
    plugin._APPROVAL_ATTEMPTS.clear()
    plugin._CANDIDATE_CONSUMED_PLANS.clear()
    plugin._CANDIDATE_CONSUMED_APPROVAL_ATTEMPTS.clear()


def load_installed_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    if not plugin_file.is_file():
        raise RuntimeError(f"installed plugin missing: {plugin_file}")
    spec = importlib.util.spec_from_file_location(
        "orion_p5_02i_installed_i7_probe", plugin_file
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
        raise RuntimeError("Hermes gateway is running; I7 expects manual-off state")

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

    handlers = {entry["handler"] for entry in ctx.tools.values()}
    if plugin._execute_disposable_plan_candidate in handlers:
        raise RuntimeError("private disposable executor unexpectedly registered")
    if plugin._execute_disposable_restore_candidate in handlers:
        raise RuntimeError("private restore executor unexpectedly registered")

    if "require_fresh_approval" not in inspect.signature(
        plugin._execute_disposable_plan_candidate
    ).parameters:
        raise RuntimeError("installed plugin lacks P5-02I strict approval seam")

    mode = plugin._production_mutation_mode()
    if mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED or mode.get("mutation_allowed"):
        raise RuntimeError("production mutation mode is not disabled")

    fixture = Path(
        tempfile.mkdtemp(prefix="orion-p5-02i-i7-", dir=str(fixture_parent))
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

            # ============================================================
            # I7-A: pre-mutation failure after durable recovery + receipt
            # preparation but before protected replace.
            # ============================================================
            pre_note = vault / "pre-failure.md"
            pre_before = b"# pre failure\r\nbefore\r\n"
            pre_after_text = "# pre failure\r\nafter proposal\r\n"
            pre_note.write_bytes(pre_before)

            pre_preview = json.loads(plugin.preview_edit({
                "target_relative_path": "pre-failure.md",
                "new_content": pre_after_text,
            }))
            if pre_preview.get("success") is not True:
                raise RuntimeError("I7 pre-failure preview failed")

            pre_evidence = fresh_once(
                pre_preview["plan_token"],
                "P5-02I I7-A PRE-MUTATION FAILURE",
            )

            def fail_before_replace(name: str) -> None:
                if name == "edit_after_recovery":
                    raise RuntimeError("p5_02i_i7_pre_mutation_interrupt")

            pre_result = plugin._execute_disposable_plan_candidate(
                pre_preview["plan_token"],
                approval_evidence=pre_evidence,
                require_fresh_approval=True,
                failure_hook=fail_before_replace,
            )

            if pre_result.get("success") is not False:
                raise RuntimeError(f"I7 pre-failure unexpectedly succeeded: {pre_result}")
            if pre_result.get("mutation_performed") is not False:
                raise RuntimeError(f"I7 pre-failure reported mutation: {pre_result}")
            if pre_note.read_bytes() != pre_before:
                raise RuntimeError("I7 pre-failure changed protected bytes")

            pre_dir = recovery / pre_preview["plan_token"]
            if not pre_dir.is_dir():
                raise RuntimeError("I7 pre-failure recovery directory missing")
            if not (pre_dir / "original.bin").is_file():
                raise RuntimeError("I7 pre-failure backup missing")
            if not (pre_dir / "manifest.json").is_file():
                raise RuntimeError("I7 pre-failure manifest missing")
            if not (pre_dir / "receipt.json").is_file():
                raise RuntimeError("I7 pre-failure receipt missing")

            pre_manifest = json.loads(
                (pre_dir / "manifest.json").read_text(encoding="utf-8")
            )
            pre_receipt_raw = json.loads(
                (pre_dir / "receipt.json").read_text(encoding="utf-8")
            )
            if pre_manifest.get("state") != "prepared":
                raise RuntimeError("I7 pre-failure manifest not prepared")
            if pre_receipt_raw.get("state") != "prepared":
                raise RuntimeError("I7 pre-failure receipt not prepared")

            # Simulated restart: disk state must classify without any plan or
            # approval memory.
            clear_ephemeral(plugin)

            pre_recovery = plugin._inspect_disposable_recovery_candidate(
                pre_preview["plan_token"]
            )
            pre_receipt = plugin._inspect_disposable_receipt_candidate(
                pre_preview["plan_token"]
            )

            if (
                pre_recovery.get("success") is not True
                or pre_recovery.get("classification") != "prepared_no_effect"
                or pre_recovery.get("recovery_required") is not False
            ):
                raise RuntimeError(
                    "I7 pre-failure recovery classification mismatch: "
                    + json.dumps(pre_recovery, sort_keys=True)
                )

            if (
                pre_receipt.get("success") is not True
                or pre_receipt.get("correlation_valid") is not True
                or pre_receipt.get("receipt_state") != "prepared"
                or pre_receipt.get("receipt_finalized") is not False
                or pre_receipt.get("receipt_reconciliation_required") is not True
                or pre_receipt.get("current_classification") != "prepared_no_effect"
                or pre_receipt.get("authorization_reusable") is not False
            ):
                raise RuntimeError(
                    "I7 pre-failure receipt classification mismatch: "
                    + json.dumps(pre_receipt, sort_keys=True)
                )

            # Public apply cannot reconstruct authority from the prepared record.
            public_pre = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"]({
                    "plan_token": pre_preview["plan_token"]
                })
            )
            if (
                public_pre.get("error") != "p5_01_mutation_not_authorized"
                or public_pre.get("plan_known") is not False
                or public_pre.get("mutation_performed") is not False
            ):
                raise RuntimeError(
                    "I7 prepared record influenced public apply: "
                    + json.dumps(public_pre, sort_keys=True)
                )

            # ============================================================
            # I7-B: post-mutation failure after protected replacement but
            # before manifest/receipt finalization.
            # ============================================================
            post_note = vault / "post-failure.md"
            post_before = b"# post failure\r\nbefore\r\n"
            post_after_text = "# post failure\r\nafter protected replace\r\n"
            post_after = post_after_text.encode("utf-8")
            post_note.write_bytes(post_before)

            post_preview = json.loads(plugin.preview_edit({
                "target_relative_path": "post-failure.md",
                "new_content": post_after_text,
            }))
            if post_preview.get("success") is not True:
                raise RuntimeError("I7 post-failure preview failed")

            post_evidence = fresh_once(
                post_preview["plan_token"],
                "P5-02I I7-B POST-MUTATION FAILURE",
            )

            def fail_after_replace(name: str) -> None:
                if name == "edit_after_replace":
                    raise RuntimeError("p5_02i_i7_post_mutation_interrupt")

            post_result = plugin._execute_disposable_plan_candidate(
                post_preview["plan_token"],
                approval_evidence=post_evidence,
                require_fresh_approval=True,
                failure_hook=fail_after_replace,
            )

            if post_result.get("success") is not False:
                raise RuntimeError(
                    f"I7 post-failure unexpectedly succeeded: {post_result}"
                )
            if post_result.get("mutation_performed") is not True:
                raise RuntimeError(
                    f"I7 post-failure did not report mutation: {post_result}"
                )
            if post_result.get("recovery_required") is not True:
                raise RuntimeError(
                    f"I7 post-failure did not require recovery: {post_result}"
                )
            if post_note.read_bytes() != post_after:
                raise RuntimeError("I7 post-failure protected bytes mismatch")

            post_dir = recovery / post_preview["plan_token"]
            if not post_dir.is_dir():
                raise RuntimeError("I7 post-failure recovery directory missing")
            if (post_dir / "original.bin").read_bytes() != post_before:
                raise RuntimeError("I7 post-failure recovery backup mismatch")

            post_manifest = json.loads(
                (post_dir / "manifest.json").read_text(encoding="utf-8")
            )
            post_receipt_raw = json.loads(
                (post_dir / "receipt.json").read_text(encoding="utf-8")
            )
            if post_manifest.get("state") != "prepared":
                raise RuntimeError("I7 post-failure manifest unexpectedly finalized")
            if post_receipt_raw.get("state") != "prepared":
                raise RuntimeError("I7 post-failure receipt unexpectedly finalized")

            # Simulate restart again. No mutation/recovery retry is attempted.
            clear_ephemeral(plugin)

            post_recovery = plugin._inspect_disposable_recovery_candidate(
                post_preview["plan_token"]
            )
            post_receipt = plugin._inspect_disposable_receipt_candidate(
                post_preview["plan_token"]
            )

            if (
                post_recovery.get("success") is not True
                or post_recovery.get("classification") != "applied_unfinalized"
                or post_recovery.get("recovery_required") is not True
            ):
                raise RuntimeError(
                    "I7 post-failure recovery classification mismatch: "
                    + json.dumps(post_recovery, sort_keys=True)
                )

            if (
                post_receipt.get("success") is not True
                or post_receipt.get("correlation_valid") is not True
                or post_receipt.get("receipt_state") != "prepared"
                or post_receipt.get("receipt_finalized") is not False
                or post_receipt.get("receipt_reconciliation_required") is not True
                or post_receipt.get("final_classification") is not None
                or post_receipt.get("current_classification") != "applied_unfinalized"
                or post_receipt.get("recovery_required") is not True
                or post_receipt.get("authorization_reusable") is not False
            ):
                raise RuntimeError(
                    "I7 post-failure receipt classification mismatch: "
                    + json.dumps(post_receipt, sort_keys=True)
                )

            # Explicitly do NOT retry or auto-repair. Public apply remains inert.
            public_post = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"]({
                    "plan_token": post_preview["plan_token"]
                })
            )
            if (
                public_post.get("error") != "p5_01_mutation_not_authorized"
                or public_post.get("plan_known") is not False
                or public_post.get("mutation_performed") is not False
            ):
                raise RuntimeError(
                    "I7 applied-unfinalized record influenced public apply: "
                    + json.dumps(public_post, sort_keys=True)
                )

            print("", flush=True)
            print("I7_PRE_FAILURE_RESULT_REFUSED=true", flush=True)
            print("I7_PRE_FAILURE_PROTECTED_BYTES_UNCHANGED=true", flush=True)
            print("I7_PRE_FAILURE_RECOVERY_CLASSIFICATION=prepared_no_effect", flush=True)
            print("I7_PRE_FAILURE_RECEIPT_STATE=prepared", flush=True)
            print("I7_PRE_FAILURE_RECONCILIATION_REQUIRED=true", flush=True)
            print("I7_POST_FAILURE_MUTATION_PERFORMED=true", flush=True)
            print("I7_POST_FAILURE_RECOVERY_CLASSIFICATION=applied_unfinalized", flush=True)
            print("I7_POST_FAILURE_RECEIPT_STATE=prepared", flush=True)
            print("I7_POST_FAILURE_RECONCILIATION_REQUIRED=true", flush=True)
            print("I7_POST_FAILURE_RECOVERY_REQUIRED=true", flush=True)
            print("I7_NO_AUTO_RETRY_OR_REPAIR=true", flush=True)
            print("I7_RESTART_CLASSIFICATION_DISK_DERIVED=true", flush=True)
            print("I7_AUTHORIZATION_REUSABLE=false", flush=True)
            print("I7_REGISTERED_APPLY_FAIL_CLOSED=true", flush=True)
            print("I7_REAL_VAULT_INBOX_TOUCHED=false", flush=True)

        passed = True
        return 0
    finally:
        if passed:
            shutil.rmtree(fixture)
            print("DISPOSABLE_FIXTURE_CLEANED_AFTER_EVIDENCE=true", flush=True)
            print("P5_02I_I7_QUALIFICATION=PASS", flush=True)
        else:
            print(
                f"P5_02I_I7_QUALIFICATION=FAIL; FIXTURE_PRESERVED={fixture}",
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("P5_02I_I7_QUALIFICATION=ABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(
            f"P5_02I_I7_QUALIFICATION=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
