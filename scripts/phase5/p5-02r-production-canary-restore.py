#!/usr/bin/env python3
"""P5-02R production canary restore qualification.

Restores the exact P5-02Q canary edit from its committed recovery record.

The restore preview is built by the qualified private read-only production
restore-preview helper. The mutation itself is dispatched only through the
registered guarded public apply tool and requires a fresh Hermes human ONCE.

No automatic follow-up mutation is attempted on failure.
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

ORIGIN_RECOVERY_ID = (
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f"
)
TARGET_RELATIVE_PATH = "_Orion-P5-Canary.md"
EXPECTED_CANONICAL_PATH = Path(r"C:\Personal\Me\_Orion-P5-Canary.md")

# P5-02Q accepted post-state. This is the object that P5-02R is authorized to
# restore, and therefore its file identity is a pre-restore race/stale guard.
EXPECTED_PRE_RESTORE_FILE_ID = (
    "5e1aeb8a1aeb5d91:19c10700000020000000000000000000"
)

BEFORE_RESTORE_BYTES = (
    b"# Orion Phase 5 Canary\n"
    b"state: after\n"
    b"gate: first-production-edit\n"
)
RESTORED_BYTES = (
    b"# Orion Phase 5 Canary\n"
    b"state: before\n"
    b"gate: first-production-edit\n"
)

EXPECTED_CURRENT_SHA256 = (
    "86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19"
)
EXPECTED_RESTORE_SHA256 = (
    "ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c"
)
EXPECTED_RESTORE_DIFF_SHA256 = (
    "3963b73cb038a92f67fb7d81c7d3443dace68ebd238bbdbd73ce04197d9d8ba8"
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
    result: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("recovery inventory contains non-object record")
        rid = record.get("recovery_id")
        if not isinstance(rid, str):
            raise RuntimeError("recovery inventory record id missing")
        if rid in result:
            raise RuntimeError("duplicate recovery id in inventory")
        result[rid] = record
    return result


def emit_failure_state(plugin, target: Path, recovery_root: Path, result: dict) -> None:
    print("P5_02R_APPLY_SUCCESS=false")
    print(f"P5_02R_APPLY_ERROR={result.get('error')}")
    print(
        "P5_02R_APPLY_MUTATION_PERFORMED="
        f"{str(bool(result.get('mutation_performed'))).lower()}"
    )
    print(
        "P5_02R_APPLY_RECOVERY_REQUIRED="
        f"{str(bool(result.get('recovery_required'))).lower()}"
    )
    if isinstance(result.get("recovery_id"), str):
        print(f"P5_02R_NEW_RECOVERY_ID={result['recovery_id']}")
    if target.is_file():
        try:
            print(f"P5_02R_POST_FAILURE_TARGET_SHA256={sha256(target.read_bytes())}")
            print(
                "P5_02R_POST_FAILURE_TARGET_FILE_ID="
                f"{plugin._windows_path_file_identity(target)}"
            )
        except Exception as exc:
            print(f"P5_02R_POST_FAILURE_TARGET_INSPECTION_ERROR={type(exc).__name__}")
    try:
        inventory = plugin._enumerate_production_recovery_records()
        print(
            "P5_02R_POST_FAILURE_RECOVERY_ENUM_SUCCESS="
            f"{str(bool(inventory.get('success'))).lower()}"
        )
        if inventory.get("success"):
            print(
                "P5_02R_POST_FAILURE_RECOVERY_COUNT="
                f"{inventory.get('record_count')}"
            )
            print(
                "P5_02R_POST_FAILURE_RECOVERY_ATTENTION="
                f"{inventory.get('attention_count')}"
            )
            print(
                "P5_02R_POST_FAILURE_RECOVERY_TRUNCATED="
                f"{str(bool(inventory.get('truncated'))).lower()}"
            )
    except Exception as exc:
        print(f"P5_02R_POST_FAILURE_RECOVERY_ENUM_ERROR={type(exc).__name__}")
    print(f"P5_02R_RECOVERY_ROOT={recovery_root}")
    print("P5_02R_AUTOMATIC_FOLLOWUP_MUTATION=false")
    print("P5_02R_RECOVERY_EVIDENCE_PRESERVED=true")


def require_origin_record_before(record: dict) -> None:
    if record.get("valid") is not True or record.get("needs_attention") is not False:
        raise RuntimeError("origin recovery record is not valid/clean before restore")

    recovery = record.get("recovery")
    receipt = record.get("receipt")
    if not isinstance(recovery, dict) or not isinstance(receipt, dict):
        raise RuntimeError("origin recovery/receipt inspection missing")

    if (
        recovery.get("success") is not True
        or recovery.get("recovery_id") != ORIGIN_RECOVERY_ID
        or recovery.get("action") != "edit_note"
        or recovery.get("manifest_state") != "committed"
        or recovery.get("classification") != "committed"
        or recovery.get("recovery_required") is not False
        or recovery.get("backup_sha256") != EXPECTED_RESTORE_SHA256
        or recovery.get("target_sha256") != EXPECTED_CURRENT_SHA256
        or recovery.get("before_sha256") != EXPECTED_RESTORE_SHA256
        or recovery.get("after_sha256") != EXPECTED_CURRENT_SHA256
        or recovery.get("target_relative_path") != TARGET_RELATIVE_PATH
    ):
        raise RuntimeError("origin recovery record does not match frozen P5-02Q state")

    if (
        receipt.get("success") is not True
        or receipt.get("correlation_valid") is not True
        or receipt.get("authorization_reusable") is not False
        or receipt.get("recovery_required") is not False
        or receipt.get("receipt_state") != "committed"
        or receipt.get("receipt_finalized") is not True
        or receipt.get("receipt_reconciliation_required") is not False
        or receipt.get("final_classification") != "committed"
        or receipt.get("current_classification") != "committed"
        or receipt.get("approval_choice") != "once"
        or receipt.get("backup_sha256") != EXPECTED_RESTORE_SHA256
    ):
        raise RuntimeError("origin receipt does not match frozen P5-02Q state")


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
            raise RuntimeError(f"ambient Phase 5 setting unexpectedly present: {name}")

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
    if profile / ".env" not in [Path(p).resolve() for p in loaded]:
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
    if apply_entry is None:
        raise RuntimeError("installed Orion apply tool was not discovered")
    if apply_entry.handler.__name__ != "apply_plan_production_guarded":
        raise RuntimeError("registered apply handler identity mismatch")

    expected_plugin_file = (plugin_dir / "__init__.py").resolve(strict=True)
    plugin = sys.modules.get(apply_entry.handler.__module__)
    if plugin is None:
        raise RuntimeError("installed Orion plugin module unavailable")

    plugin_file = Path(getattr(plugin, "__file__", "")).resolve(strict=True)
    if plugin_file != expected_plugin_file:
        raise RuntimeError(
            "registered apply handler was not loaded from the verified installed plugin"
        )
    if apply_entry.handler is not plugin.apply_plan_production_guarded:
        raise RuntimeError("registered apply handler object mismatch")
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
        raise RuntimeError(f"unexpected pre-restore production mode: {mode}")

    roots = plugin._validate_production_roots()
    if roots.get("success") is not True:
        raise RuntimeError("native production root validation failed before restore")
    if roots.get("mutation_allowed") is not False:
        raise RuntimeError("native validator unexpectedly allows mutation")

    vault_root = Path(roots["vault_root"]).resolve(strict=True)
    recovery_root = Path(roots["recovery_root"]).resolve(strict=True)
    if recovery_root != expected_recovery_root:
        raise RuntimeError("native recovery root mismatch")

    inventory_before = plugin._enumerate_production_recovery_records()
    if (
        inventory_before.get("success") is not True
        or inventory_before.get("record_count") != 1
        or inventory_before.get("attention_count") != 0
        or inventory_before.get("truncated") is not False
    ):
        raise RuntimeError("production recovery inventory is not the accepted P5-02Q state")

    records_before = index_records(inventory_before)
    if set(records_before) != {ORIGIN_RECOVERY_ID}:
        raise RuntimeError("unexpected production recovery id before restore")
    require_origin_record_before(records_before[ORIGIN_RECOVERY_ID])

    target = vault_root / TARGET_RELATIVE_PATH
    if not target.is_file():
        raise RuntimeError("production canary is missing")
    canonical_target = target.resolve(strict=True)
    if canonical_target != EXPECTED_CANONICAL_PATH:
        raise RuntimeError("production canary canonical path mismatch")
    if plugin._path_has_reparse_component(target):
        raise RuntimeError("production canary has reparse component")

    current_bytes = target.read_bytes()
    if current_bytes != BEFORE_RESTORE_BYTES:
        raise RuntimeError("production canary bytes differ from accepted P5-02Q post-state")
    if sha256(current_bytes) != EXPECTED_CURRENT_SHA256:
        raise RuntimeError("production canary current SHA-256 mismatch")
    current_file_id = plugin._windows_path_file_identity(target)
    if current_file_id != EXPECTED_PRE_RESTORE_FILE_ID:
        raise RuntimeError("production canary pre-restore file identity mismatch")

    preview = plugin._preview_production_restore_candidate(ORIGIN_RECOVERY_ID)
    if preview.get("success") is not True or preview.get("mutation_performed") is not False:
        raise RuntimeError(
            "production restore preview failed: " + json.dumps(preview, sort_keys=True)
        )

    plan = preview.get("plan")
    diff_text = preview.get("diff")
    if not isinstance(plan, dict) or not isinstance(diff_text, str):
        raise RuntimeError("production restore preview contract missing plan/diff")
    if preview.get("restore_kind") != "historical_edit":
        raise RuntimeError("production restore kind mismatch")
    if preview.get("changed") is not True:
        raise RuntimeError("production restore preview unexpectedly reports no change")

    if plan.get("action") != "restore_edit":
        raise RuntimeError("production restore action mismatch")
    if plan.get("recovery_id") != ORIGIN_RECOVERY_ID:
        raise RuntimeError("production restore origin recovery id mismatch")
    if plan.get("recovery_action") != "edit_note":
        raise RuntimeError("production restore origin action mismatch")
    if plan.get("recovery_manifest_state") != "committed":
        raise RuntimeError("production restore origin manifest state mismatch")
    if plan.get("target_relative_path") != TARGET_RELATIVE_PATH:
        raise RuntimeError("production restore relative target mismatch")
    if plan.get("target_canonical_path") != str(EXPECTED_CANONICAL_PATH):
        raise RuntimeError("production restore canonical target mismatch")
    if plan.get("target_file_id") != EXPECTED_PRE_RESTORE_FILE_ID:
        raise RuntimeError("production restore preview file identity mismatch")
    if plan.get("current_sha256") != EXPECTED_CURRENT_SHA256:
        raise RuntimeError("production restore current hash mismatch")
    if plan.get("restore_sha256") != EXPECTED_RESTORE_SHA256:
        raise RuntimeError("production restore target hash mismatch")
    if plan.get("recovery_backup_sha256") != EXPECTED_RESTORE_SHA256:
        raise RuntimeError("production restore backup hash mismatch")
    if plan.get("diff_sha256") != EXPECTED_RESTORE_DIFF_SHA256:
        raise RuntimeError("production restore diff hash mismatch")
    if sha256(diff_text.encode("utf-8")) != EXPECTED_RESTORE_DIFF_SHA256:
        raise RuntimeError("production restore exact diff differs from frozen contract")

    if target.read_bytes() != BEFORE_RESTORE_BYTES:
        raise RuntimeError("production canary changed during restore preview")
    if plugin._windows_path_file_identity(target) != EXPECTED_PRE_RESTORE_FILE_ID:
        raise RuntimeError("production canary identity changed during restore preview")

    plan_token = preview.get("plan_token")
    if not isinstance(plan_token, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_token):
        raise RuntimeError("production restore plan token invalid")
    if plan_token == ORIGIN_RECOVERY_ID:
        raise RuntimeError("restore plan token unexpectedly equals origin recovery id")

    print("P5_02R_RESTORE_PREVIEW_CONTRACT=PASS")
    print(f"P5_02R_ORIGIN_RECOVERY_ID={ORIGIN_RECOVERY_ID}")
    print(f"P5_02R_RESTORE_PLAN_TOKEN={plan_token}")
    print(f"P5_02R_CANARY_PRE_RESTORE_FILE_ID={EXPECTED_PRE_RESTORE_FILE_ID}")
    print(f"P5_02R_CURRENT_SHA256={EXPECTED_CURRENT_SHA256}")
    print(f"P5_02R_RESTORE_SHA256={EXPECTED_RESTORE_SHA256}")
    print(f"P5_02R_RESTORE_DIFF_SHA256={EXPECTED_RESTORE_DIFF_SHA256}")
    print("P5_02R_MUTATION_MODE_PERSISTED=false")
    print("P5_02R_PRODUCTION_RECOVERY_COUNT_BEFORE=1")
    print("P5_02R_PRODUCTION_RECOVERY_ATTENTION_BEFORE=0")
    print("P5_02R_EXACT_DIFF_BEGIN")
    print(diff_text, end="" if diff_text.endswith("\n") else "\n")
    print("P5_02R_EXACT_DIFF_END")
    print("")
    print("P5_02R_APPROVAL_PROMPT_EXPECTED=true")
    print("P5_02R_CHOOSE_ONCE_ONLY=true", flush=True)

    interactive_token = None
    raw_apply = None
    try:
        interactive_token = set_hermes_interactive_context(True)
        os.environ["ORION_P5_MUTATION_MODE"] = "mutation_enabled"

        enabled_mode = plugin._production_mutation_mode()
        if (
            enabled_mode.get("valid") is not True
            or enabled_mode.get("mode") != plugin.PRODUCTION_MODE_MUTATION_ENABLED
            or enabled_mode.get("mutation_allowed") is not True
        ):
            raise RuntimeError("process-scoped mutation mode did not enable correctly")

        raw_apply = handle_function_call(
            APPLY_TOOL,
            {"plan_token": plan_token},
            task_id="p5-02r-canary-restore",
            session_id="p5-02r-canary-restore",
            tool_call_id="p5-02r-canary-restore-call",
            turn_id="p5-02r-canary-restore-turn",
            user_task="P5-02R exact production canary restore",
            enabled_tools=[APPLY_TOOL],
            enabled_toolsets=["orion_vault"],
        )
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
        raise RuntimeError("production mutation mode did not return to disabled")

    result = parse_json_result(raw_apply, label="restore apply")
    if (
        result.get("success") is not True
        or result.get("mutation_performed") is not True
        or result.get("recovery_required") is not False
    ):
        emit_failure_state(plugin, target, recovery_root, result)
        raise RuntimeError("P5-02R production restore did not complete cleanly")

    if result.get("action") != "restore_edit":
        raise RuntimeError("P5-02R result action mismatch")
    if result.get("origin_recovery_id") != ORIGIN_RECOVERY_ID:
        raise RuntimeError("P5-02R result origin recovery id mismatch")

    new_recovery_id = result.get("recovery_id")
    if not isinstance(new_recovery_id, str) or not re.fullmatch(
        r"[0-9a-f]{64}", new_recovery_id
    ):
        raise RuntimeError("P5-02R new recovery id invalid")
    if new_recovery_id != plan_token:
        raise RuntimeError("P5-02R new recovery id does not equal restore plan token")
    if new_recovery_id == ORIGIN_RECOVERY_ID:
        raise RuntimeError("P5-02R new recovery id collided with origin record")

    expected_new_dir = recovery_root / new_recovery_id
    result_recovery_dir = result.get("recovery_dir")
    if not isinstance(result_recovery_dir, str):
        raise RuntimeError("P5-02R result recovery directory missing")
    if Path(result_recovery_dir).resolve(strict=True) != expected_new_dir.resolve(strict=True):
        raise RuntimeError("P5-02R result recovery directory mismatch")

    restored_actual = target.read_bytes()
    if restored_actual != RESTORED_BYTES:
        raise RuntimeError("P5-02R target bytes do not equal frozen restored bytes")
    if sha256(restored_actual) != EXPECTED_RESTORE_SHA256:
        raise RuntimeError("P5-02R target restored SHA-256 mismatch")
    if plugin._path_has_reparse_component(target):
        raise RuntimeError("P5-02R target became a reparse path")
    post_restore_file_id = plugin._windows_path_file_identity(target)

    inventory_after = plugin._enumerate_production_recovery_records()
    if (
        inventory_after.get("success") is not True
        or inventory_after.get("record_count") != 2
        or inventory_after.get("attention_count") != 0
        or inventory_after.get("truncated") is not False
    ):
        raise RuntimeError(
            "P5-02R post-restore recovery inventory is not two clean records"
        )

    records_after = index_records(inventory_after)
    if set(records_after) != {ORIGIN_RECOVERY_ID, new_recovery_id}:
        raise RuntimeError("P5-02R recovery id set mismatch after restore")

    origin_record = records_after[ORIGIN_RECOVERY_ID]
    if origin_record.get("valid") is not True or origin_record.get("needs_attention") is not False:
        raise RuntimeError("origin record became invalid/attention after restore")
    origin_recovery = origin_record.get("recovery")
    origin_receipt = origin_record.get("receipt")
    if not isinstance(origin_recovery, dict) or not isinstance(origin_receipt, dict):
        raise RuntimeError("origin record inspection missing after restore")
    if (
        origin_recovery.get("manifest_state") != "committed"
        or origin_recovery.get("classification") != "committed_then_changed"
        or origin_recovery.get("recovery_required") is not False
        or origin_recovery.get("target_sha256") != EXPECTED_RESTORE_SHA256
        or origin_receipt.get("receipt_state") != "committed"
        or origin_receipt.get("receipt_finalized") is not True
        or origin_receipt.get("receipt_reconciliation_required") is not False
        or origin_receipt.get("current_classification") != "committed_then_changed"
    ):
        raise RuntimeError("origin P5-02Q record has unexpected post-restore classification")

    restore_record = records_after[new_recovery_id]
    if restore_record.get("valid") is not True or restore_record.get("needs_attention") is not False:
        raise RuntimeError("new restore record is not valid/clean")
    recovery = restore_record.get("recovery")
    receipt = restore_record.get("receipt")
    if not isinstance(recovery, dict) or not isinstance(receipt, dict):
        raise RuntimeError("new restore recovery/receipt inspection missing")

    if (
        recovery.get("success") is not True
        or recovery.get("recovery_id") != new_recovery_id
        or recovery.get("origin_recovery_id") != ORIGIN_RECOVERY_ID
        or recovery.get("action") != "restore_edit"
        or recovery.get("manifest_state") != "committed"
        or recovery.get("classification") != "committed"
        or recovery.get("recovery_required") is not False
        or recovery.get("backup_sha256") != EXPECTED_CURRENT_SHA256
        or recovery.get("target_sha256") != EXPECTED_RESTORE_SHA256
        or recovery.get("before_sha256") != EXPECTED_CURRENT_SHA256
        or recovery.get("after_sha256") != EXPECTED_RESTORE_SHA256
        or recovery.get("target_relative_path") != TARGET_RELATIVE_PATH
    ):
        raise RuntimeError("new committed restore recovery inspection mismatch")

    if (
        receipt.get("success") is not True
        or receipt.get("correlation_valid") is not True
        or receipt.get("authorization_reusable") is not False
        or receipt.get("recovery_required") is not False
        or receipt.get("recovery_id") != new_recovery_id
        or receipt.get("plan_token") != new_recovery_id
        or receipt.get("action") != "restore_edit"
        or receipt.get("receipt_state") != "committed"
        or receipt.get("receipt_finalized") is not True
        or receipt.get("receipt_reconciliation_required") is not False
        or receipt.get("final_classification") != "committed"
        or receipt.get("current_classification") != "committed"
        or receipt.get("approval_surface") != "cli"
        or receipt.get("approval_choice") != "once"
        or receipt.get("backup_sha256") != EXPECTED_CURRENT_SHA256
    ):
        raise RuntimeError("new committed restore receipt inspection mismatch")

    recovery_names = sorted(p.name for p in expected_new_dir.iterdir())
    if recovery_names != ["before_restore.bin", "manifest.json", "receipt.json"]:
        raise RuntimeError(
            "P5-02R restore recovery directory entries mismatch: "
            + repr(recovery_names)
        )

    print("P5_02R_PRODUCTION_CANARY_RESTORE=PASS")
    print("P5_02R_APPLY_SUCCESS=true")
    print("P5_02R_MUTATION_PERFORMED=true")
    print("P5_02R_RECOVERY_REQUIRED=false")
    print(f"P5_02R_ORIGIN_RECOVERY_ID={ORIGIN_RECOVERY_ID}")
    print(f"P5_02R_NEW_RECOVERY_ID={new_recovery_id}")
    print(f"P5_02R_NEW_RECOVERY_DIR={expected_new_dir}")
    print("P5_02R_NEW_RECOVERY_RECORD_VALID=true")
    print("P5_02R_NEW_RECOVERY_MANIFEST_STATE=committed")
    print("P5_02R_NEW_RECOVERY_CLASSIFICATION=committed")
    print("P5_02R_NEW_RECEIPT_STATE=committed")
    print("P5_02R_NEW_RECEIPT_FINALIZED=true")
    print("P5_02R_NEW_RECEIPT_RECONCILIATION_REQUIRED=false")
    print("P5_02R_APPROVAL_SURFACE=cli")
    print("P5_02R_APPROVAL_CHOICE=once")
    print("P5_02R_AUTHORIZATION_REUSABLE=false")
    print("P5_02R_ORIGIN_CLASSIFICATION=committed_then_changed")
    print("P5_02R_ORIGIN_NEEDS_ATTENTION=false")
    print("P5_02R_PRODUCTION_RECOVERY_COUNT_AFTER=2")
    print("P5_02R_PRODUCTION_RECOVERY_ATTENTION_AFTER=0")
    print(f"P5_02R_CANARY_POST_RESTORE_FILE_ID={post_restore_file_id}")
    print(f"P5_02R_CANARY_POST_RESTORE_SHA256={EXPECTED_RESTORE_SHA256}")
    print("P5_02R_MUTATION_MODE_AFTER=disabled")
    print("P5_02R_AUTOMATIC_FOLLOWUP_MUTATION=false")
    print("P5_02R_RECOVERY_EVIDENCE_PRESERVED=true")
    print("HERMES_MANUAL_OFF=true")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02R_PRODUCTION_CANARY_RESTORE=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
