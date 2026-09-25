#!/usr/bin/env python3
"""P5-02U production move-source restore gate.

Restores only the removed inbox source from the accepted P5-02T committed
move recovery record. The existing vault target is reference evidence and must
remain present and byte-identical before and after the restore.

The restore preview is built by the qualified private read-only production
restore-preview helper. The mutation itself is dispatched only through the
registered guarded public apply tool and requires a fresh Hermes human ONCE.

No automatic target deletion, recovery cleanup, or follow-up mutation occurs.
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

EDIT_RECOVERY_ID = (
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f"
)
EDIT_RESTORE_RECOVERY_ID = (
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27"
)
MOVE_RECOVERY_ID = (
    "8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6"
)

SOURCE_RELATIVE_PATH = "_Orion-P5-Move-Canary.md"
TARGET_RELATIVE_PATH = "_Orion-P5-Move-Canary.md"
EXPECTED_SOURCE_PATH = Path(
    r"C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md"
)
EXPECTED_TARGET_PATH = Path(
    r"C:\Personal\Me\_Orion-P5-Move-Canary.md"
)
EXPECTED_INBOX_ROOT = Path(r"C:\Personal\Orion-Inbox")
EXPECTED_VAULT_ROOT = Path(r"C:\Personal\Me")

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
EXPECTED_SHA256 = (
    "132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132"
)
EXPECTED_RESTORE_DIFF_SHA256 = (
    "5129b0fd7837d9207c4a05d3be365d9939c6a0c39c4fba48369487d6a2761bd2"
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


def require_edit_record(record: dict) -> None:
    if record.get("valid") is not True or record.get("needs_attention") is not False:
        raise RuntimeError("P5-02Q edit record invalid/attention")
    recovery = record.get("recovery")
    receipt = record.get("receipt")
    if not isinstance(recovery, dict) or not isinstance(receipt, dict):
        raise RuntimeError("P5-02Q edit recovery/receipt inspection missing")
    if (
        recovery.get("manifest_state") != "committed"
        or recovery.get("classification") != "committed_then_changed"
        or recovery.get("recovery_required") is not False
        or receipt.get("receipt_state") != "committed"
        or receipt.get("receipt_finalized") is not True
        or receipt.get("receipt_reconciliation_required") is not False
        or receipt.get("current_classification") != "committed_then_changed"
    ):
        raise RuntimeError("P5-02Q edit record differs from accepted state")


def require_edit_restore_record(record: dict) -> None:
    if record.get("valid") is not True or record.get("needs_attention") is not False:
        raise RuntimeError("P5-02R restore record invalid/attention")
    recovery = record.get("recovery")
    receipt = record.get("receipt")
    if not isinstance(recovery, dict) or not isinstance(receipt, dict):
        raise RuntimeError("P5-02R restore recovery/receipt inspection missing")
    if (
        recovery.get("manifest_state") != "committed"
        or recovery.get("classification") != "committed"
        or recovery.get("recovery_required") is not False
        or receipt.get("receipt_state") != "committed"
        or receipt.get("receipt_finalized") is not True
        or receipt.get("receipt_reconciliation_required") is not False
        or receipt.get("current_classification") != "committed"
    ):
        raise RuntimeError("P5-02R restore record differs from accepted state")


def require_move_record_before(record: dict) -> None:
    if record.get("valid") is not True or record.get("needs_attention") is not False:
        raise RuntimeError("P5-02T move record invalid/attention before restore")
    recovery = record.get("recovery")
    receipt = record.get("receipt")
    if not isinstance(recovery, dict) or not isinstance(receipt, dict):
        raise RuntimeError("P5-02T move recovery/receipt inspection missing")

    if (
        recovery.get("success") is not True
        or recovery.get("recovery_id") != MOVE_RECOVERY_ID
        or recovery.get("action") != "move_draft"
        or recovery.get("manifest_state") != "committed"
        or recovery.get("classification") != "committed"
        or recovery.get("recovery_required") is not False
        or recovery.get("backup_sha256") != EXPECTED_SHA256
        or recovery.get("source_sha256") is not None
        or recovery.get("target_sha256") != EXPECTED_SHA256
        or recovery.get("approved_source_sha256") != EXPECTED_SHA256
        or recovery.get("source_draft") != SOURCE_RELATIVE_PATH
        or recovery.get("target_relative_path") != TARGET_RELATIVE_PATH
    ):
        raise RuntimeError("P5-02T move recovery differs from accepted state")

    if (
        receipt.get("success") is not True
        or receipt.get("correlation_valid") is not True
        or receipt.get("authorization_reusable") is not False
        or receipt.get("recovery_required") is not False
        or receipt.get("recovery_id") != MOVE_RECOVERY_ID
        or receipt.get("plan_token") != MOVE_RECOVERY_ID
        or receipt.get("action") != "move_draft"
        or receipt.get("receipt_state") != "committed"
        or receipt.get("receipt_finalized") is not True
        or receipt.get("receipt_reconciliation_required") is not False
        or receipt.get("final_classification") != "committed"
        or receipt.get("current_classification") != "committed"
        or receipt.get("approval_surface") != "cli"
        or receipt.get("approval_choice") != "once"
        or receipt.get("backup_sha256") != EXPECTED_SHA256
    ):
        raise RuntimeError("P5-02T move receipt differs from accepted state")


def require_pre_restore_inventory(records: dict[str, dict]) -> None:
    expected = {
        EDIT_RECOVERY_ID,
        EDIT_RESTORE_RECOVERY_ID,
        MOVE_RECOVERY_ID,
    }
    if set(records) != expected:
        raise RuntimeError("pre-restore recovery id set differs from P5-02T state")
    require_edit_record(records[EDIT_RECOVERY_ID])
    require_edit_restore_record(records[EDIT_RESTORE_RECOVERY_ID])
    require_move_record_before(records[MOVE_RECOVERY_ID])


def emit_failure_state(
    plugin,
    source: Path,
    target: Path,
    recovery_root: Path,
    result: dict | None = None,
) -> None:
    if isinstance(result, dict):
        print(f"P5_02U_APPLY_ERROR={result.get('error')}")
        print(
            "P5_02U_APPLY_MUTATION_PERFORMED="
            f"{str(bool(result.get('mutation_performed'))).lower()}"
        )
        print(
            "P5_02U_APPLY_RECOVERY_REQUIRED="
            f"{str(bool(result.get('recovery_required'))).lower()}"
        )
        if isinstance(result.get("recovery_id"), str):
            print(f"P5_02U_NEW_RECOVERY_ID={result['recovery_id']}")

    try:
        if os.path.lexists(source):
            print("P5_02U_POST_FAILURE_SOURCE_STATE=present")
            if source.is_file():
                print(
                    "P5_02U_POST_FAILURE_SOURCE_SHA256="
                    f"{sha256(source.read_bytes())}"
                )
        else:
            print("P5_02U_POST_FAILURE_SOURCE_STATE=absent")
    except Exception as exc:
        print(
            "P5_02U_POST_FAILURE_SOURCE_INSPECTION_ERROR="
            f"{type(exc).__name__}"
        )

    try:
        if target.is_file():
            print("P5_02U_POST_FAILURE_TARGET_STATE=present")
            print(
                "P5_02U_POST_FAILURE_TARGET_SHA256="
                f"{sha256(target.read_bytes())}"
            )
        elif os.path.lexists(target):
            print("P5_02U_POST_FAILURE_TARGET_STATE=non_file")
        else:
            print("P5_02U_POST_FAILURE_TARGET_STATE=absent")
    except Exception as exc:
        print(
            "P5_02U_POST_FAILURE_TARGET_INSPECTION_ERROR="
            f"{type(exc).__name__}"
        )

    try:
        inventory = plugin._enumerate_production_recovery_records()
        print(
            "P5_02U_POST_FAILURE_RECOVERY_ENUM_SUCCESS="
            f"{str(bool(inventory.get('success'))).lower()}"
        )
        if inventory.get("success"):
            print(
                "P5_02U_POST_FAILURE_RECOVERY_COUNT="
                f"{inventory.get('record_count')}"
            )
            print(
                "P5_02U_POST_FAILURE_RECOVERY_ATTENTION="
                f"{inventory.get('attention_count')}"
            )
            print(
                "P5_02U_POST_FAILURE_RECOVERY_TRUNCATED="
                f"{str(bool(inventory.get('truncated'))).lower()}"
            )
    except Exception as exc:
        print(
            "P5_02U_POST_FAILURE_RECOVERY_ENUM_ERROR="
            f"{type(exc).__name__}"
        )

    print(f"P5_02U_RECOVERY_ROOT={recovery_root}")
    print("P5_02U_AUTOMATIC_TARGET_DELETE=false")
    print("P5_02U_AUTOMATIC_RECOVERY_CLEANUP=false")
    print("P5_02U_AUTOMATIC_FOLLOWUP_MUTATION=false")
    print("P5_02U_RECOVERY_EVIDENCE_PRESERVED=true")


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
            "registered apply handler was not loaded from verified installed plugin"
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
        raise RuntimeError("native production-root validation failed before restore")
    if roots.get("mutation_allowed") is not False:
        raise RuntimeError("native validator unexpectedly allows mutation")

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
        or inventory_before.get("record_count") != 3
        or inventory_before.get("attention_count") != 0
        or inventory_before.get("truncated") is not False
    ):
        raise RuntimeError(
            "production recovery inventory differs from accepted P5-02T state"
        )
    records_before = index_records(inventory_before)
    require_pre_restore_inventory(records_before)

    source = inbox_root / SOURCE_RELATIVE_PATH
    target = vault_root / TARGET_RELATIVE_PATH

    if os.path.lexists(source):
        raise RuntimeError("move source is no longer absent before restore")
    if source.resolve(strict=False) != EXPECTED_SOURCE_PATH:
        raise RuntimeError("move source canonical candidate mismatch")
    if not source.parent.is_dir():
        raise RuntimeError("move source parent is missing")
    if source.parent.resolve(strict=True) != EXPECTED_INBOX_ROOT:
        raise RuntimeError("move source parent canonical path mismatch")
    if plugin._path_has_reparse_component(source.parent):
        raise RuntimeError("move source parent has a reparse component")

    if not target.is_file():
        raise RuntimeError("P5-02T vault target is missing before restore")
    if target.resolve(strict=True) != EXPECTED_TARGET_PATH:
        raise RuntimeError("P5-02T vault target canonical path mismatch")
    if plugin._path_has_reparse_component(target):
        raise RuntimeError("P5-02T vault target has a reparse component")
    target_bytes_before = target.read_bytes()
    if target_bytes_before != SOURCE_BYTES:
        raise RuntimeError("P5-02T vault target bytes differ from frozen source bytes")
    if sha256(target_bytes_before) != EXPECTED_SHA256:
        raise RuntimeError("P5-02T vault target SHA-256 mismatch")

    preview = plugin._preview_production_restore_candidate(MOVE_RECOVERY_ID)
    if (
        preview.get("success") is not True
        or preview.get("mutation_performed") is not False
    ):
        raise RuntimeError(
            "production move-source restore preview failed: "
            + json.dumps(preview, sort_keys=True)
        )
    if preview.get("restore_kind") != "historical_move_source":
        raise RuntimeError("production restore kind mismatch")
    if preview.get("changed") is not True:
        raise RuntimeError("move-source restore preview unexpectedly reports no change")

    plan = preview.get("plan")
    diff_text = preview.get("diff")
    if not isinstance(plan, dict) or not isinstance(diff_text, str):
        raise RuntimeError("move-source restore preview contract missing plan/diff")

    if plan.get("action") != "restore_move_source":
        raise RuntimeError("move-source restore action mismatch")
    if plan.get("recovery_id") != MOVE_RECOVERY_ID:
        raise RuntimeError("move-source restore origin recovery id mismatch")
    if plan.get("recovery_action") != "move_draft":
        raise RuntimeError("move-source restore origin action mismatch")
    if plan.get("recovery_manifest_state") != "committed":
        raise RuntimeError("move-source restore origin manifest state mismatch")
    if plan.get("source_draft") != SOURCE_RELATIVE_PATH:
        raise RuntimeError("move-source restore source relative path mismatch")
    if plan.get("source_state") != "absent":
        raise RuntimeError("move-source restore source state mismatch")
    if plan.get("target_relative_path") != SOURCE_RELATIVE_PATH:
        raise RuntimeError("move-source restore target-relative field mismatch")
    if plan.get("target_canonical_path") != str(EXPECTED_SOURCE_PATH):
        raise RuntimeError("move-source restore source canonical path mismatch")
    if plan.get("source_parent_canonical_path") != str(EXPECTED_INBOX_ROOT):
        raise RuntimeError("move-source restore parent canonical path mismatch")
    if plan.get("restore_sha256") != EXPECTED_SHA256:
        raise RuntimeError("move-source restore SHA-256 mismatch")
    if plan.get("recovery_backup_sha256") != EXPECTED_SHA256:
        raise RuntimeError("move-source restore backup SHA-256 mismatch")
    if plan.get("reference_target_relative_path") != TARGET_RELATIVE_PATH:
        raise RuntimeError("move-source restore reference target relative mismatch")
    if plan.get("reference_target_canonical_path") != str(EXPECTED_TARGET_PATH):
        raise RuntimeError("move-source restore reference target canonical mismatch")
    if plan.get("reference_target_state") != "present":
        raise RuntimeError("move-source restore reference target is not present")
    if plan.get("reference_target_sha256") != EXPECTED_SHA256:
        raise RuntimeError("move-source restore reference target SHA-256 mismatch")
    if plan.get("diff_sha256") != EXPECTED_RESTORE_DIFF_SHA256:
        raise RuntimeError("move-source restore diff hash mismatch")
    if sha256(diff_text.encode("utf-8")) != EXPECTED_RESTORE_DIFF_SHA256:
        raise RuntimeError("move-source restore exact diff differs from frozen contract")

    if os.path.lexists(source):
        raise RuntimeError("move source appeared during restore preview")
    if not target.is_file() or target.read_bytes() != SOURCE_BYTES:
        raise RuntimeError("vault target changed during restore preview")
    if sha256(target.read_bytes()) != EXPECTED_SHA256:
        raise RuntimeError("vault target hash changed during restore preview")

    inventory_after_preview = plugin._enumerate_production_recovery_records()
    if (
        inventory_after_preview.get("success") is not True
        or inventory_after_preview.get("record_count") != 3
        or inventory_after_preview.get("attention_count") != 0
        or inventory_after_preview.get("truncated") is not False
    ):
        raise RuntimeError("recovery inventory changed during restore preview")
    require_pre_restore_inventory(index_records(inventory_after_preview))

    plan_token = preview.get("plan_token")
    if not isinstance(plan_token, str) or not re.fullmatch(
        r"[0-9a-f]{64}", plan_token
    ):
        raise RuntimeError("move-source restore plan token invalid")
    if plan_token in {
        EDIT_RECOVERY_ID,
        EDIT_RESTORE_RECOVERY_ID,
        MOVE_RECOVERY_ID,
    }:
        raise RuntimeError("move-source restore plan token collided with prior record")

    print("P5_02U_RESTORE_PREVIEW_CONTRACT=PASS")
    print(f"P5_02U_ORIGIN_MOVE_RECOVERY_ID={MOVE_RECOVERY_ID}")
    print(f"P5_02U_RESTORE_PLAN_TOKEN={plan_token}")
    print(f"P5_02U_SOURCE_CANONICAL_PATH={EXPECTED_SOURCE_PATH}")
    print("P5_02U_SOURCE_STATE_BEFORE=absent")
    print(f"P5_02U_RESTORE_SHA256={EXPECTED_SHA256}")
    print(f"P5_02U_REFERENCE_TARGET_CANONICAL_PATH={EXPECTED_TARGET_PATH}")
    print("P5_02U_REFERENCE_TARGET_STATE_BEFORE=present")
    print(f"P5_02U_REFERENCE_TARGET_SHA256={EXPECTED_SHA256}")
    print(f"P5_02U_RESTORE_DIFF_SHA256={EXPECTED_RESTORE_DIFF_SHA256}")
    print("P5_02U_MUTATION_MODE_PERSISTED=false")
    print("P5_02U_PRODUCTION_RECOVERY_COUNT_BEFORE=3")
    print("P5_02U_PRODUCTION_RECOVERY_ATTENTION_BEFORE=0")
    print("P5_02U_EXACT_DIFF_BEGIN")
    print(diff_text, end="" if diff_text.endswith("\n") else "\n")
    print("P5_02U_EXACT_DIFF_END")
    print("")
    print("P5_02U_APPROVAL_PROMPT_EXPECTED=true")
    print("P5_02U_CHOOSE_ONCE_ONLY=true", flush=True)

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
                task_id="p5-02u-move-source-restore",
                session_id="p5-02u-move-source-restore",
                tool_call_id="p5-02u-move-source-restore-call",
                turn_id="p5-02u-move-source-restore-turn",
                user_task="P5-02U exact production move-source restore",
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
        emit_failure_state(plugin, source, target, recovery_root)
        raise RuntimeError("production mutation mode did not return to disabled")

    if dispatch_error is not None:
        emit_failure_state(plugin, source, target, recovery_root)
        raise dispatch_error

    result = parse_json_result(raw_apply, label="move-source restore apply")
    if (
        result.get("success") is not True
        or result.get("mutation_performed") is not True
        or result.get("recovery_required") is not False
    ):
        emit_failure_state(plugin, source, target, recovery_root, result)
        raise RuntimeError("P5-02U production restore did not complete cleanly")

    if result.get("action") != "restore_move_source":
        raise RuntimeError("P5-02U result action mismatch")
    if result.get("origin_recovery_id") != MOVE_RECOVERY_ID:
        raise RuntimeError("P5-02U result origin recovery id mismatch")

    new_recovery_id = result.get("recovery_id")
    if not isinstance(new_recovery_id, str) or not re.fullmatch(
        r"[0-9a-f]{64}", new_recovery_id
    ):
        raise RuntimeError("P5-02U new recovery id invalid")
    if new_recovery_id != plan_token:
        raise RuntimeError("P5-02U new recovery id does not equal restore plan token")
    if new_recovery_id in {
        EDIT_RECOVERY_ID,
        EDIT_RESTORE_RECOVERY_ID,
        MOVE_RECOVERY_ID,
    }:
        raise RuntimeError("P5-02U new recovery id collided with prior record")

    expected_new_dir = recovery_root / new_recovery_id
    result_recovery_dir = result.get("recovery_dir")
    if not isinstance(result_recovery_dir, str):
        raise RuntimeError("P5-02U result recovery directory missing")
    if (
        Path(result_recovery_dir).resolve(strict=True)
        != expected_new_dir.resolve(strict=True)
    ):
        raise RuntimeError("P5-02U result recovery directory mismatch")

    if not source.is_file():
        raise RuntimeError("P5-02U restored inbox source is missing")
    if source.resolve(strict=True) != EXPECTED_SOURCE_PATH:
        raise RuntimeError("P5-02U restored source canonical path mismatch")
    if plugin._path_has_reparse_component(source):
        raise RuntimeError("P5-02U restored source has a reparse component")
    source_bytes_after = source.read_bytes()
    if source_bytes_after != SOURCE_BYTES:
        raise RuntimeError("P5-02U restored source bytes mismatch")
    if sha256(source_bytes_after) != EXPECTED_SHA256:
        raise RuntimeError("P5-02U restored source SHA-256 mismatch")
    restored_source_file_id = plugin._windows_path_file_identity(source)

    if not target.is_file():
        raise RuntimeError("P5-02U unexpectedly removed the vault target")
    if target.resolve(strict=True) != EXPECTED_TARGET_PATH:
        raise RuntimeError("P5-02U vault target canonical path changed")
    if plugin._path_has_reparse_component(target):
        raise RuntimeError("P5-02U vault target became a reparse path")
    target_bytes_after = target.read_bytes()
    if target_bytes_after != SOURCE_BYTES:
        raise RuntimeError("P5-02U vault target bytes changed")
    if sha256(target_bytes_after) != EXPECTED_SHA256:
        raise RuntimeError("P5-02U vault target SHA-256 changed")

    inventory_after = plugin._enumerate_production_recovery_records()
    if (
        inventory_after.get("success") is not True
        or inventory_after.get("record_count") != 4
        or inventory_after.get("attention_count") != 0
        or inventory_after.get("truncated") is not False
    ):
        raise RuntimeError(
            "P5-02U post-restore recovery inventory is not four clean records"
        )

    records_after = index_records(inventory_after)
    expected_ids = {
        EDIT_RECOVERY_ID,
        EDIT_RESTORE_RECOVERY_ID,
        MOVE_RECOVERY_ID,
        new_recovery_id,
    }
    if set(records_after) != expected_ids:
        raise RuntimeError("P5-02U recovery id set mismatch after restore")

    require_edit_record(records_after[EDIT_RECOVERY_ID])
    require_edit_restore_record(records_after[EDIT_RESTORE_RECOVERY_ID])

    move_record = records_after[MOVE_RECOVERY_ID]
    if (
        move_record.get("valid") is not True
        or move_record.get("needs_attention") is not False
    ):
        raise RuntimeError("P5-02T move record invalid/attention after restore")
    move_recovery = move_record.get("recovery")
    move_receipt = move_record.get("receipt")
    if not isinstance(move_recovery, dict) or not isinstance(move_receipt, dict):
        raise RuntimeError("P5-02T move inspection missing after restore")
    if (
        move_recovery.get("manifest_state") != "committed"
        or move_recovery.get("classification") != "committed_then_changed"
        or move_recovery.get("recovery_required") is not False
        or move_recovery.get("source_sha256") != EXPECTED_SHA256
        or move_recovery.get("target_sha256") != EXPECTED_SHA256
        or move_receipt.get("receipt_state") != "committed"
        or move_receipt.get("receipt_finalized") is not True
        or move_receipt.get("receipt_reconciliation_required") is not False
        or move_receipt.get("current_classification")
        != "committed_then_changed"
    ):
        raise RuntimeError(
            "P5-02T move record has unexpected post-restore classification"
        )

    restore_record = records_after[new_recovery_id]
    if (
        restore_record.get("valid") is not True
        or restore_record.get("needs_attention") is not False
    ):
        raise RuntimeError("new move-source restore record is not valid/clean")
    recovery = restore_record.get("recovery")
    receipt = restore_record.get("receipt")
    if not isinstance(recovery, dict) or not isinstance(receipt, dict):
        raise RuntimeError("new move-source restore inspection missing")

    if (
        recovery.get("success") is not True
        or recovery.get("recovery_id") != new_recovery_id
        or recovery.get("origin_recovery_id") != MOVE_RECOVERY_ID
        or recovery.get("action") != "restore_move_source"
        or recovery.get("manifest_state") != "committed"
        or recovery.get("classification") != "committed"
        or recovery.get("recovery_required") is not False
        or recovery.get("backup_sha256") != EXPECTED_SHA256
        or recovery.get("source_sha256") != EXPECTED_SHA256
        or recovery.get("after_sha256") != EXPECTED_SHA256
        or recovery.get("source_draft") != SOURCE_RELATIVE_PATH
    ):
        raise RuntimeError(
            "new committed move-source restore recovery inspection mismatch"
        )

    if (
        receipt.get("success") is not True
        or receipt.get("correlation_valid") is not True
        or receipt.get("authorization_reusable") is not False
        or receipt.get("recovery_required") is not False
        or receipt.get("recovery_id") != new_recovery_id
        or receipt.get("plan_token") != new_recovery_id
        or receipt.get("action") != "restore_move_source"
        or receipt.get("receipt_state") != "committed"
        or receipt.get("receipt_finalized") is not True
        or receipt.get("receipt_reconciliation_required") is not False
        or receipt.get("final_classification") != "committed"
        or receipt.get("current_classification") != "committed"
        or receipt.get("approval_surface") != "cli"
        or receipt.get("approval_choice") != "once"
        or receipt.get("backup_sha256") != EXPECTED_SHA256
    ):
        raise RuntimeError(
            "new committed move-source restore receipt inspection mismatch"
        )

    recovery_names = sorted(item.name for item in expected_new_dir.iterdir())
    if recovery_names != ["created_source.bin", "manifest.json", "receipt.json"]:
        raise RuntimeError(
            "P5-02U restore recovery directory entries mismatch: "
            + repr(recovery_names)
        )

    print("P5_02U_PRODUCTION_MOVE_SOURCE_RESTORE=PASS")
    print("P5_02U_APPLY_SUCCESS=true")
    print("P5_02U_MUTATION_PERFORMED=true")
    print("P5_02U_RECOVERY_REQUIRED=false")
    print(f"P5_02U_ORIGIN_MOVE_RECOVERY_ID={MOVE_RECOVERY_ID}")
    print(f"P5_02U_NEW_RECOVERY_ID={new_recovery_id}")
    print(f"P5_02U_NEW_RECOVERY_DIR={expected_new_dir}")
    print("P5_02U_NEW_RECOVERY_RECORD_VALID=true")
    print("P5_02U_NEW_RECOVERY_MANIFEST_STATE=committed")
    print("P5_02U_NEW_RECOVERY_CLASSIFICATION=committed")
    print("P5_02U_NEW_RECEIPT_STATE=committed")
    print("P5_02U_NEW_RECEIPT_FINALIZED=true")
    print("P5_02U_NEW_RECEIPT_RECONCILIATION_REQUIRED=false")
    print("P5_02U_APPROVAL_SURFACE=cli")
    print("P5_02U_APPROVAL_CHOICE=once")
    print("P5_02U_AUTHORIZATION_REUSABLE=false")
    print("P5_02U_ORIGIN_MOVE_CLASSIFICATION=committed_then_changed")
    print("P5_02U_ORIGIN_MOVE_NEEDS_ATTENTION=false")
    print("P5_02U_SOURCE_STATE_AFTER=present")
    print(f"P5_02U_SOURCE_SHA256={EXPECTED_SHA256}")
    print(f"P5_02U_SOURCE_FILE_ID={restored_source_file_id}")
    print("P5_02U_REFERENCE_TARGET_STATE_AFTER=present")
    print(f"P5_02U_REFERENCE_TARGET_SHA256={EXPECTED_SHA256}")
    print("P5_02U_TARGET_DELETED=false")
    print("P5_02U_PRODUCTION_RECOVERY_COUNT_AFTER=4")
    print("P5_02U_PRODUCTION_RECOVERY_ATTENTION_AFTER=0")
    print("P5_02U_MUTATION_MODE_AFTER=disabled")
    print("P5_02U_AUTOMATIC_TARGET_DELETE=false")
    print("P5_02U_AUTOMATIC_RECOVERY_CLEANUP=false")
    print("P5_02U_AUTOMATIC_FOLLOWUP_MUTATION=false")
    print("P5_02U_RECOVERY_EVIDENCE_PRESERVED=true")
    print("HERMES_MANUAL_OFF=true")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02U_PRODUCTION_MOVE_SOURCE_RESTORE=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
