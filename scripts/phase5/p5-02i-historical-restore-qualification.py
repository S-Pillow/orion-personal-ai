#!/usr/bin/env python3
"""P5-02I I6 installed-runtime historical restore qualification.

Uses only temporary disposable roots. Establishes committed edit/move origin
transactions with fresh human ALLOW ONCE decisions, then performs historical
edit and move-source restores with NEW fresh ALLOW ONCE decisions. Also proves
origin approval cannot authorize restore and stale restore approval is consumed.

No real Orion vault/inbox path is used. Public apply remains fail-closed.
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
        raise RuntimeError("MCP calls are forbidden in P5-02I I6")


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


def snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def load_installed_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    if not plugin_file.is_file():
        raise RuntimeError(f"installed plugin missing: {plugin_file}")
    spec = importlib.util.spec_from_file_location(
        "orion_p5_02i_installed_i6_probe", plugin_file
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
        raise RuntimeError("Hermes gateway is running; I6 expects manual-off state")

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
        tempfile.mkdtemp(prefix="orion-p5-02i-i6-", dir=str(fixture_parent))
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

            # ============================================================
            # A. Establish committed edit origin with fresh approval.
            # ============================================================
            edit_note = vault / "historical-edit.md"
            edit_before = b"# historical edit\r\nbefore\r\n"
            edit_after_text = "# historical edit\r\nafter origin commit\r\n"
            edit_after = edit_after_text.encode("utf-8")
            edit_note.write_bytes(edit_before)

            edit_preview = json.loads(plugin.preview_edit({
                "target_relative_path": "historical-edit.md",
                "new_content": edit_after_text,
            }))
            if edit_preview.get("success") is not True:
                raise RuntimeError("I6 edit-origin preview failed")

            edit_origin_evidence = fresh_once(
                edit_preview["plan_token"],
                "P5-02I I6-A EDIT ORIGIN",
            )
            edit_origin = plugin._execute_disposable_plan_candidate(
                edit_preview["plan_token"],
                approval_evidence=edit_origin_evidence,
                require_fresh_approval=True,
            )
            if (
                edit_origin.get("success") is not True
                or edit_origin.get("mutation_performed") is not True
            ):
                raise RuntimeError(f"I6 edit-origin commit failed: {edit_origin}")
            if edit_note.read_bytes() != edit_after:
                raise RuntimeError("I6 edit-origin bytes mismatch")

            edit_origin_dir = Path(edit_origin["recovery_dir"])
            edit_origin_snapshot = snapshot_tree(edit_origin_dir)

            # ============================================================
            # B. Establish committed move origin with fresh approval.
            # ============================================================
            move_source = inbox / "historical-move.md"
            move_target = vault / "Projects" / "historical-move.md"
            move_bytes = (
                b"---\r\n"
                b"orion_draft: true\r\n"
                b"status: draft\r\n"
                b"---\r\n"
                b"# historical move\r\n"
            )
            move_source.write_bytes(move_bytes)

            move_preview = json.loads(plugin.preview_move_draft({
                "source_draft": "historical-move.md",
                "target_relative_path": "Projects/historical-move.md",
            }))
            if move_preview.get("success") is not True:
                raise RuntimeError("I6 move-origin preview failed")

            move_origin_evidence = fresh_once(
                move_preview["plan_token"],
                "P5-02I I6-B MOVE ORIGIN",
            )
            move_origin = plugin._execute_disposable_plan_candidate(
                move_preview["plan_token"],
                approval_evidence=move_origin_evidence,
                require_fresh_approval=True,
            )
            if (
                move_origin.get("success") is not True
                or move_origin.get("mutation_performed") is not True
            ):
                raise RuntimeError(f"I6 move-origin commit failed: {move_origin}")
            if move_source.exists():
                raise RuntimeError("I6 move-origin source still exists")
            if move_target.read_bytes() != move_bytes:
                raise RuntimeError("I6 move-origin target mismatch")

            move_origin_dir = Path(move_origin["recovery_dir"])
            move_origin_snapshot = snapshot_tree(move_origin_dir)
            move_target_before_restore = move_target.read_bytes()

            # ============================================================
            # C. Build historical edit restore preview. Origin approval must
            #    NOT authorize the restore.
            # ============================================================
            edit_restore = plugin._preview_disposable_restore_candidate(
                edit_preview["plan_token"]
            )
            if edit_restore.get("success") is not True:
                raise RuntimeError(
                    f"I6 edit restore preview failed: {edit_restore}"
                )
            if edit_restore.get("plan", {}).get("action") != "restore_edit":
                raise RuntimeError("I6 edit restore preview action mismatch")

            origin_misuse = plugin._execute_disposable_restore_candidate(
                edit_restore["plan_token"],
                approval_evidence=edit_origin_evidence,
            )
            expect_failure(
                origin_misuse,
                "approval_evidence_invalid",
                "origin edit approval used for restore",
            )
            if edit_note.read_bytes() != edit_after:
                raise RuntimeError("origin approval misuse changed edit target")
            if (recovery / edit_restore["plan_token"]).exists():
                raise RuntimeError("origin approval misuse created restore record")

            edit_restore_evidence = fresh_once(
                edit_restore["plan_token"],
                "P5-02I I6-C HISTORICAL EDIT RESTORE",
            )
            edit_restored = plugin._execute_disposable_restore_candidate(
                edit_restore["plan_token"],
                approval_evidence=edit_restore_evidence,
            )
            if (
                edit_restored.get("success") is not True
                or edit_restored.get("mutation_performed") is not True
            ):
                raise RuntimeError(
                    f"I6 historical edit restore failed: {edit_restored}"
                )
            if edit_note.read_bytes() != edit_before:
                raise RuntimeError("I6 edit restore did not restore original bytes")
            if edit_restored.get("recovery_id") != edit_restore["plan_token"]:
                raise RuntimeError("I6 edit restore recovery id mismatch")
            if edit_restored.get("recovery_id") == edit_preview["plan_token"]:
                raise RuntimeError("I6 edit restore reused origin recovery id")

            edit_restore_dir = Path(edit_restored["recovery_dir"])
            edit_restore_manifest = json.loads(
                (edit_restore_dir / "manifest.json").read_text(encoding="utf-8")
            )
            edit_restore_receipt = json.loads(
                (edit_restore_dir / "receipt.json").read_text(encoding="utf-8")
            )
            if edit_restore_manifest.get("state") != "committed":
                raise RuntimeError("I6 edit restore manifest not committed")
            if edit_restore_manifest.get("action") != "restore_edit":
                raise RuntimeError("I6 edit restore manifest action mismatch")
            if (
                edit_restore_manifest.get("origin_recovery_id")
                != edit_preview["plan_token"]
            ):
                raise RuntimeError("I6 edit restore origin correlation mismatch")
            if edit_restore_receipt.get("state") != "committed":
                raise RuntimeError("I6 edit restore receipt not committed")
            if (
                edit_restore_receipt.get("origin_recovery_id")
                != edit_preview["plan_token"]
            ):
                raise RuntimeError("I6 edit restore receipt origin mismatch")
            if (
                edit_restore_receipt.get("approval", {}).get("attempt_id")
                != edit_restore_evidence["attempt_id"]
            ):
                raise RuntimeError("I6 edit restore fresh approval correlation mismatch")
            if snapshot_tree(edit_origin_dir) != edit_origin_snapshot:
                raise RuntimeError("I6 edit origin recovery record was modified")

            edit_restore_inspected = plugin._inspect_disposable_receipt_candidate(
                edit_restore["plan_token"]
            )
            if (
                edit_restore_inspected.get("success") is not True
                or edit_restore_inspected.get("current_classification") != "committed"
                or edit_restore_inspected.get("authorization_reusable") is not False
            ):
                raise RuntimeError(
                    "I6 edit restore receipt inspection failed: "
                    + json.dumps(edit_restore_inspected, sort_keys=True)
                )

            # ============================================================
            # D. Historical move-source restore. It recreates only the inbox
            #    source and must leave the vault target byte-for-byte unchanged.
            # ============================================================
            move_restore = plugin._preview_disposable_restore_candidate(
                move_preview["plan_token"]
            )
            if move_restore.get("success") is not True:
                raise RuntimeError(
                    f"I6 move restore preview failed: {move_restore}"
                )
            if move_restore.get("plan", {}).get("action") != "restore_move_source":
                raise RuntimeError("I6 move restore preview action mismatch")

            move_origin_misuse = plugin._execute_disposable_restore_candidate(
                move_restore["plan_token"],
                approval_evidence=move_origin_evidence,
            )
            expect_failure(
                move_origin_misuse,
                "approval_evidence_invalid",
                "origin move approval used for restore",
            )
            if move_source.exists():
                raise RuntimeError("origin move approval misuse recreated source")
            if move_target.read_bytes() != move_target_before_restore:
                raise RuntimeError("origin move approval misuse changed vault target")

            move_restore_evidence = fresh_once(
                move_restore["plan_token"],
                "P5-02I I6-D HISTORICAL MOVE-SOURCE RESTORE",
            )
            move_restored = plugin._execute_disposable_restore_candidate(
                move_restore["plan_token"],
                approval_evidence=move_restore_evidence,
            )
            if (
                move_restored.get("success") is not True
                or move_restored.get("mutation_performed") is not True
            ):
                raise RuntimeError(
                    f"I6 historical move restore failed: {move_restored}"
                )
            if move_source.read_bytes() != move_bytes:
                raise RuntimeError("I6 move restore source bytes mismatch")
            if move_target.read_bytes() != move_target_before_restore:
                raise RuntimeError("I6 move restore changed vault target")
            if move_restored.get("recovery_id") != move_restore["plan_token"]:
                raise RuntimeError("I6 move restore recovery id mismatch")
            if move_restored.get("recovery_id") == move_preview["plan_token"]:
                raise RuntimeError("I6 move restore reused origin recovery id")

            move_restore_dir = Path(move_restored["recovery_dir"])
            move_restore_manifest = json.loads(
                (move_restore_dir / "manifest.json").read_text(encoding="utf-8")
            )
            move_restore_receipt = json.loads(
                (move_restore_dir / "receipt.json").read_text(encoding="utf-8")
            )
            if move_restore_manifest.get("state") != "committed":
                raise RuntimeError("I6 move restore manifest not committed")
            if move_restore_manifest.get("action") != "restore_move_source":
                raise RuntimeError("I6 move restore manifest action mismatch")
            if (
                move_restore_manifest.get("origin_recovery_id")
                != move_preview["plan_token"]
            ):
                raise RuntimeError("I6 move restore origin correlation mismatch")
            if move_restore_receipt.get("state") != "committed":
                raise RuntimeError("I6 move restore receipt not committed")
            if (
                move_restore_receipt.get("approval", {}).get("attempt_id")
                != move_restore_evidence["attempt_id"]
            ):
                raise RuntimeError("I6 move restore fresh approval correlation mismatch")
            if snapshot_tree(move_origin_dir) != move_origin_snapshot:
                raise RuntimeError("I6 move origin recovery record was modified")

            move_restore_inspected = plugin._inspect_disposable_receipt_candidate(
                move_restore["plan_token"]
            )
            if (
                move_restore_inspected.get("success") is not True
                or move_restore_inspected.get("current_classification") != "committed"
                or move_restore_inspected.get("authorization_reusable") is not False
            ):
                raise RuntimeError(
                    "I6 move restore receipt inspection failed: "
                    + json.dumps(move_restore_inspected, sort_keys=True)
                )

            # ============================================================
            # E. Stale restore after approval consumes that approval.
            #    Use a second edit transaction so successful C remains intact.
            # ============================================================
            stale_note = vault / "stale-restore.md"
            stale_before = b"# stale restore\r\nbefore\r\n"
            stale_after_text = "# stale restore\r\nafter origin\r\n"
            stale_after = stale_after_text.encode("utf-8")
            stale_note.write_bytes(stale_before)

            stale_origin_preview = json.loads(plugin.preview_edit({
                "target_relative_path": "stale-restore.md",
                "new_content": stale_after_text,
            }))
            if stale_origin_preview.get("success") is not True:
                raise RuntimeError("I6 stale-origin preview failed")

            stale_origin_evidence = fresh_once(
                stale_origin_preview["plan_token"],
                "P5-02I I6-E STALE-RESTORE ORIGIN",
            )
            stale_origin = plugin._execute_disposable_plan_candidate(
                stale_origin_preview["plan_token"],
                approval_evidence=stale_origin_evidence,
                require_fresh_approval=True,
            )
            if stale_origin.get("success") is not True:
                raise RuntimeError(f"I6 stale-origin commit failed: {stale_origin}")
            if stale_note.read_bytes() != stale_after:
                raise RuntimeError("I6 stale-origin bytes mismatch")

            stale_restore = plugin._preview_disposable_restore_candidate(
                stale_origin_preview["plan_token"]
            )
            if stale_restore.get("success") is not True:
                raise RuntimeError("I6 stale restore preview failed")

            stale_restore_evidence = fresh_once(
                stale_restore["plan_token"],
                "P5-02I I6-F STALE RESTORE CONSUMPTION",
            )

            newer = b"# stale restore\r\nnewer user edit after approval\r\n"
            stale_note.write_bytes(newer)
            stale_result = plugin._execute_disposable_restore_candidate(
                stale_restore["plan_token"],
                approval_evidence=stale_restore_evidence,
            )
            expect_failure(
                stale_result,
                "restore_current_state_changed",
                "stale historical edit restore",
            )
            if stale_note.read_bytes() != newer:
                raise RuntimeError("I6 stale restore changed newer bytes")
            if (recovery / stale_restore["plan_token"]).exists():
                raise RuntimeError("I6 stale restore created recovery transaction")

            # Return to the previewed current bytes; consumed approval still
            # cannot be revived.
            stale_note.write_bytes(stale_after)
            stale_replay = plugin._execute_disposable_restore_candidate(
                stale_restore["plan_token"],
                approval_evidence=stale_restore_evidence,
            )
            expect_failure(
                stale_replay,
                "approval_evidence_already_consumed",
                "stale restore approval replay",
            )
            if stale_note.read_bytes() != stale_after:
                raise RuntimeError("I6 stale restore replay mutated fixture")

            # Public apply remains inert for restore plans too.
            public_restore = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"]({
                    "plan_token": edit_restore["plan_token"]
                })
            )
            if (
                public_restore.get("error") != "p5_01_mutation_not_authorized"
                or public_restore.get("mutation_performed") is not False
            ):
                raise RuntimeError("registered apply no longer fails closed")

            print("", flush=True)
            print("I6_EDIT_ORIGIN_COMMITTED=true", flush=True)
            print("I6_MOVE_ORIGIN_COMMITTED=true", flush=True)
            print("I6_ORIGIN_APPROVAL_CANNOT_AUTHORIZE_RESTORE=true", flush=True)
            print("I6_EDIT_RESTORE_COMMITTED=true", flush=True)
            print("I6_EDIT_RESTORE_INDEPENDENT_RECORD=true", flush=True)
            print("I6_EDIT_ORIGIN_RECORD_UNCHANGED=true", flush=True)
            print("I6_MOVE_SOURCE_RESTORED=true", flush=True)
            print("I6_MOVE_VAULT_TARGET_UNCHANGED=true", flush=True)
            print("I6_MOVE_RESTORE_INDEPENDENT_RECORD=true", flush=True)
            print("I6_MOVE_ORIGIN_RECORD_UNCHANGED=true", flush=True)
            print("I6_RESTORE_APPROVAL_FRESH_ONCE=true", flush=True)
            print("I6_STALE_RESTORE_REFUSED=true", flush=True)
            print("I6_STALE_RESTORE_APPROVAL_CONSUMED=true", flush=True)
            print("I6_REGISTERED_APPLY_FAIL_CLOSED=true", flush=True)
            print("I6_REAL_VAULT_INBOX_TOUCHED=false", flush=True)

        passed = True
        return 0
    finally:
        if passed:
            shutil.rmtree(fixture)
            print("DISPOSABLE_FIXTURE_CLEANED=true", flush=True)
            print("P5_02I_I6_QUALIFICATION=PASS", flush=True)
        else:
            print(
                f"P5_02I_I6_QUALIFICATION=FAIL; FIXTURE_PRESERVED={fixture}",
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("P5_02I_I6_QUALIFICATION=ABORTED", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(
            f"P5_02I_I6_QUALIFICATION=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
