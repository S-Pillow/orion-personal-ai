#!/usr/bin/env python3
"""P5-02S-B read-only production move readiness verifier.

This script never enables mutation and never invokes the apply tool. It
validates the accepted P5-02R baseline, the controlled inbox draft fixture, an
absent vault target, and the exact registered move preview contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


PREVIEW_MOVE_TOOL = "orion_vault_preview_move_draft"
SOURCE_RELATIVE_PATH = "_Orion-P5-Move-Canary.md"
TARGET_RELATIVE_PATH = "_Orion-P5-Move-Canary.md"
EXPECTED_SOURCE_PATH = Path(r"C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md")
EXPECTED_TARGET_PATH = Path(r"C:\Personal\Me\_Orion-P5-Move-Canary.md")

ORIGIN_EDIT_RECOVERY_ID = (
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f"
)
RESTORE_RECOVERY_ID = (
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27"
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
        rid = record.get("recovery_id")
        if not isinstance(rid, str) or rid in indexed:
            raise RuntimeError("recovery inventory id invalid/duplicate")
        indexed[rid] = record
    return indexed


def require_historical_baseline(records: dict[str, dict]) -> None:
    if set(records) != {ORIGIN_EDIT_RECOVERY_ID, RESTORE_RECOVERY_ID}:
        raise RuntimeError("production recovery id set differs from accepted P5-02R state")

    origin = records[ORIGIN_EDIT_RECOVERY_ID]
    restore = records[RESTORE_RECOVERY_ID]
    for record in (origin, restore):
        if record.get("valid") is not True or record.get("needs_attention") is not False:
            raise RuntimeError("production recovery baseline contains invalid/attention record")

    origin_recovery = origin.get("recovery")
    origin_receipt = origin.get("receipt")
    restore_recovery = restore.get("recovery")
    restore_receipt = restore.get("receipt")
    if not all(
        isinstance(x, dict)
        for x in (origin_recovery, origin_receipt, restore_recovery, restore_receipt)
    ):
        raise RuntimeError("production recovery baseline inspection missing")

    if (
        origin_recovery.get("manifest_state") != "committed"
        or origin_recovery.get("classification") != "committed_then_changed"
        or origin_recovery.get("recovery_required") is not False
        or origin_receipt.get("receipt_state") != "committed"
        or origin_receipt.get("receipt_finalized") is not True
        or origin_receipt.get("receipt_reconciliation_required") is not False
        or origin_receipt.get("current_classification") != "committed_then_changed"
    ):
        raise RuntimeError("P5-02Q origin record differs from accepted post-restore state")

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    parser.add_argument("expected_recovery_root", type=Path)
    args = parser.parse_args()

    profile = args.profile.resolve(strict=True)
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
    from tools.registry import registry

    loaded = load_hermes_dotenv(hermes_home=profile)
    if profile / ".env" not in [Path(p).resolve() for p in loaded]:
        raise RuntimeError("Hermes loader did not report COMPANION .env as loaded")

    if (os.environ.get("ORION_P5_MUTATION_MODE") or "").strip():
        raise RuntimeError("production mutation mode unexpectedly persisted")
    for name in ("ORION_P5_ALLOW_DISPOSABLE_MUTATION", "ORION_P5_RECOVERY_ROOT"):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"disposable mutation setting unexpectedly persisted: {name}")

    discover_plugins()
    preview_entry = registry.get_entry(PREVIEW_MOVE_TOOL)
    if preview_entry is None:
        raise RuntimeError("registered Orion move-preview tool unavailable")
    if preview_entry.handler.__name__ != "preview_move_draft":
        raise RuntimeError("registered move-preview handler identity mismatch")

    plugin = sys.modules.get(preview_entry.handler.__module__)
    if plugin is None:
        raise RuntimeError("installed Orion plugin module unavailable")
    if preview_entry.handler is not plugin.preview_move_draft:
        raise RuntimeError("registered move-preview handler object mismatch")

    mode = plugin._production_mutation_mode()
    if (
        mode.get("valid") is not True
        or mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED
        or mode.get("mutation_allowed") is not False
    ):
        raise RuntimeError(f"unexpected production mutation mode: {mode}")

    roots = plugin._validate_production_roots()
    if roots.get("success") is not True or roots.get("mutation_allowed") is not False:
        raise RuntimeError("native production-root validation failed read-only")

    vault_root = Path(roots["vault_root"]).resolve(strict=True)
    inbox_root = Path(roots["inbox_root"]).resolve(strict=True)
    recovery_root = Path(roots["recovery_root"]).resolve(strict=True)
    if recovery_root != expected_recovery_root:
        raise RuntimeError("native recovery-root mismatch")

    inventory_before = plugin._enumerate_production_recovery_records()
    if (
        inventory_before.get("success") is not True
        or inventory_before.get("record_count") != 2
        or inventory_before.get("attention_count") != 0
        or inventory_before.get("truncated") is not False
    ):
        raise RuntimeError("production recovery inventory differs from accepted P5-02R baseline")
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

    raw_preview = handle_function_call(
        PREVIEW_MOVE_TOOL,
        {
            "source_draft": SOURCE_RELATIVE_PATH,
            "target_relative_path": TARGET_RELATIVE_PATH,
        },
        task_id="p5-02s-move-preview",
        session_id="p5-02s-move-preview",
        tool_call_id="p5-02s-move-preview-call",
        turn_id="p5-02s-move-preview-turn",
        user_task="P5-02S exact production move readiness preview",
        enabled_tools=[PREVIEW_MOVE_TOOL],
        enabled_toolsets=["orion_vault"],
    )
    preview = parse_json_result(raw_preview, label="move preview")
    if preview.get("success") is not True or preview.get("mutation_performed") is not False:
        raise RuntimeError("registered move preview did not succeed read-only")

    plan = preview.get("plan")
    diff_text = preview.get("diff")
    if not isinstance(plan, dict) or not isinstance(diff_text, str):
        raise RuntimeError("move preview contract missing plan/diff")
    if plan.get("action") != "move_draft":
        raise RuntimeError("move preview action mismatch")
    if plan.get("source_draft") != SOURCE_RELATIVE_PATH:
        raise RuntimeError("move preview source-relative mismatch")
    if plan.get("source_canonical_path") != str(EXPECTED_SOURCE_PATH):
        raise RuntimeError("move preview source-canonical mismatch")
    if plan.get("target_relative_path") != TARGET_RELATIVE_PATH:
        raise RuntimeError("move preview target-relative mismatch")
    if plan.get("target_candidate_path") != str(EXPECTED_TARGET_PATH):
        raise RuntimeError("move preview target candidate mismatch")
    if plan.get("target_canonical_path") != str(EXPECTED_TARGET_PATH):
        raise RuntimeError("move preview target canonical mismatch")
    if plan.get("target_existing_ancestor_canonical_path") != str(vault_root):
        raise RuntimeError("move preview target ancestor mismatch")
    if plan.get("target_state") != "absent":
        raise RuntimeError("move preview target state is not absent")
    if plan.get("source_sha256") != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("move preview source hash mismatch")
    if plan.get("source_file_id") != source_file_id:
        raise RuntimeError("move preview source file identity mismatch")
    if plan.get("diff_sha256") != EXPECTED_DIFF_SHA256:
        raise RuntimeError("move preview diff hash mismatch")
    if sha256(diff_text.encode("utf-8")) != EXPECTED_DIFF_SHA256:
        raise RuntimeError("move preview exact diff differs from frozen contract")

    if source.read_bytes() != SOURCE_BYTES:
        raise RuntimeError("source bytes changed during side-effect-free preview")
    if plugin._windows_path_file_identity(source) != source_file_id:
        raise RuntimeError("source file identity changed during preview")
    if os.path.lexists(target):
        raise RuntimeError("target appeared during side-effect-free preview")

    inventory_after = plugin._enumerate_production_recovery_records()
    if (
        inventory_after.get("success") is not True
        or inventory_after.get("record_count") != 2
        or inventory_after.get("attention_count") != 0
        or inventory_after.get("truncated") is not False
    ):
        raise RuntimeError("recovery inventory changed during move preview")
    require_historical_baseline(index_records(inventory_after))

    print("P5_02S_MOVE_READINESS=PASS")
    print("P5_02S_MUTATION_MODE=disabled")
    print("P5_02S_MUTATION_ALLOWED=false")
    print("P5_02S_RECOVERY_INVENTORY_COUNT=2")
    print("P5_02S_RECOVERY_ATTENTION_COUNT=0")
    print(f"P5_02S_SOURCE_RELATIVE_PATH={SOURCE_RELATIVE_PATH}")
    print(f"P5_02S_SOURCE_CANONICAL_PATH={source.resolve(strict=True)}")
    print(f"P5_02S_SOURCE_FILE_ID={source_file_id}")
    print(f"P5_02S_SOURCE_SHA256={EXPECTED_SOURCE_SHA256}")
    print(f"P5_02S_TARGET_RELATIVE_PATH={TARGET_RELATIVE_PATH}")
    print(f"P5_02S_TARGET_CANONICAL_PATH={EXPECTED_TARGET_PATH}")
    print("P5_02S_TARGET_STATE=absent")
    print(f"P5_02S_MOVE_DIFF_SHA256={EXPECTED_DIFF_SHA256}")
    print("P5_02S_PREVIEW_MUTATION=false")
    print("P5_02S_SOURCE_UNCHANGED=true")
    print("P5_02S_TARGET_STILL_ABSENT=true")
    print("P5_02S_EXACT_DIFF_BEGIN")
    print(diff_text, end="" if diff_text.endswith("\n") else "\n")
    print("P5_02S_EXACT_DIFF_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02S_MOVE_READINESS=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
