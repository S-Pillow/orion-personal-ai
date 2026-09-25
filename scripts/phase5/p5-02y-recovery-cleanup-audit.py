#!/usr/bin/env python3
"""P5-02Y exact audited recovery cleanup helper.

This helper never deletes recovery directories itself. It validates the exact
closed Phase 5 canary recovery set, writes/updates a durable audit record outside
the recovery root, and verifies the final empty-root post-state.

PowerShell owns the explicitly enumerated directory removals. This helper makes
that pruning restart-auditable by recording each successful removal durably.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_PLUGIN_VERSION = "p5-02v-0.3.0"
EXPECTED_SHA256 = (
    "132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132"
)
EXPECTED_SOURCE_FILE_ID = (
    "5e1aeb8a1aeb5d91:67660100000036010000000000000000"
)
EXPECTED_EDIT_CANARY_SHA256 = (
    "ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c"
)

EXPECTED_SOURCE = Path(r"C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md")
EXPECTED_TARGET = Path(r"C:\Personal\Me\_Orion-P5-Move-Canary.md")
EXPECTED_EDIT_CANARY = Path(r"C:\Personal\Me\_Orion-P5-Canary.md")

EXPECTED_RECORDS: dict[str, tuple[str, str]] = {
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f":
        ("edit_note", "committed_then_changed"),
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27":
        ("restore_edit", "committed"),
    "8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6":
        ("move_draft", "committed_then_changed"),
    "5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175":
        ("restore_move_source", "committed"),
    "e48123ceecc2be50afb2902511f64397f5dcfa35338ab9fd785cbf7278658b36":
        ("delete_note", "committed"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "orion_p5_02y_cleanup_audit", plugin_file
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed plugin import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def durable_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def read_audit(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("audit record is not a JSON object")
    return value


def inventory_directory(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = path.resolve(strict=True)
    for item in sorted(path.rglob("*"), key=lambda p: str(p).lower()):
        if item.is_symlink():
            raise RuntimeError(f"recovery artifact is symlink/reparse-like: {item}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise RuntimeError(f"unexpected recovery artifact type: {item}")
        rel = item.resolve(strict=True).relative_to(root).as_posix()
        data = item.read_bytes()
        rows.append(
            {
                "relative_path": rel,
                "size": len(data),
                "sha256": sha256_bytes(data),
            }
        )
    return rows


def load_runtime(
    profile: Path, plugin_dir: Path, recovery_root: Path
) -> tuple[Any, dict[str, Any]]:
    for name in (
        "ORION_P5_PRODUCTION_RECOVERY_ROOT",
        "ORION_P5_MUTATION_MODE",
        "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
        "ORION_P5_RECOVERY_ROOT",
    ):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"ambient Phase 5 setting present: {name}")

    os.environ["HERMES_HOME"] = str(profile)
    from hermes_cli.env_loader import load_hermes_dotenv

    loaded = load_hermes_dotenv(hermes_home=profile)
    if profile / ".env" not in [Path(p).resolve() for p in loaded]:
        raise RuntimeError("COMPANION .env not loaded")

    effective = (
        os.environ.get("ORION_P5_PRODUCTION_RECOVERY_ROOT") or ""
    ).strip()
    if not effective:
        raise RuntimeError("production recovery root not ingested")
    if Path(effective).resolve(strict=True) != recovery_root:
        raise RuntimeError("effective recovery root mismatch")
    if (os.environ.get("ORION_P5_MUTATION_MODE") or "").strip():
        raise RuntimeError("production mutation mode unexpectedly persisted")
    for name in ("ORION_P5_ALLOW_DISPOSABLE_MUTATION", "ORION_P5_RECOVERY_ROOT"):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"forbidden disposable setting persisted: {name}")

    plugin = load_plugin(plugin_dir)
    if plugin.PLUGIN_VERSION != EXPECTED_PLUGIN_VERSION:
        raise RuntimeError("installed plugin internal version mismatch")

    roots = plugin._validate_production_roots()
    if roots.get("success") is not True:
        raise RuntimeError(
            "native root validation failed: " + json.dumps(roots, sort_keys=True)
        )
    if roots.get("mutation_allowed") is not False:
        raise RuntimeError("native validator unexpectedly allows mutation")
    if Path(roots["recovery_root"]).resolve(strict=True) != recovery_root:
        raise RuntimeError("native recovery root mismatch")
    return plugin, roots


def validate_reference_state(plugin: Any) -> dict[str, Any]:
    if not EXPECTED_SOURCE.is_file():
        raise RuntimeError("restored inbox source missing")
    if EXPECTED_SOURCE.resolve(strict=True) != EXPECTED_SOURCE:
        raise RuntimeError("restored source canonical path mismatch")
    if plugin._path_has_reparse_component(EXPECTED_SOURCE):
        raise RuntimeError("restored source has a reparse component")
    source_sha = sha256_file(EXPECTED_SOURCE)
    if source_sha != EXPECTED_SHA256:
        raise RuntimeError("restored source hash mismatch")
    if os.name != "nt":
        raise RuntimeError("P5-02Y production cleanup is Windows-only")
    source_file_id = plugin._windows_path_file_identity(EXPECTED_SOURCE)
    if source_file_id != EXPECTED_SOURCE_FILE_ID:
        raise RuntimeError("restored source file identity mismatch")

    if os.path.lexists(EXPECTED_TARGET):
        raise RuntimeError("protected-delete target unexpectedly exists")

    if not EXPECTED_EDIT_CANARY.is_file():
        raise RuntimeError("edit canary missing")
    edit_sha = sha256_file(EXPECTED_EDIT_CANARY)
    if edit_sha != EXPECTED_EDIT_CANARY_SHA256:
        raise RuntimeError("edit canary hash mismatch")

    return {
        "source_path": str(EXPECTED_SOURCE),
        "source_sha256": source_sha,
        "source_file_id": source_file_id,
        "target_path": str(EXPECTED_TARGET),
        "target_state": "absent",
        "edit_canary_path": str(EXPECTED_EDIT_CANARY),
        "edit_canary_sha256": edit_sha,
    }


def validate_exact_inventory(
    plugin: Any, recovery_root: Path
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    inventory = plugin._enumerate_production_recovery_records()
    if (
        inventory.get("success") is not True
        or inventory.get("record_count") != 5
        or inventory.get("attention_count") != 0
        or inventory.get("truncated") is not False
    ):
        raise RuntimeError(
            "recovery inventory is not exact five/zero-attention baseline"
        )

    records: dict[str, dict[str, Any]] = {}
    for row in inventory.get("records") or []:
        recovery_id = row.get("recovery_id")
        if not isinstance(recovery_id, str) or recovery_id in records:
            raise RuntimeError("recovery inventory has invalid/duplicate id")
        records[recovery_id] = row

    if set(records) != set(EXPECTED_RECORDS):
        raise RuntimeError("recovery id set differs from approved cleanup set")

    audit_rows: list[dict[str, Any]] = []
    for recovery_id in sorted(EXPECTED_RECORDS):
        expected_action, expected_classification = EXPECTED_RECORDS[recovery_id]
        row = records[recovery_id]
        recovery = row.get("recovery")
        receipt = row.get("receipt")
        if (
            row.get("valid") is not True
            or row.get("needs_attention") is not False
            or not isinstance(recovery, dict)
            or not isinstance(receipt, dict)
        ):
            raise RuntimeError(f"record invalid/attention: {recovery_id}")
        if (
            recovery.get("success") is not True
            or recovery.get("action") != expected_action
            or recovery.get("manifest_state") != "committed"
            or recovery.get("classification") != expected_classification
            or recovery.get("recovery_required") is not False
        ):
            raise RuntimeError(f"recovery state mismatch: {recovery_id}")
        if (
            receipt.get("success") is not True
            or receipt.get("correlation_valid") is not True
            or receipt.get("authorization_reusable") is not False
            or receipt.get("recovery_required") is not False
            or receipt.get("receipt_state") != "committed"
            or receipt.get("receipt_finalized") is not True
            or receipt.get("receipt_reconciliation_required") is not False
            or receipt.get("current_classification")
            != expected_classification
        ):
            raise RuntimeError(f"receipt state mismatch: {recovery_id}")

        recovery_dir = recovery_root / recovery_id
        if not recovery_dir.is_dir():
            raise RuntimeError(f"recovery directory missing: {recovery_id}")

        audit_rows.append(
            {
                "recovery_id": recovery_id,
                "action": expected_action,
                "classification": expected_classification,
                "manifest_state": recovery.get("manifest_state"),
                "recovery_required": False,
                "receipt_state": receipt.get("receipt_state"),
                "receipt_finalized": receipt.get("receipt_finalized"),
                "receipt_reconciliation_required":
                    receipt.get("receipt_reconciliation_required"),
                "approval_surface": receipt.get("approval_surface"),
                "approval_choice": receipt.get("approval_choice"),
                "files": inventory_directory(recovery_dir),
            }
        )

    return records, audit_rows


def cmd_prepare(args: argparse.Namespace) -> int:
    profile = args.profile.resolve(strict=True)
    plugin_dir = args.plugin_dir.resolve(strict=True)
    recovery_root = args.recovery_root.resolve(strict=True)
    audit_path = args.audit_path.resolve(strict=False)

    if recovery_root in audit_path.parents or audit_path == recovery_root:
        raise RuntimeError("audit path must be outside production recovery root")

    plugin, _roots = load_runtime(profile, plugin_dir, recovery_root)
    reference = validate_reference_state(plugin)
    _records, audit_rows = validate_exact_inventory(plugin, recovery_root)

    if audit_path.exists():
        raise RuntimeError("audit path already exists")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "gate": "P5-02Y",
        "status": "prepared",
        "created_at_utc": utc_now(),
        "completed_at_utc": None,
        "policy": {
            "kind": "exact_count_exact_id",
            "approved_record_count": 5,
            "approved_recovery_ids": sorted(EXPECTED_RECORDS),
            "automatic_pruning": False,
            "unresolved_records_allowed": False,
            "attention_records_allowed": False,
            "owner_authorization_scope":
                "Phase 5 canary closure recovery cleanup",
        },
        "pre_state": reference,
        "records": audit_rows,
        "removed": [],
        "post_state": None,
    }
    durable_json_write(audit_path, payload)

    print("P5_02Y_AUDIT_PREPARE=PASS")
    print(f"P5_02Y_AUDIT_PATH={audit_path}")
    print(f"P5_02Y_AUDIT_SHA256_PREPARED={sha256_file(audit_path)}")
    print("P5_02Y_POLICY_KIND=exact_count_exact_id")
    print("P5_02Y_APPROVED_RECOVERY_COUNT=5")
    print("P5_02Y_RECOVERY_ATTENTION_COUNT=0")
    print("P5_02Y_UNRESOLVED_RECORDS=0")
    print("P5_02Y_REFERENCE_SOURCE_VALID=true")
    print("P5_02Y_REFERENCE_TARGET_ABSENT=true")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    audit_path = args.audit_path.resolve(strict=True)
    recovery_id = args.recovery_id
    if recovery_id not in EXPECTED_RECORDS:
        raise RuntimeError("recovery id is not in approved cleanup set")

    payload = read_audit(audit_path)
    if payload.get("gate") != "P5-02Y" or payload.get("status") != "prepared":
        raise RuntimeError("audit is not in prepared state")
    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise RuntimeError("audit policy missing")
    if sorted(policy.get("approved_recovery_ids") or []) != sorted(
        EXPECTED_RECORDS
    ):
        raise RuntimeError("audit approved-id set mismatch")

    removed = payload.get("removed")
    if not isinstance(removed, list):
        raise RuntimeError("audit removed journal invalid")
    existing_ids = {
        row.get("recovery_id")
        for row in removed
        if isinstance(row, dict)
    }
    if recovery_id in existing_ids:
        raise RuntimeError("recovery id already journaled as removed")

    removed.append(
        {
            "recovery_id": recovery_id,
            "removed_at_utc": utc_now(),
        }
    )
    payload["removed"] = removed
    durable_json_write(audit_path, payload)

    print("P5_02Y_AUDIT_RECORD_REMOVAL=PASS")
    print(f"P5_02Y_REMOVED_RECOVERY_ID={recovery_id}")
    print(f"P5_02Y_AUDIT_SHA256_PROGRESS={sha256_file(audit_path)}")
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    profile = args.profile.resolve(strict=True)
    plugin_dir = args.plugin_dir.resolve(strict=True)
    recovery_root = args.recovery_root.resolve(strict=True)
    audit_path = args.audit_path.resolve(strict=True)

    payload = read_audit(audit_path)
    if payload.get("gate") != "P5-02Y" or payload.get("status") != "prepared":
        raise RuntimeError("audit is not in prepared state")

    removed = payload.get("removed")
    if not isinstance(removed, list):
        raise RuntimeError("audit removed journal invalid")
    removed_ids = [
        row.get("recovery_id")
        for row in removed
        if isinstance(row, dict)
    ]
    if len(removed_ids) != 5 or set(removed_ids) != set(EXPECTED_RECORDS):
        raise RuntimeError("audit removal journal is not complete/exact")

    remaining = list(recovery_root.iterdir())
    if remaining:
        raise RuntimeError(
            "production recovery root is not empty after exact cleanup"
        )

    plugin, _roots = load_runtime(profile, plugin_dir, recovery_root)
    reference = validate_reference_state(plugin)

    inventory = plugin._enumerate_production_recovery_records()
    if (
        inventory.get("success") is not True
        or inventory.get("record_count") != 0
        or inventory.get("attention_count") != 0
        or inventory.get("truncated") is not False
    ):
        raise RuntimeError("native recovery inventory not clean/empty after cleanup")

    payload["status"] = "committed"
    payload["completed_at_utc"] = utc_now()
    payload["post_state"] = {
        **reference,
        "production_recovery_count": 0,
        "production_recovery_attention": 0,
    }
    durable_json_write(audit_path, payload)

    print("P5_02Y_AUDIT_FINALIZE=PASS")
    print(f"P5_02Y_AUDIT_PATH={audit_path}")
    print(f"P5_02Y_AUDIT_SHA256_FINAL={sha256_file(audit_path)}")
    print("P5_02Y_AUDIT_STATUS=committed")
    print("P5_02Y_PRODUCTION_RECOVERY_COUNT_AFTER=0")
    print("P5_02Y_PRODUCTION_RECOVERY_ATTENTION_AFTER=0")
    print("P5_02Y_REFERENCE_SOURCE_VALID_AFTER=true")
    print("P5_02Y_REFERENCE_TARGET_ABSENT_AFTER=true")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("profile", type=Path)
    prepare.add_argument("plugin_dir", type=Path)
    prepare.add_argument("recovery_root", type=Path)
    prepare.add_argument("audit_path", type=Path)
    prepare.set_defaults(func=cmd_prepare)

    record = sub.add_parser("record")
    record.add_argument("audit_path", type=Path)
    record.add_argument("recovery_id")
    record.set_defaults(func=cmd_record)

    finalize = sub.add_parser("finalize")
    finalize.add_argument("profile", type=Path)
    finalize.add_argument("plugin_dir", type=Path)
    finalize.add_argument("recovery_root", type=Path)
    finalize.add_argument("audit_path", type=Path)
    finalize.set_defaults(func=cmd_finalize)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02Y_AUDIT_HELPER=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
