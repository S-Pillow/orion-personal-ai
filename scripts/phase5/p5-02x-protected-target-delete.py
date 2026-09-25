#!/usr/bin/env python3
"""P5-02X exact protected vault-target deletion.

Deletes only the retained P5-02T vault target after:
- exact path/hash/content validation;
- exact registered delete-preview validation;
- Windows file-identity binding in the immutable preview plan;
- exact four-record / zero-attention P5-02U recovery baseline;
- a fresh Hermes human ONCE decision through the guarded registered apply path.

The restored inbox source must remain present and unchanged. Recovery cleanup is
not performed here. On any ambiguous failure the gate preserves observed state
and all recovery evidence.
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
PREVIEW_DELETE_TOOL = "orion_vault_preview_delete"

EDIT_RECOVERY_ID = (
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f"
)
EDIT_RESTORE_RECOVERY_ID = (
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27"
)
MOVE_RECOVERY_ID = (
    "8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6"
)
MOVE_SOURCE_RESTORE_RECOVERY_ID = (
    "5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175"
)

SOURCE_RELATIVE_PATH = "_Orion-P5-Move-Canary.md"
TARGET_RELATIVE_PATH = "_Orion-P5-Move-Canary.md"
EXPECTED_INBOX_ROOT = Path(r"C:\Personal\Orion-Inbox")
EXPECTED_VAULT_ROOT = Path(r"C:\Personal\Me")
EXPECTED_SOURCE_PATH = Path(
    r"C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md"
)
EXPECTED_TARGET_PATH = Path(
    r"C:\Personal\Me\_Orion-P5-Move-Canary.md"
)
EXPECTED_SOURCE_FILE_ID = (
    "5e1aeb8a1aeb5d91:67660100000036010000000000000000"
)

FROZEN_BYTES = (
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
EXPECTED_DELETE_DIFF_SHA256 = (
    "74c256be2c280ecabb7175d3f18cba214dfb37b34f595ef72146921c6133c0cf"
)

EXPECTED_BASELINE = {
    EDIT_RECOVERY_ID: ("edit_note", "committed_then_changed"),
    EDIT_RESTORE_RECOVERY_ID: ("restore_edit", "committed"),
    MOVE_RECOVERY_ID: ("move_draft", "committed_then_changed"),
    MOVE_SOURCE_RESTORE_RECOVERY_ID: ("restore_move_source", "committed"),
}


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


def require_baseline(records: dict[str, dict]) -> None:
    if set(records) != set(EXPECTED_BASELINE):
        raise RuntimeError("recovery id set differs from accepted P5-02U state")

    for recovery_id, (action, classification) in EXPECTED_BASELINE.items():
        record = records[recovery_id]
        if (
            record.get("valid") is not True
            or record.get("needs_attention") is not False
        ):
            raise RuntimeError(
                f"accepted recovery invalid/attention: {recovery_id}"
            )
        recovery = record.get("recovery")
        receipt = record.get("receipt")
        if not isinstance(recovery, dict) or not isinstance(receipt, dict):
            raise RuntimeError(
                f"accepted recovery inspection missing: {recovery_id}"
            )
        if (
            recovery.get("success") is not True
            or recovery.get("action") != action
            or recovery.get("manifest_state") != "committed"
            or recovery.get("classification") != classification
            or recovery.get("recovery_required") is not False
        ):
            raise RuntimeError(
                f"accepted recovery state mismatch: {recovery_id}"
            )
        if (
            receipt.get("success") is not True
            or receipt.get("correlation_valid") is not True
            or receipt.get("authorization_reusable") is not False
            or receipt.get("recovery_required") is not False
            or receipt.get("receipt_state") != "committed"
            or receipt.get("receipt_finalized") is not True
            or receipt.get("receipt_reconciliation_required") is not False
            or receipt.get("current_classification") != classification
        ):
            raise RuntimeError(
                f"accepted receipt state mismatch: {recovery_id}"
            )


def emit_failure_state(
    plugin,
    source: Path,
    target: Path,
    recovery_root: Path,
    *,
    result: dict | None = None,
    stage: str = "unknown",
) -> None:
    print(f"P5_02X_FAILURE_STAGE={stage}")
    if isinstance(result, dict):
        print(f"P5_02X_APPLY_ERROR={result.get('error')}")
        print(
            "P5_02X_APPLY_MUTATION_PERFORMED="
            f"{str(bool(result.get('mutation_performed'))).lower()}"
        )
        print(
            "P5_02X_APPLY_RECOVERY_REQUIRED="
            f"{str(bool(result.get('recovery_required'))).lower()}"
        )
        if isinstance(result.get("recovery_id"), str):
            print(f"P5_02X_RECOVERY_ID={result['recovery_id']}")

    try:
        if source.is_file():
            print("P5_02X_POST_FAILURE_SOURCE_STATE=present")
            print(
                "P5_02X_POST_FAILURE_SOURCE_SHA256="
                f"{sha256(source.read_bytes())}"
            )
        elif os.path.lexists(source):
            print("P5_02X_POST_FAILURE_SOURCE_STATE=non_file")
        else:
            print("P5_02X_POST_FAILURE_SOURCE_STATE=absent")
    except Exception as exc:
        print(
            "P5_02X_POST_FAILURE_SOURCE_INSPECTION_ERROR="
            f"{type(exc).__name__}"
        )

    try:
        if target.is_file():
            print("P5_02X_POST_FAILURE_TARGET_STATE=present")
            print(
                "P5_02X_POST_FAILURE_TARGET_SHA256="
                f"{sha256(target.read_bytes())}"
            )
        elif os.path.lexists(target):
            print("P5_02X_POST_FAILURE_TARGET_STATE=non_file")
        else:
            print("P5_02X_POST_FAILURE_TARGET_STATE=absent")
    except Exception as exc:
        print(
            "P5_02X_POST_FAILURE_TARGET_INSPECTION_ERROR="
            f"{type(exc).__name__}"
        )

    try:
        inventory = plugin._enumerate_production_recovery_records()
        print(
            "P5_02X_POST_FAILURE_RECOVERY_ENUM_SUCCESS="
            f"{str(bool(inventory.get('success'))).lower()}"
        )
        if inventory.get("success"):
            print(
                "P5_02X_POST_FAILURE_RECOVERY_COUNT="
                f"{inventory.get('record_count')}"
            )
            print(
                "P5_02X_POST_FAILURE_RECOVERY_ATTENTION="
                f"{inventory.get('attention_count')}"
            )
            print(
                "P5_02X_POST_FAILURE_RECOVERY_TRUNCATED="
                f"{str(bool(inventory.get('truncated'))).lower()}"
            )
    except Exception as exc:
        print(
            "P5_02X_POST_FAILURE_RECOVERY_ENUM_ERROR="
            f"{type(exc).__name__}"
        )

    print(f"P5_02X_RECOVERY_ROOT={recovery_root}")
    print("P5_02X_AUTOMATIC_TARGET_RESTORE=false")
    print("P5_02X_AUTOMATIC_SOURCE_MUTATION=false")
    print("P5_02X_AUTOMATIC_RECOVERY_CLEANUP=false")
    print("P5_02X_RECOVERY_EVIDENCE_PRESERVED=true")


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
    preview_entry = registry.get_entry(PREVIEW_DELETE_TOOL)
    if apply_entry is None or preview_entry is None:
        raise RuntimeError("installed Orion delete/apply tools were not discovered")
    if apply_entry.handler.__name__ != "apply_plan_production_guarded":
        raise RuntimeError("registered apply handler identity mismatch")
    if preview_entry.handler.__name__ != "preview_delete":
        raise RuntimeError("registered delete-preview handler identity mismatch")

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
            "registered delete preview was not loaded from verified installed plugin"
        )
    if apply_module is not preview_module:
        raise RuntimeError("registered Orion tools were loaded from different modules")

    plugin = apply_module
    if plugin.PLUGIN_VERSION != "p5-02v-0.3.0":
        raise RuntimeError("installed Orion plugin version mismatch")
    if apply_entry.handler is not plugin.apply_plan_production_guarded:
        raise RuntimeError("registered apply handler object mismatch")
    if preview_entry.handler is not plugin.preview_delete:
        raise RuntimeError("registered delete-preview handler object mismatch")
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
        raise RuntimeError(f"unexpected pre-delete production mode: {mode}")

    roots = plugin._validate_production_roots()
    if roots.get("success") is not True:
        raise RuntimeError("native production-root validation failed before delete")
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
        or inventory_before.get("record_count") != 4
        or inventory_before.get("attention_count") != 0
        or inventory_before.get("truncated") is not False
    ):
        raise RuntimeError(
            "production recovery inventory differs from accepted P5-02U state"
        )
    require_baseline(index_records(inventory_before))

    source = inbox_root / SOURCE_RELATIVE_PATH
    target = vault_root / TARGET_RELATIVE_PATH

    if not source.is_file():
        raise RuntimeError("restored inbox source is missing before target delete")
    if source.resolve(strict=True) != EXPECTED_SOURCE_PATH:
        raise RuntimeError("restored inbox source canonical path mismatch")
    if plugin._path_has_reparse_component(source):
        raise RuntimeError("restored inbox source has a reparse component")
    source_bytes = source.read_bytes()
    if source_bytes != FROZEN_BYTES or sha256(source_bytes) != EXPECTED_SHA256:
        raise RuntimeError("restored inbox source differs from frozen bytes/hash")
    if os.name != "nt":
        raise RuntimeError("P5-02X production target is Windows-only")
    source_file_id = plugin._windows_path_file_identity(source)
    if source_file_id != EXPECTED_SOURCE_FILE_ID:
        raise RuntimeError("restored inbox source Windows identity mismatch")

    if not target.is_file():
        raise RuntimeError("retained vault target is missing before protected delete")
    if target.resolve(strict=True) != EXPECTED_TARGET_PATH:
        raise RuntimeError("retained vault target canonical path mismatch")
    if plugin._path_has_reparse_component(target):
        raise RuntimeError("retained vault target has a reparse component")
    target_bytes = target.read_bytes()
    if target_bytes != FROZEN_BYTES or sha256(target_bytes) != EXPECTED_SHA256:
        raise RuntimeError("retained vault target differs from frozen bytes/hash")

    raw_preview = handle_function_call(
        PREVIEW_DELETE_TOOL,
        {"target_relative_path": TARGET_RELATIVE_PATH},
        task_id="p5-02x-delete-preview",
        session_id="p5-02x-delete-preview",
        tool_call_id="p5-02x-delete-preview-call",
        turn_id="p5-02x-delete-preview-turn",
        user_task="P5-02X exact protected target delete preview",
        enabled_tools=[PREVIEW_DELETE_TOOL],
        enabled_toolsets=["orion_vault"],
    )
    preview = parse_json_result(raw_preview, label="delete preview")
    if (
        preview.get("success") is not True
        or preview.get("mutation_performed") is not False
        or preview.get("changed") is not True
    ):
        raise RuntimeError("exact production delete preview did not succeed read-only")

    plan = preview.get("plan")
    diff_text = preview.get("diff")
    if not isinstance(plan, dict) or not isinstance(diff_text, str):
        raise RuntimeError("production delete preview contract missing plan/diff")
    if plan.get("action") != "delete_note":
        raise RuntimeError("production delete preview action mismatch")
    if plan.get("target_relative_path") != TARGET_RELATIVE_PATH:
        raise RuntimeError("production delete preview relative path mismatch")
    if plan.get("target_canonical_path") != str(EXPECTED_TARGET_PATH):
        raise RuntimeError("production delete preview canonical path mismatch")
    if plan.get("target_sha256") != EXPECTED_SHA256:
        raise RuntimeError("production delete preview target SHA-256 mismatch")
    if plan.get("target_state") != "present":
        raise RuntimeError("production delete preview target state mismatch")
    target_file_id = plan.get("target_file_id")
    if (
        not isinstance(target_file_id, str)
        or not re.fullmatch(r"[0-9a-f]+:[0-9a-f]+", target_file_id)
    ):
        raise RuntimeError("production delete preview Windows file identity invalid")
    if plugin._windows_path_file_identity(target) != target_file_id:
        raise RuntimeError("production delete preview file identity changed")
    if plan.get("diff_sha256") != EXPECTED_DELETE_DIFF_SHA256:
        raise RuntimeError("production delete preview diff hash mismatch")
    if sha256(diff_text.encode("utf-8")) != EXPECTED_DELETE_DIFF_SHA256:
        raise RuntimeError("production delete exact diff differs from frozen contract")

    if source.read_bytes() != FROZEN_BYTES:
        raise RuntimeError("restored inbox source changed during delete preview")
    if plugin._windows_path_file_identity(source) != EXPECTED_SOURCE_FILE_ID:
        raise RuntimeError("restored inbox source identity changed during preview")
    if target.read_bytes() != FROZEN_BYTES:
        raise RuntimeError("retained target changed during delete preview")
    if plugin._windows_path_file_identity(target) != target_file_id:
        raise RuntimeError("retained target identity changed during preview")

    inventory_after_preview = plugin._enumerate_production_recovery_records()
    if (
        inventory_after_preview.get("success") is not True
        or inventory_after_preview.get("record_count") != 4
        or inventory_after_preview.get("attention_count") != 0
        or inventory_after_preview.get("truncated") is not False
    ):
        raise RuntimeError("recovery inventory changed during delete preview")
    require_baseline(index_records(inventory_after_preview))

    plan_token = preview.get("plan_token")
    if not isinstance(plan_token, str) or not re.fullmatch(
        r"[0-9a-f]{64}", plan_token
    ):
        raise RuntimeError("production delete preview plan token invalid")

    print("P5_02X_PREVIEW_CONTRACT=PASS")
    print(f"P5_02X_PLAN_TOKEN={plan_token}")
    print(f"P5_02X_SOURCE_CANONICAL_PATH={EXPECTED_SOURCE_PATH}")
    print(f"P5_02X_SOURCE_FILE_ID={EXPECTED_SOURCE_FILE_ID}")
    print(f"P5_02X_SOURCE_SHA256={EXPECTED_SHA256}")
    print(f"P5_02X_TARGET_CANONICAL_PATH={EXPECTED_TARGET_PATH}")
    print(f"P5_02X_TARGET_FILE_ID={target_file_id}")
    print(f"P5_02X_TARGET_SHA256={EXPECTED_SHA256}")
    print("P5_02X_TARGET_STATE_BEFORE=present")
    print(f"P5_02X_DELETE_DIFF_SHA256={EXPECTED_DELETE_DIFF_SHA256}")
    print("P5_02X_PRODUCTION_RECOVERY_COUNT_BEFORE=4")
    print("P5_02X_PRODUCTION_RECOVERY_ATTENTION_BEFORE=0")
    print("P5_02X_MUTATION_MODE_PERSISTED=false")
    print("P5_02X_EXACT_DIFF_BEGIN")
    print(diff_text, end="" if diff_text.endswith("\n") else "\n")
    print("P5_02X_EXACT_DIFF_END")
    print("")
    print("P5_02X_APPROVAL_PROMPT_EXPECTED=true")
    print("P5_02X_CHOOSE_ONCE_ONLY=true", flush=True)

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
                task_id="p5-02x-protected-delete",
                session_id="p5-02x-protected-delete",
                tool_call_id="p5-02x-protected-delete-call",
                turn_id="p5-02x-protected-delete-turn",
                user_task="P5-02X exact protected target delete",
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
        emit_failure_state(
            plugin,
            source,
            target,
            recovery_root,
            stage="mutation_mode_cleanup",
        )
        raise RuntimeError("production mutation mode did not return to disabled")

    if dispatch_error is not None:
        emit_failure_state(
            plugin,
            source,
            target,
            recovery_root,
            stage="registered_apply_dispatch",
        )
        raise dispatch_error

    result = parse_json_result(raw_apply, label="delete apply")
    if (
        result.get("success") is not True
        or result.get("mutation_performed") is not True
        or result.get("recovery_required") is not False
    ):
        emit_failure_state(
            plugin,
            source,
            target,
            recovery_root,
            result=result,
            stage="apply_result",
        )
        raise RuntimeError("P5-02X protected delete did not complete cleanly")

    if result.get("action") != "delete_note":
        raise RuntimeError("P5-02X result action mismatch")
    if result.get("target_relative_path") != TARGET_RELATIVE_PATH:
        raise RuntimeError("P5-02X result target mismatch")

    recovery_id = result.get("recovery_id")
    if not isinstance(recovery_id, str) or not re.fullmatch(
        r"[0-9a-f]{64}", recovery_id
    ):
        raise RuntimeError("P5-02X recovery id invalid")
    if recovery_id != plan_token:
        raise RuntimeError("P5-02X recovery id does not equal delete plan token")
    if recovery_id in EXPECTED_BASELINE:
        raise RuntimeError("P5-02X recovery id collided with historical record")

    expected_recovery_dir = recovery_root / recovery_id
    result_recovery_dir = result.get("recovery_dir")
    if not isinstance(result_recovery_dir, str):
        raise RuntimeError("P5-02X recovery directory missing")
    if (
        Path(result_recovery_dir).resolve(strict=True)
        != expected_recovery_dir.resolve(strict=True)
    ):
        raise RuntimeError("P5-02X recovery directory mismatch")

    if not source.is_file():
        raise RuntimeError("P5-02X changed/removed restored inbox source")
    if source.resolve(strict=True) != EXPECTED_SOURCE_PATH:
        raise RuntimeError("P5-02X source canonical path changed")
    if source.read_bytes() != FROZEN_BYTES:
        raise RuntimeError("P5-02X source bytes changed")
    if sha256(source.read_bytes()) != EXPECTED_SHA256:
        raise RuntimeError("P5-02X source hash changed")
    if plugin._windows_path_file_identity(source) != EXPECTED_SOURCE_FILE_ID:
        raise RuntimeError("P5-02X source file identity changed")

    if os.path.lexists(target):
        raise RuntimeError("P5-02X target still exists after successful delete")

    inventory_after = plugin._enumerate_production_recovery_records()
    if (
        inventory_after.get("success") is not True
        or inventory_after.get("record_count") != 5
        or inventory_after.get("attention_count") != 0
        or inventory_after.get("truncated") is not False
    ):
        raise RuntimeError(
            "P5-02X post-delete recovery inventory is not five clean records"
        )

    records_after = index_records(inventory_after)
    expected_ids = set(EXPECTED_BASELINE) | {recovery_id}
    if set(records_after) != expected_ids:
        raise RuntimeError("P5-02X post-delete recovery id set mismatch")
    require_baseline({
        key: records_after[key] for key in EXPECTED_BASELINE
    })

    delete_record = records_after[recovery_id]
    if (
        delete_record.get("valid") is not True
        or delete_record.get("needs_attention") is not False
    ):
        raise RuntimeError("new P5-02X delete recovery record invalid/attention")

    recovery = delete_record.get("recovery")
    receipt = delete_record.get("receipt")
    if not isinstance(recovery, dict) or not isinstance(receipt, dict):
        raise RuntimeError("new P5-02X recovery/receipt inspection missing")

    if (
        recovery.get("success") is not True
        or recovery.get("recovery_id") != recovery_id
        or recovery.get("action") != "delete_note"
        or recovery.get("manifest_state") != "committed"
        or recovery.get("classification") != "committed"
        or recovery.get("recovery_required") is not False
        or recovery.get("backup_sha256") != EXPECTED_SHA256
        or recovery.get("target_sha256") is not None
        or recovery.get("before_sha256") != EXPECTED_SHA256
        or recovery.get("after_state") != "absent"
        or recovery.get("target_relative_path") != TARGET_RELATIVE_PATH
    ):
        raise RuntimeError("new committed P5-02X delete recovery mismatch")

    if (
        receipt.get("success") is not True
        or receipt.get("correlation_valid") is not True
        or receipt.get("authorization_reusable") is not False
        or receipt.get("recovery_required") is not False
        or receipt.get("recovery_id") != recovery_id
        or receipt.get("plan_token") != recovery_id
        or receipt.get("action") != "delete_note"
        or receipt.get("receipt_state") != "committed"
        or receipt.get("receipt_finalized") is not True
        or receipt.get("receipt_reconciliation_required") is not False
        or receipt.get("final_classification") != "committed"
        or receipt.get("current_classification") != "committed"
        or receipt.get("approval_surface") != "cli"
        or receipt.get("approval_choice") != "once"
        or receipt.get("backup_sha256") != EXPECTED_SHA256
    ):
        raise RuntimeError("new committed P5-02X delete receipt mismatch")

    recovery_names = sorted(
        item.name for item in expected_recovery_dir.iterdir()
    )
    if recovery_names != ["deleted_target.bin", "manifest.json", "receipt.json"]:
        raise RuntimeError(
            "P5-02X delete recovery directory entries mismatch: "
            + repr(recovery_names)
        )
    if (expected_recovery_dir / "deleted_target.bin").read_bytes() != FROZEN_BYTES:
        raise RuntimeError("P5-02X delete backup bytes mismatch")

    print("P5_02X_PROTECTED_TARGET_DELETE=PASS")
    print("P5_02X_APPLY_SUCCESS=true")
    print("P5_02X_MUTATION_PERFORMED=true")
    print("P5_02X_RECOVERY_REQUIRED=false")
    print(f"P5_02X_RECOVERY_ID={recovery_id}")
    print(f"P5_02X_RECOVERY_DIR={expected_recovery_dir}")
    print("P5_02X_DELETE_RECOVERY_RECORD_VALID=true")
    print("P5_02X_DELETE_RECOVERY_MANIFEST_STATE=committed")
    print("P5_02X_DELETE_RECOVERY_CLASSIFICATION=committed")
    print("P5_02X_RECEIPT_STATE=committed")
    print("P5_02X_RECEIPT_FINALIZED=true")
    print("P5_02X_RECEIPT_RECONCILIATION_REQUIRED=false")
    print("P5_02X_APPROVAL_SURFACE=cli")
    print("P5_02X_APPROVAL_CHOICE=once")
    print("P5_02X_AUTHORIZATION_REUSABLE=false")
    print("P5_02X_SOURCE_STATE_AFTER=present")
    print(f"P5_02X_SOURCE_SHA256={EXPECTED_SHA256}")
    print(f"P5_02X_SOURCE_FILE_ID={EXPECTED_SOURCE_FILE_ID}")
    print("P5_02X_TARGET_STATE_AFTER=absent")
    print("P5_02X_PRODUCTION_RECOVERY_COUNT_AFTER=5")
    print("P5_02X_PRODUCTION_RECOVERY_ATTENTION_AFTER=0")
    print("P5_02X_MUTATION_MODE_AFTER=disabled")
    print("P5_02X_AUTOMATIC_TARGET_RESTORE=false")
    print("P5_02X_AUTOMATIC_SOURCE_MUTATION=false")
    print("P5_02X_AUTOMATIC_RECOVERY_CLEANUP=false")
    print("P5_02X_RECOVERY_EVIDENCE_PRESERVED=true")
    print("HERMES_MANUAL_OFF=true")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02X_PROTECTED_TARGET_DELETE=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
