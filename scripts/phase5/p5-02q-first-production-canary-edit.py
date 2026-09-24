#!/usr/bin/env python3
"""P5-02Q first production canary edit.

This is the first authorized Orion production mutation gate. It is intentionally
limited to one frozen edit_note contract against the Phase 5 canary.

The script:
- loads the installed COMPANION plugin;
- proves production mutation mode is not persisted;
- proves recovery inventory is empty;
- validates the exact canary path, bytes, SHA-256, and Windows file identity;
- creates the exact side-effect-free preview while mutation is still disabled;
- validates the frozen after-hash and exact diff hash;
- enables mutation only in this child process immediately before apply;
- dispatches exactly orion_vault_apply_plan through Hermes
  model_tools.handle_function_call();
- requires the plugin's genuine fresh human ONCE approval;
- removes mutation_enabled from the process immediately after dispatch;
- verifies the exact after bytes/hash and committed schema-v2 recovery record;
- never auto-restores or deletes recovery evidence on failure.
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
PREVIEW_TOOL = "orion_vault_preview_edit"
TARGET_RELATIVE_PATH = "_Orion-P5-Canary.md"
EXPECTED_CANONICAL_PATH = Path(r"C:\Personal\Me\_Orion-P5-Canary.md")
EXPECTED_PRE_FILE_ID = "5e1aeb8a1aeb5d91:cba20a00000012000000000000000000"
BEFORE_BYTES = (
    b"# Orion Phase 5 Canary\n"
    b"state: before\n"
    b"gate: first-production-edit\n"
)
AFTER_TEXT = (
    "# Orion Phase 5 Canary\n"
    "state: after\n"
    "gate: first-production-edit\n"
)
AFTER_BYTES = AFTER_TEXT.encode("utf-8")
EXPECTED_BEFORE_SHA256 = "ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c"
EXPECTED_AFTER_SHA256 = "86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19"
EXPECTED_DIFF_SHA256 = "6642d44372449d01e1ec3f5d325bd2b372f52cc58610293bcccf0e4e4ec996e8"


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


def print_failure_state(plugin, target: Path, recovery_root: Path, result: dict) -> None:
    print("P5_02Q_APPLY_SUCCESS=false")
    print(f"P5_02Q_APPLY_ERROR={result.get('error')}")
    print(f"P5_02Q_APPLY_MUTATION_PERFORMED={str(bool(result.get('mutation_performed'))).lower()}")
    print(f"P5_02Q_APPLY_RECOVERY_REQUIRED={str(bool(result.get('recovery_required'))).lower()}")
    if isinstance(result.get("recovery_id"), str):
        print(f"P5_02Q_RECOVERY_ID={result['recovery_id']}")
    if target.is_file():
        try:
            print(f"P5_02Q_POST_FAILURE_TARGET_SHA256={sha256(target.read_bytes())}")
        except Exception as exc:
            print(f"P5_02Q_POST_FAILURE_TARGET_HASH_ERROR={type(exc).__name__}")
    try:
        inventory = plugin._enumerate_production_recovery_records()
        print(f"P5_02Q_POST_FAILURE_RECOVERY_ENUM_SUCCESS={str(bool(inventory.get('success'))).lower()}")
        if inventory.get("success"):
            print(f"P5_02Q_POST_FAILURE_RECOVERY_COUNT={inventory.get('record_count')}")
            print(f"P5_02Q_POST_FAILURE_RECOVERY_ATTENTION={inventory.get('attention_count')}")
            print(f"P5_02Q_POST_FAILURE_RECOVERY_TRUNCATED={str(bool(inventory.get('truncated'))).lower()}")
    except Exception as exc:
        print(f"P5_02Q_POST_FAILURE_RECOVERY_ENUM_ERROR={type(exc).__name__}")
    print(f"P5_02Q_RECOVERY_ROOT={recovery_root}")
    print("P5_02Q_AUTOMATIC_RESTORE=false")
    print("P5_02Q_RECOVERY_EVIDENCE_PRESERVED=true")


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

    effective_recovery = (os.environ.get("ORION_P5_PRODUCTION_RECOVERY_ROOT") or "").strip()
    if not effective_recovery:
        raise RuntimeError("persisted production recovery root was not loaded")
    if Path(effective_recovery).resolve(strict=True) != expected_recovery_root:
        raise RuntimeError("effective production recovery root mismatch")
    if (os.environ.get("ORION_P5_MUTATION_MODE") or "").strip():
        raise RuntimeError("production mutation mode unexpectedly persisted")
    for name in ("ORION_P5_ALLOW_DISPOSABLE_MUTATION", "ORION_P5_RECOVERY_ROOT"):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"disposable mutation setting unexpectedly persisted: {name}")

    discover_plugins()
    apply_entry = registry.get_entry(APPLY_TOOL)
    preview_entry = registry.get_entry(PREVIEW_TOOL)
    if apply_entry is None or preview_entry is None:
        raise RuntimeError("installed Orion tools were not discovered")
    if apply_entry.handler.__name__ != "apply_plan_production_guarded":
        raise RuntimeError("registered apply handler identity mismatch")

    plugin = sys.modules.get(apply_entry.handler.__module__)
    if plugin is None:
        raise RuntimeError("installed Orion plugin module unavailable")
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
        raise RuntimeError(f"unexpected pre-apply production mode: {mode}")

    roots = plugin._validate_production_roots()
    if roots.get("success") is not True:
        raise RuntimeError("native production root validation failed before preview")
    if roots.get("mutation_allowed") is not False:
        raise RuntimeError("native production root validation unexpectedly allows mutation")

    vault_root = Path(roots["vault_root"]).resolve(strict=True)
    recovery_root = Path(roots["recovery_root"]).resolve(strict=True)
    if recovery_root != expected_recovery_root:
        raise RuntimeError("native recovery root mismatch")

    inventory_before = plugin._enumerate_production_recovery_records()
    if (
        inventory_before.get("success") is not True
        or inventory_before.get("record_count") != 0
        or inventory_before.get("attention_count") != 0
        or inventory_before.get("truncated") is not False
    ):
        raise RuntimeError("production recovery inventory is not clean before P5-02Q")

    target = vault_root / TARGET_RELATIVE_PATH
    if not target.is_file():
        raise RuntimeError("production canary is missing")
    canonical_target = target.resolve(strict=True)
    if canonical_target != EXPECTED_CANONICAL_PATH:
        raise RuntimeError("production canary canonical path mismatch")
    if plugin._path_has_reparse_component(target):
        raise RuntimeError("production canary has reparse component")

    before_actual = target.read_bytes()
    if before_actual != BEFORE_BYTES:
        raise RuntimeError("production canary before bytes differ from frozen contract")
    if sha256(before_actual) != EXPECTED_BEFORE_SHA256:
        raise RuntimeError("production canary before SHA-256 mismatch")

    pre_file_id = plugin._windows_path_file_identity(target)
    if pre_file_id != EXPECTED_PRE_FILE_ID:
        raise RuntimeError("production canary Windows file identity mismatch")

    raw_preview = handle_function_call(
        PREVIEW_TOOL,
        {
            "target_relative_path": TARGET_RELATIVE_PATH,
            "new_content": AFTER_TEXT,
        },
        task_id="p5-02q-canary-preview",
        session_id="p5-02q-canary-preview",
        tool_call_id="p5-02q-canary-preview-call",
        turn_id="p5-02q-canary-preview-turn",
        user_task="P5-02Q exact production canary edit preview",
        enabled_tools=[PREVIEW_TOOL],
        enabled_toolsets=["orion_vault"],
    )
    preview = parse_json_result(raw_preview, label="preview")
    if preview.get("success") is not True or preview.get("mutation_performed") is not False:
        raise RuntimeError("exact production preview did not succeed read-only")

    plan = preview.get("plan")
    diff_text = preview.get("diff")
    if not isinstance(plan, dict) or not isinstance(diff_text, str):
        raise RuntimeError("production preview contract missing plan/diff")
    if plan.get("action") != "edit_note":
        raise RuntimeError("production preview action mismatch")
    if plan.get("target_relative_path") != TARGET_RELATIVE_PATH:
        raise RuntimeError("production preview relative target mismatch")
    if plan.get("target_canonical_path") != str(EXPECTED_CANONICAL_PATH):
        raise RuntimeError("production preview canonical target mismatch")
    if plan.get("target_file_id") != EXPECTED_PRE_FILE_ID:
        raise RuntimeError("production preview file identity mismatch")
    if plan.get("original_sha256") != EXPECTED_BEFORE_SHA256:
        raise RuntimeError("production preview before hash mismatch")
    if plan.get("proposed_sha256") != EXPECTED_AFTER_SHA256:
        raise RuntimeError("production preview after hash mismatch")
    if plan.get("diff_sha256") != EXPECTED_DIFF_SHA256:
        raise RuntimeError("production preview diff hash mismatch")
    if sha256(diff_text.encode("utf-8")) != EXPECTED_DIFF_SHA256:
        raise RuntimeError("production preview exact diff differs from frozen contract")
    if target.read_bytes() != BEFORE_BYTES:
        raise RuntimeError("production canary changed during preview")
    if plugin._windows_path_file_identity(target) != EXPECTED_PRE_FILE_ID:
        raise RuntimeError("production canary identity changed during preview")

    plan_token = preview.get("plan_token")
    if not isinstance(plan_token, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_token):
        raise RuntimeError("production preview plan token invalid")

    print("P5_02Q_PREVIEW_CONTRACT=PASS")
    print(f"P5_02Q_PLAN_TOKEN={plan_token}")
    print(f"P5_02Q_CANARY_PRE_FILE_ID={EXPECTED_PRE_FILE_ID}")
    print(f"P5_02Q_CANARY_BEFORE_SHA256={EXPECTED_BEFORE_SHA256}")
    print(f"P5_02Q_CANARY_AFTER_SHA256={EXPECTED_AFTER_SHA256}")
    print(f"P5_02Q_CANARY_DIFF_SHA256={EXPECTED_DIFF_SHA256}")
    print("P5_02Q_MUTATION_MODE_PERSISTED=false")
    print("P5_02Q_PRODUCTION_RECOVERY_COUNT_BEFORE=0")
    print("P5_02Q_PRODUCTION_RECOVERY_ATTENTION_BEFORE=0")
    print("P5_02Q_HERMES_GATEWAY_REQUIRED=false")
    print("")
    print("P5_02Q_APPROVAL_PROMPT_EXPECTED=true")
    print("P5_02Q_CHOOSE_ONCE_ONLY=true", flush=True)

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
            task_id="p5-02q-canary-apply",
            session_id="p5-02q-canary-apply",
            tool_call_id="p5-02q-canary-apply-call",
            turn_id="p5-02q-canary-apply-turn",
            user_task="P5-02Q exact first production canary edit",
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

    result = parse_json_result(raw_apply, label="apply")
    if (
        result.get("success") is not True
        or result.get("mutation_performed") is not True
        or result.get("recovery_required") is not False
    ):
        print_failure_state(plugin, target, recovery_root, result)
        raise RuntimeError("P5-02Q production apply did not complete cleanly")

    if result.get("action") != "edit_note":
        raise RuntimeError("P5-02Q result action mismatch")
    if result.get("target_relative_path") != TARGET_RELATIVE_PATH:
        raise RuntimeError("P5-02Q result target mismatch")

    recovery_id = result.get("recovery_id")
    if not isinstance(recovery_id, str) or not re.fullmatch(r"[0-9a-f]{64}", recovery_id):
        raise RuntimeError("P5-02Q recovery id invalid")
    if recovery_id != plan_token:
        raise RuntimeError("P5-02Q recovery id does not equal plan token")

    expected_recovery_dir = recovery_root / recovery_id
    result_recovery_dir = result.get("recovery_dir")
    if not isinstance(result_recovery_dir, str):
        raise RuntimeError("P5-02Q result recovery directory missing")
    if Path(result_recovery_dir).resolve(strict=True) != expected_recovery_dir.resolve(strict=True):
        raise RuntimeError("P5-02Q result recovery directory mismatch")

    after_actual = target.read_bytes()
    if after_actual != AFTER_BYTES:
        raise RuntimeError("P5-02Q target bytes do not equal frozen after bytes")
    if sha256(after_actual) != EXPECTED_AFTER_SHA256:
        raise RuntimeError("P5-02Q target after SHA-256 mismatch")
    if plugin._path_has_reparse_component(target):
        raise RuntimeError("P5-02Q target became a reparse path")
    post_file_id = plugin._windows_path_file_identity(target)

    inventory_after = plugin._enumerate_production_recovery_records()
    if (
        inventory_after.get("success") is not True
        or inventory_after.get("record_count") != 1
        or inventory_after.get("attention_count") != 0
        or inventory_after.get("truncated") is not False
    ):
        raise RuntimeError(
            "P5-02Q post-mutation recovery inventory is not one clean committed record"
        )

    records = inventory_after.get("records")
    if not isinstance(records, list) or len(records) != 1:
        raise RuntimeError("P5-02Q recovery record list mismatch")
    record = records[0]
    if (
        record.get("recovery_id") != recovery_id
        or record.get("valid") is not True
        or record.get("needs_attention") is not False
    ):
        raise RuntimeError("P5-02Q recovery record identity/validity mismatch")

    recovery = record.get("recovery")
    receipt = record.get("receipt")
    if not isinstance(recovery, dict) or not isinstance(receipt, dict):
        raise RuntimeError("P5-02Q recovery/receipt inspection missing")

    if (
        recovery.get("success") is not True
        or recovery.get("action") != "edit_note"
        or recovery.get("manifest_state") != "committed"
        or recovery.get("classification") != "committed"
        or recovery.get("recovery_required") is not False
        or recovery.get("backup_sha256") != EXPECTED_BEFORE_SHA256
        or recovery.get("target_sha256") != EXPECTED_AFTER_SHA256
        or recovery.get("before_sha256") != EXPECTED_BEFORE_SHA256
        or recovery.get("after_sha256") != EXPECTED_AFTER_SHA256
        or recovery.get("target_relative_path") != TARGET_RELATIVE_PATH
    ):
        raise RuntimeError("P5-02Q committed recovery inspection mismatch")

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
        or receipt.get("approval_surface") != "cli"
        or receipt.get("approval_choice") != "once"
        or receipt.get("backup_sha256") != EXPECTED_BEFORE_SHA256
    ):
        raise RuntimeError("P5-02Q committed receipt inspection mismatch")

    recovery_names = sorted(p.name for p in expected_recovery_dir.iterdir())
    if recovery_names != ["manifest.json", "original.bin", "receipt.json"]:
        raise RuntimeError(
            "P5-02Q recovery directory contains unexpected/missing entries: "
            + repr(recovery_names)
        )

    print("P5_02Q_PRODUCTION_CANARY_EDIT=PASS")
    print("P5_02Q_APPLY_SUCCESS=true")
    print("P5_02Q_MUTATION_PERFORMED=true")
    print("P5_02Q_RECOVERY_REQUIRED=false")
    print(f"P5_02Q_RECOVERY_ID={recovery_id}")
    print(f"P5_02Q_RECOVERY_DIR={expected_recovery_dir}")
    print("P5_02Q_RECOVERY_RECORD_VALID=true")
    print("P5_02Q_RECOVERY_MANIFEST_STATE=committed")
    print("P5_02Q_RECOVERY_CLASSIFICATION=committed")
    print("P5_02Q_RECEIPT_STATE=committed")
    print("P5_02Q_RECEIPT_FINALIZED=true")
    print("P5_02Q_RECEIPT_RECONCILIATION_REQUIRED=false")
    print("P5_02Q_APPROVAL_SURFACE=cli")
    print("P5_02Q_APPROVAL_CHOICE=once")
    print("P5_02Q_AUTHORIZATION_REUSABLE=false")
    print("P5_02Q_PRODUCTION_RECOVERY_COUNT_AFTER=1")
    print("P5_02Q_PRODUCTION_RECOVERY_ATTENTION_AFTER=0")
    print(f"P5_02Q_CANARY_POST_FILE_ID={post_file_id}")
    print(f"P5_02Q_CANARY_POST_SHA256={EXPECTED_AFTER_SHA256}")
    print("P5_02Q_MUTATION_MODE_AFTER=disabled")
    print("P5_02Q_AUTOMATIC_RESTORE=false")
    print("P5_02Q_RECOVERY_EVIDENCE_PRESERVED=true")
    print("HERMES_MANUAL_OFF=true")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02Q_PRODUCTION_CANARY_EDIT=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
