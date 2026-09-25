#!/usr/bin/env python3
"""P5-02T first production move gate.

Performs exactly one authorized move_draft of the frozen P5-02S controlled
fixture through the installed registered Orion apply path.

The gate:
- binds discovered Orion handlers to the exact verified installed plugin path;
- revalidates the frozen source path, bytes, SHA-256, Windows file identity,
  absent target, exact preview plan, and exact diff while mutation is disabled;
- requires the accepted P5-02Q/P5-02R two-record recovery baseline;
- enables production mutation only inside this process around one apply dispatch;
- requires a fresh Hermes human ONCE approval;
- verifies source-absent + target-exact postconditions and a new committed
  move recovery/receipt record;
- never auto-restores, deletes the target, or cleans recovery evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


APPLY_TOOL = "orion_vault_apply_plan"
PREVIEW_MOVE_TOOL = "orion_vault_preview_move_draft"

EXPECTED_VAULT_ROOT = Path(r"C:\Personal\Me")
EXPECTED_INBOX_ROOT = Path(r"C:\Personal\Orion-Inbox")
SOURCE_RELATIVE_PATH = "_Orion-P5-Move-Canary.md"
TARGET_RELATIVE_PATH = "_Orion-P5-Move-Canary.md"
EXPECTED_SOURCE_PATH = Path(r"C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md")
EXPECTED_TARGET_PATH = Path(r"C:\Personal\Me\_Orion-P5-Move-Canary.md")
EXPECTED_SOURCE_FILE_ID = (
    "5e1aeb8a1aeb5d91:eec0070000001f000000000000000000"
)

SOURCE_BYTES = (
    b"---\n"
    b"orion_draft: true\n"
    b"status: draft\n"
    b"date: 2026-09-24\n"
    b"origin: p5-02s-controlled-fixture\n"
    b"---\n"
    b"# Orion Phase 5 Move Canary\n"
    b"state: inbox\n"
    b"gate: first-production-move\n"
)
EXPECTED_SOURCE_SHA256 = (
    "132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132"
)
EXPECTED_DIFF_SHA256 = (
    "61e4f48a0964aec273217a87dc3d7ac706f2a6525886420ee5e6d80fcb26a587"
)

ORIGIN_EDIT_RECOVERY_ID = (
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f"
)
RESTORE_RECOVERY_ID = (
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_json_result(raw: object, *, label: str) -> dict:
    if not isinstance(raw, str):
        raise RuntimeError(f"{label} returned non-string result")
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"{label} returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} returned non-object JSON")
    return value


def index_records(inventory: dict) -> dict[str, dict]:
    records = inventory.get("records")
    if not isinstance(records, list):
        raise RuntimeError("recovery inventory records missing")
    indexed: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("recovery inventory contains non-object record")
        recovery_id = record.get("recovery_id")
        if not isinstance(recovery_id, str) or recovery_id in indexed:
            raise RuntimeError("recovery inventory id invalid/duplicate")
        indexed[recovery_id] = record
    return indexed


def require_historical_baseline(records: dict[str, dict]) -> None:
    if set(records) != {ORIGIN_EDIT_RECOVERY_ID, RESTORE_RECOVERY_ID}:
        raise RuntimeError(
            "production recovery id set differs from accepted P5-02R state"
        )

    origin = records[ORIGIN_EDIT_RECOVERY_ID]
    restore = records[RESTORE_RECOVERY_ID]
    for record in (origin, restore):
        if (
            record.get("valid") is not True
            or record.get("needs_attention") is not False
        ):
            raise RuntimeError(
                "production recovery baseline contains invalid/attention record"
            )

    origin_recovery = origin.get("recovery")
    origin_receipt = origin.get("receipt")
    restore_recovery = restore.get("recovery")
    restore_receipt = restore.get("receipt")
    if not all(
        isinstance(item, dict)
        for item in (
            origin_recovery,
            origin_receipt,
            restore_recovery,
            restore_receipt,
        )
    ):
        raise RuntimeError("production recovery baseline inspection missing")

    if (
        origin_recovery.get("manifest_state") != "committed"
        or origin_recovery.get("classification") != "committed_then_changed"
        or origin_recovery.get("recovery_required") is not False
        or origin_receipt.get("receipt_state") != "committed"
        or origin_receipt.get("receipt_finalized") is not True
        or origin_receipt.get("receipt_reconciliation_required") is not False
        or origin_receipt.get("current_classification")
        != "committed_then_changed"
    ):
        raise RuntimeError(
            "P5-02Q origin record differs from accepted P5-02R state"
        )

    if (
        restore_recovery.get("manifest_state") != "committed"
        or restore_recovery.get("classification") != "committed"
        or restore_recovery.get("recovery_required") is not False
        or restore_receipt.get("receipt_state") != "committed"
        or restore_receipt.get("receipt_finalized") is not True
        or restore_receipt.get("receipt_reconciliation_required") is not False
        or restore_receipt.get("current_classification") != "committed"
    ):
        raise RuntimeError("P5-02R restore record differs from accepted state")


def emit_observed_failure_state(
    plugin,
    source: Path,
    target: Path,
    recovery_root: Path,
    *,
    stage: str,
    error: str,
) -> None:
    print(f"P5_02T_FAILURE_STAGE={stage}")
    print(f"P5_02T_FAILURE_ERROR={error}")
    try:
        if os.path.lexists(source):
            print("P5_02T_POST_FAILURE_SOURCE_STATE=present")
            if source.is_file():
                print(
                    "P5_02T_POST_FAILURE_SOURCE_SHA256="
                    f"{sha256(source.read_bytes())}"
                )
                if os.name == "nt":
                    print(
                        "P5_02T_POST_FAILURE_SOURCE_FILE_ID="
                        f"{plugin._windows_path_file_identity(source)}"
                    )
        else:
            print("P5_02T_POST_FAILURE_SOURCE_STATE=absent")
    except Exception as exc:
        print(
            "P5_02T_POST_FAILURE_SOURCE_INSPECTION_ERROR="
            f"{type(exc).__name__}"
        )

    try:
        if os.path.lexists(target):
            print("P5_02T_POST_FAILURE_TARGET_STATE=present")
            if target.is_file():
                print(
                    "P5_02T_POST_FAILURE_TARGET_SHA256="
                    f"{sha256(target.read_bytes())}"
                )
        else:
            print("P5_02T_POST_FAILURE_TARGET_STATE=absent")
    except Exception as exc:
        print(
            "P5_02T_POST_FAILURE_TARGET_INSPECTION_ERROR="
            f"{type(exc).__name__}"
        )

    try:
        inventory = plugin._enumerate_production_recovery_records()
        print(
            "P5_02T_POST_FAILURE_RECOVERY_ENUM_SUCCESS="
            f"{str(bool(inventory.get('success'))).lower()}"
        )
        if inventory.get("success"):
            print(
                "P5_02T_POST_FAILURE_RECOVERY_COUNT="
                f"{inventory.get('record_count')}"
            )
            print(
                "P5_02T_POST_FAILURE_RECOVERY_ATTENTION="
                f"{inventory.get('attention_count')}"
            )
            print(
                "P5_02T_POST_FAILURE_RECOVERY_TRUNCATED="
                f"{str(bool(inventory.get('truncated'))).lower()}"
            )
    except Exception as exc:
        print(
            "P5_02T_POST_FAILURE_RECOVERY_ENUM_ERROR="
            f"{type(exc).__name__}"
        )

    print(f"P5_02T_RECOVERY_ROOT={recovery_root}")
    print("P5_02T_AUTOMATIC_RESTORE=false")
    print("P5_02T_AUTOMATIC_TARGET_DELETE=false")
    print("P5_02T_RECOVERY_EVIDENCE_PRESERVED=true")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument("expected_recovery_root", type=Path)
    args = parser.parse_args()

    profile = args.profile.resolve(strict=True)
    plugin_dir = args.plugin_dir.resolve(strict=True)
    expected_recovery_root = args.expected_recovery_root.resolve(strict=True)

    for name in (
        "ORION_P5_PRODUCTION_RECOVERY_ROOT",
        "ORION_P5_MUTATION_MODE",
        "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
        "ORION_P5_RECOVERY_ROOT",
    ):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(
                f"ambient Phase 5 setting unexpectedly present: {name}"
            )

    os.environ["HERMES_HOME"] = str(profile)

    from hermes_cli.env_loader import load_hermes_dotenv
    from hermes_cli.plugins import discover_plugins
    from model_tools import handle_function_call
    from tools.approval import (
        reset_hermes_interactive_context,
        set_hermes_interactive_context,
    )
    from tools.registry import registry

    loaded = load_hermes_dotenv(hermes_home=profile)
    if profile / ".env" not in [Path(item).resolve() for item in loaded]:
        raise RuntimeError("Hermes loader did not report COMPANION .env as loaded")

    effective_recovery = (
        os.environ.get("ORION_P5_PRODUCTION_RECOVERY_ROOT") or ""
    ).strip()
    if not effective_recovery:
        raise RuntimeError("persisted production recovery root was not loaded")
    if Path(effective_recovery).resolve(strict=True) != expected_recovery_root:
        raise RuntimeError("effective production recovery root mismatch")
    if (os.environ.get("ORION_P5_MUTATION_MODE") or "").strip():
        raise RuntimeError("production mutation mode unexpectedly persisted")
    for name in ("ORION_P5_ALLOW_DISPOSABLE_MUTATION", "ORION_P5_RECOVERY_ROOT"):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(
                f"disposable mutation setting unexpectedly persisted: {name}"
            )

    discover_plugins()
    apply_entry = registry.get_entry(APPLY_TOOL)
    preview_entry = registry.get_entry(PREVIEW_MOVE_TOOL)
    if apply_entry is None or preview_entry is None:
        raise RuntimeError("installed Orion move/apply tools were not discovered")
    if apply_entry.handler.__name__ != "apply_plan_production_guarded":
        raise RuntimeError("registered apply handler identity mismatch")
    if preview_entry.handler.__name__ != "preview_move_draft":
        raise RuntimeError("registered move-preview handler identity mismatch")

    expected_plugin_file = (plugin_dir / "__init__.py").resolve(strict=True)
    apply_module = sys.modules.get(apply_entry.handler.__module__)
    preview_module = sys.modules.get(preview_entry.handler.__module__)
    if apply_module is None or preview_module is None:
        raise RuntimeError("installed Orion plugin module unavailable")

    apply_module_file = Path(
        getattr(apply_module, "__file__", "")
    ).resolve(strict=True)
    preview_module_file = Path(
        getattr(preview_module, "__file__", "")
    ).resolve(strict=True)
    if apply_module_file != expected_plugin_file:
        raise RuntimeError(
            "registered apply handler was not loaded from verified installed plugin"
        )
    if preview_module_file != expected_plugin_file:
        raise RuntimeError(
            "registered move-preview handler was not loaded from verified installed plugin"
        )
    if apply_module is not preview_module:
        raise RuntimeError("registered Orion tools were loaded from different modules")

    plugin = apply_module
    if apply_entry.handler is not plugin.apply_plan_production_guarded:
        raise RuntimeError("registered apply handler object mismatch")
    if preview_entry.handler is not plugin.preview_move_draft:
        raise RuntimeError("registered move-preview handler object mismatch")
    if plugin._execute_production_plan_candidate in {
        entry.handler for entry in registry.get_all_entries()
    }:
        raise RuntimeError("private production executor unexpectedly registered")

    mode = plugin._production_mutation_mode()
    if (
        mode.get("valid") is not True
        or mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED
        or mode.get("mutation_allowed") is not False
    ):
        raise RuntimeError(f"unexpected pre-move production mode: {mode}")

    roots = plugin._validate_production_roots()
    if roots.get("success") is not True:
        raise RuntimeError("native production-root validation failed before move")
    if roots.get("mutation_allowed") is not False:
        raise RuntimeError("native production-root validation unexpectedly allows mutation")

    vault_root = Path(roots["vault_root"]).resolve(strict=True)
    inbox_root = Path(roots["inbox_root"]).resolve(strict=True)
    recovery_root = Path(roots["recovery_root"]).resolve(strict=True)
    if vault_root != EXPECTED_VAULT_ROOT:
        raise RuntimeError("accepted vault root mismatch")
    if inbox_root != EXPECTED_INBOX_ROOT:
        raise RuntimeError("accepted inbox root mismatch")
    if recovery_root != expected_recovery_root:
        raise RuntimeError("native recovery-root mismatch")

    inventory_before = plugin._enumerate_production_recovery_records()
    if (
        inventory_before.get("success") is not True
        or inventory_before.get("record_count") != 2
        or inventory_before.get("attention_count") != 0
        or inventory_before.get("truncated") is not False
    ):
        raise RuntimeError(
            "production recovery inventory differs from accepted P5-02R baseline"
        )
    require_historical_baseline(index_records(inventory_before))

    source = inbox_root / SOURCE_RELATIVE_PATH
    target = vault_root / TARGET_RELATIVE_PATH

    if not source.is_file():
        raise RuntimeError("controlled move source fixture is missing")
    if source.resolve(strict=True) != EXPECTED_SOURCE_PATH:
        raise RuntimeError("controlled move source canonical path mismatch")
    if plugin._path_has_reparse_component(source):
        raise RuntimeError("controlled move source has a reparse component")
    if target.resolve(strict=False) != EXPECTED_TARGET_PATH:
        raise RuntimeError("controlled move target canonical candidate mismatch")
    if os.path.lexists(target):
        raise RuntimeError("controlled move target is not absent")
    if plugin._path_has_reparse_component(target.parent):
        raise RuntimeError("controlled move target parent has a reparse component")

    source_bytes = source.read_bytes()
    if source_bytes != SOURCE_BYTES:
        raise RuntimeError("controlled move source bytes differ from frozen fixture")
    if sha256(source_bytes) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("controlled move source SHA-256 mismatch")
    source_file_id = plugin._windows_path_file_identity(source)
    if source_file_id != EXPECTED_SOURCE_FILE_ID:
        raise RuntimeError("controlled move source Windows file identity mismatch")

    raw_preview = handle_function_call(
        PREVIEW_MOVE_TOOL,
        {
            "source_draft": SOURCE_RELATIVE_PATH,
            "target_relative_path": TARGET_RELATIVE_PATH,
        },
        task_id="p5-02t-move-preview",
        session_id="p5-02t-move-preview",
        tool_call_id="p5-02t-move-preview-call",
        turn_id="p5-02t-move-preview-turn",
        user_task="P5-02T exact first production move preview",
        enabled_tools=[PREVIEW_MOVE_TOOL],
        enabled_toolsets=["orion_vault"],
    )
    preview = parse_json_result(raw_preview, label="move preview")
    if (
        preview.get("success") is not True
        or preview.get("mutation_performed") is not False
    ):
        raise RuntimeError("exact production move preview did not succeed read-only")

    plan = preview.get("plan")
    diff_text = preview.get("diff")
    if not isinstance(plan, dict) or not isinstance(diff_text, str):
        raise RuntimeError("production move preview contract missing plan/diff")
    if plan.get("action") != "move_draft":
        raise RuntimeError("production move preview action mismatch")
    if plan.get("source_draft") != SOURCE_RELATIVE_PATH:
        raise RuntimeError("production move preview source-relative mismatch")
    if plan.get("source_canonical_path") != str(EXPECTED_SOURCE_PATH):
        raise RuntimeError("production move preview source-canonical mismatch")
    if plan.get("target_relative_path") != TARGET_RELATIVE_PATH:
        raise RuntimeError("production move preview target-relative mismatch")
    if plan.get("target_candidate_path") != str(EXPECTED_TARGET_PATH):
        raise RuntimeError("production move preview target candidate mismatch")
    if plan.get("target_canonical_path") != str(EXPECTED_TARGET_PATH):
        raise RuntimeError("production move preview target canonical mismatch")
    if (
        plan.get("target_existing_ancestor_canonical_path")
        != str(EXPECTED_VAULT_ROOT)
    ):
        raise RuntimeError("production move preview target ancestor mismatch")
    if plan.get("target_state") != "absent":
        raise RuntimeError("production move preview target state is not absent")
    if plan.get("source_sha256") != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("production move preview source hash mismatch")
    if plan.get("source_file_id") != EXPECTED_SOURCE_FILE_ID:
        raise RuntimeError("production move preview source file identity mismatch")
    if plan.get("diff_sha256") != EXPECTED_DIFF_SHA256:
        raise RuntimeError("production move preview diff hash mismatch")
    if sha256(diff_text.encode("utf-8")) != EXPECTED_DIFF_SHA256:
        raise RuntimeError("production move preview exact diff differs from frozen contract")

    if source.read_bytes() != SOURCE_BYTES:
        raise RuntimeError("controlled move source changed during preview")
    if plugin._windows_path_file_identity(source) != EXPECTED_SOURCE_FILE_ID:
        raise RuntimeError("controlled move source identity changed during preview")
    if os.path.lexists(target):
        raise RuntimeError("controlled move target appeared during preview")

    inventory_after_preview = plugin._enumerate_production_recovery_records()
    if (
        inventory_after_preview.get("success") is not True
        or inventory_after_preview.get("record_count") != 2
        or inventory_after_preview.get("attention_count") != 0
        or inventory_after_preview.get("truncated") is not False
    ):
        raise RuntimeError("recovery inventory changed during move preview")
    require_historical_baseline(index_records(inventory_after_preview))

    plan_token = preview.get("plan_token")
    if not isinstance(plan_token, str) or not re.fullmatch(
        r"[0-9a-f]{64}", plan_token
    ):
        raise RuntimeError("production move preview plan token invalid")

    print("P5_02T_PREVIEW_CONTRACT=PASS")
    print(f"P5_02T_PLAN_TOKEN={plan_token}")
    print(f"P5_02T_SOURCE_CANONICAL_PATH={EXPECTED_SOURCE_PATH}")
    print(f"P5_02T_SOURCE_FILE_ID={EXPECTED_SOURCE_FILE_ID}")
    print(f"P5_02T_SOURCE_SHA256={EXPECTED_SOURCE_SHA256}")
    print(f"P5_02T_TARGET_CANONICAL_PATH={EXPECTED_TARGET_PATH}")
    print("P5_02T_TARGET_STATE_BEFORE=absent")
    print(f"P5_02T_MOVE_DIFF_SHA256={EXPECTED_DIFF_SHA256}")
    print("P5_02T_MUTATION_MODE_PERSISTED=false")
    print("P5_02T_PRODUCTION_RECOVERY_COUNT_BEFORE=2")
    print("P5_02T_PRODUCTION_RECOVERY_ATTENTION_BEFORE=0")
    print("P5_02T_EXACT_DIFF_BEGIN")
    print(diff_text, end="" if diff_text.endswith("\n") else "\n")
    print("P5_02T_EXACT_DIFF_END")
    print("")
    print("P5_02T_APPROVAL_PROMPT_EXPECTED=true")
    print("P5_02T_CHOOSE_ONCE_ONLY=true", flush=True)

    interactive_token = None
    raw_apply = None
    dispatch_error: Exception | None = None
    try:
        interactive_token = set_hermes_interactive_context(True)
        os.environ["ORION_P5_MUTATION_MODE"] = "mutation_enabled"

        enabled_mode = plugin._production_mutation_mode()
        if (
            enabled_mode.get("valid") is not True
            or enabled_mode.get("mode")
            != plugin.PRODUCTION_MODE_MUTATION_ENABLED
            or enabled_mode.get("mutation_allowed") is not True
        ):
            raise RuntimeError(
                "process-scoped production mutation mode did not enable correctly"
            )

        try:
            raw_apply = handle_function_call(
                APPLY_TOOL,
                {"plan_token": plan_token},
                task_id="p5-02t-production-move",
                session_id="p5-02t-production-move",
                tool_call_id="p5-02t-production-move-call",
                turn_id="p5-02t-production-move-turn",
                user_task="P5-02T exact first production move",
                enabled_tools=[APPLY_TOOL],
                enabled_toolsets=["orion_vault"],
            )
        except Exception as exc:
            dispatch_error = exc
    finally:
        os.environ.pop("ORION_P5_MUTATION_MODE", None)
        if interactive_token is not None:
            reset_hermes_interactive_context(interactive_token)

    disabled_after = plugin._production_mutation_mode()
    if (
        disabled_after.get("valid") is not True
        or disabled_after.get("mode") != plugin.PRODUCTION_MODE_DISABLED
        or disabled_after.get("mutation_allowed") is not False
    ):
        emit_observed_failure_state(
            plugin,
            source,
            target,
            recovery_root,
            stage="mutation_mode_cleanup",
            error="production mutation mode did not return to disabled",
        )
        raise RuntimeError("production mutation mode did not return to disabled")

    if dispatch_error is not None:
        emit_observed_failure_state(
            plugin,
            source,
            target,
            recovery_root,
            stage="registered_apply_dispatch",
            error=f"{type(dispatch_error).__name__}:{dispatch_error}",
        )
        raise dispatch_error

    result = parse_json_result(raw_apply, label="move apply")
    if (
        result.get("success") is not True
        or result.get("mutation_performed") is not True
        or result.get("recovery_required") is not False
    ):
        emit_observed_failure_state(
            plugin,
            source,
            target,
            recovery_root,
            stage="apply_result",
            error=str(result.get("error") or "unclean_apply_result"),
        )
        raise RuntimeError("P5-02T production move did not complete cleanly")

    if result.get("action") != "move_draft":
        raise RuntimeError("P5-02T result action mismatch")
    if result.get("source_draft") != SOURCE_RELATIVE_PATH:
        raise RuntimeError("P5-02T result source mismatch")
    if result.get("target_relative_path") != TARGET_RELATIVE_PATH:
        raise RuntimeError("P5-02T result target mismatch")

    recovery_id = result.get("recovery_id")
    if not isinstance(recovery_id, str) or not re.fullmatch(
        r"[0-9a-f]{64}", recovery_id
    ):
        raise RuntimeError("P5-02T recovery id invalid")
    if recovery_id != plan_token:
        raise RuntimeError("P5-02T recovery id does not equal move plan token")
    if recovery_id in {ORIGIN_EDIT_RECOVERY_ID, RESTORE_RECOVERY_ID}:
        raise RuntimeError("P5-02T recovery id collided with historical record")

    expected_recovery_dir = recovery_root / recovery_id
    result_recovery_dir = result.get("recovery_dir")
    if not isinstance(result_recovery_dir, str):
        raise RuntimeError("P5-02T result recovery directory missing")
    if (
        Path(result_recovery_dir).resolve(strict=True)
        != expected_recovery_dir.resolve(strict=True)
    ):
        raise RuntimeError("P5-02T result recovery directory mismatch")

    if os.path.lexists(source):
        raise RuntimeError("P5-02T source still exists after successful move")
    if not target.is_file():
        raise RuntimeError("P5-02T target missing after successful move")
    if target.resolve(strict=True) != EXPECTED_TARGET_PATH:
        raise RuntimeError("P5-02T target canonical path mismatch after move")
    if plugin._path_has_reparse_component(target):
        raise RuntimeError("P5-02T target became a reparse path")
    target_bytes = target.read_bytes()
    if target_bytes != SOURCE_BYTES:
        raise RuntimeError("P5-02T target bytes differ from frozen source bytes")
    if sha256(target_bytes) != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("P5-02T target SHA-256 mismatch")

    inventory_after = plugin._enumerate_production_recovery_records()
    if (
        inventory_after.get("success") is not True
        or inventory_after.get("record_count") != 3
        or inventory_after.get("attention_count") != 0
        or inventory_after.get("truncated") is not False
    ):
        raise RuntimeError(
            "P5-02T post-move recovery inventory is not three clean records"
        )

    records_after = index_records(inventory_after)
    if set(records_after) != {
        ORIGIN_EDIT_RECOVERY_ID,
        RESTORE_RECOVERY_ID,
        recovery_id,
    }:
        raise RuntimeError("P5-02T recovery id set mismatch after move")

    require_historical_baseline(
        {
            ORIGIN_EDIT_RECOVERY_ID: records_after[ORIGIN_EDIT_RECOVERY_ID],
            RESTORE_RECOVERY_ID: records_after[RESTORE_RECOVERY_ID],
        }
    )

    move_record = records_after[recovery_id]
    if (
        move_record.get("valid") is not True
        or move_record.get("needs_attention") is not False
    ):
        raise RuntimeError("new P5-02T move recovery record is not valid/clean")

    recovery = move_record.get("recovery")
    receipt = move_record.get("receipt")
    if not isinstance(recovery, dict) or not isinstance(receipt, dict):
        raise RuntimeError("new P5-02T recovery/receipt inspection missing")

    if (
        recovery.get("success") is not True
        or recovery.get("recovery_id") != recovery_id
        or recovery.get("action") != "move_draft"
        or recovery.get("manifest_state") != "committed"
        or recovery.get("classification") != "committed"
        or recovery.get("recovery_required") is not False
        or recovery.get("backup_sha256") != EXPECTED_SOURCE_SHA256
        or recovery.get("source_sha256") is not None
        or recovery.get("target_sha256") != EXPECTED_SOURCE_SHA256
        or recovery.get("approved_source_sha256") != EXPECTED_SOURCE_SHA256
        or recovery.get("source_draft") != SOURCE_RELATIVE_PATH
        or recovery.get("target_relative_path") != TARGET_RELATIVE_PATH
    ):
        raise RuntimeError("new committed P5-02T move recovery inspection mismatch")

    if (
        receipt.get("success") is not True
        or receipt.get("correlation_valid") is not True
        or receipt.get("authorization_reusable") is not False
        or receipt.get("recovery_required") is not False
        or receipt.get("recovery_id") != recovery_id
        or receipt.get("plan_token") != recovery_id
        or receipt.get("action") != "move_draft"
        or receipt.get("receipt_state") != "committed"
        or receipt.get("receipt_finalized") is not True
        or receipt.get("receipt_reconciliation_required") is not False
        or receipt.get("final_classification") != "committed"
        or receipt.get("current_classification") != "committed"
        or receipt.get("approval_surface") != "cli"
        or receipt.get("approval_choice") != "once"
        or receipt.get("backup_sha256") != EXPECTED_SOURCE_SHA256
    ):
        raise RuntimeError("new committed P5-02T move receipt inspection mismatch")

    recovery_names = sorted(
        item.name for item in expected_recovery_dir.iterdir()
    )
    if recovery_names != ["manifest.json", "receipt.json", "source.bin"]:
        raise RuntimeError(
            "P5-02T move recovery directory entries mismatch: "
            + repr(recovery_names)
        )

    print("P5_02T_PRODUCTION_MOVE=PASS")
    print("P5_02T_APPLY_SUCCESS=true")
    print("P5_02T_MUTATION_PERFORMED=true")
    print("P5_02T_RECOVERY_REQUIRED=false")
    print(f"P5_02T_RECOVERY_ID={recovery_id}")
    print(f"P5_02T_RECOVERY_DIR={expected_recovery_dir}")
    print("P5_02T_MOVE_RECOVERY_RECORD_VALID=true")
    print("P5_02T_MOVE_RECOVERY_MANIFEST_STATE=committed")
    print("P5_02T_MOVE_RECOVERY_CLASSIFICATION=committed")
    print("P5_02T_RECEIPT_STATE=committed")
    print("P5_02T_RECEIPT_FINALIZED=true")
    print("P5_02T_RECEIPT_RECONCILIATION_REQUIRED=false")
    print("P5_02T_APPROVAL_SURFACE=cli")
    print("P5_02T_APPROVAL_CHOICE=once")
    print("P5_02T_AUTHORIZATION_REUSABLE=false")
    print("P5_02T_SOURCE_STATE_AFTER=absent")
    print("P5_02T_TARGET_STATE_AFTER=present")
    print(f"P5_02T_TARGET_SHA256={EXPECTED_SOURCE_SHA256}")
    print("P5_02T_PRODUCTION_RECOVERY_COUNT_AFTER=3")
    print("P5_02T_PRODUCTION_RECOVERY_ATTENTION_AFTER=0")
    print("P5_02T_MUTATION_MODE_AFTER=disabled")
    print("P5_02T_AUTOMATIC_RESTORE=false")
    print("P5_02T_AUTOMATIC_TARGET_DELETE=false")
    print("P5_02T_RECOVERY_EVIDENCE_PRESERVED=true")
    print("HERMES_MANUAL_OFF=true")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02T_PRODUCTION_MOVE=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
