#!/usr/bin/env python3
"""Public DC-02 Markdown-only native iai transaction coordinator."""
from __future__ import annotations

import importlib.util
import json
import secrets
import sys
from pathlib import Path

_CORE_PATH = Path(__file__).with_name("orion_vault_markdown_ingest_core.py")
_SPEC = importlib.util.spec_from_file_location("orion_vault_markdown_ingest_core", _CORE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"dc02_core_import_unavailable:{_CORE_PATH}")
core = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = core
_SPEC.loader.exec_module(core)

AdapterError = core.AdapterError


def _open_and_apply(runtime, store_root: Path, staged, plan):
    try:
        store = runtime.open_store(store_root)
    except Exception as exc:
        raise AdapterError(f"store_open_failed:{type(exc).__name__}:{exc}") from exc
    try:
        reports = core.apply_plan(store, staged.paths, plan, runtime.study_document)
    except Exception as apply_exc:
        try:
            store.close()
        except Exception as close_exc:
            raise AdapterError(
                f"store_close_failed_after_apply_error:{type(close_exc).__name__}"
            ) from apply_exc
        raise
    try:
        store.close()
    except Exception as exc:
        raise AdapterError(f"store_close_failed:{type(exc).__name__}") from exc
    return reports


def main(argv: list[str] | None = None) -> int:
    args = core.parse_args(argv)
    vault_root = args.vault_root.expanduser()
    store_root = args.store_root.expanduser()
    paths = None
    lock = None
    staged = None
    try:
        paths = core.metadata_paths(store_root)
        runtime = core.load_iai_runtime()
        core.validate_store(vault_root, store_root, require_db=args.apply)
        core.validate_metadata_namespace(paths, vault_root, store_root)
        if args.apply:
            lock = core.acquire_apply_lock(paths.lock)
            core.validate_metadata_namespace(paths, vault_root, store_root)

        state = core.load_state(paths.state, vault_root, store_root)
        owner = core.load_owner(paths.owner, vault_root, store_root)
        if owner is not None and not paths.state.exists() and not paths.pending.exists():
            raise AdapterError("owned_store_missing_state_and_pending")

        notes = core.scan_markdown_vault(
            vault_root,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
        )
        if args.expected_files is not None and len(notes) != args.expected_files:
            raise AdapterError(
                f"expected_file_count_mismatch:{len(notes)}!={args.expected_files}"
            )
        doc_tags = core.validate_doc_tags(notes, state, runtime.doc_tag)
        pending = core.load_pending(
            paths.pending,
            vault_root,
            store_root,
            state,
            doc_tags,
            runtime.doc_tag,
        )

        if args.apply and pending.status == "completed":
            core.clear_pending(paths.pending)
            pending = core.PendingStatus("none", (), {})

        plan = core.build_plan(notes, state)
        if pending.status == "active":
            plan = core.reconcile_active_pending(plan, notes, state, pending.paths)

        if not args.apply:
            payload = core.result_payload(
                runtime,
                vault_root,
                store_root,
                paths,
                notes,
                plan,
                doc_tags,
                False,
                pending.status,
            )
            print(json.dumps(payload, indent=2))
            if not args.json:
                print("ORION_VAULT_MARKDOWN_INGEST=PLAN_PASS")
            return 0

        reports = {"studied": {}, "faded": {}}
        checkpoint_id = str(state["checkpoint_id"])
        if plan.mutation_count:
            # Freeze all studied inputs before journal/store mutation. From this
            # point the semantic transaction is defined by the admitted snapshot,
            # not by subsequent edits to the live vault.
            staged = core.stage_plan_sources(vault_root, store_root, notes, plan)
            core.validate_deleted_absence(vault_root, plan)
            target_checkpoint_id = secrets.token_hex(32)
            core._atomic_write(
                paths.pending,
                core._pending_payload(
                    vault_root,
                    store_root,
                    state,
                    notes,
                    doc_tags,
                    plan,
                    target_checkpoint_id,
                    recovery_doc_tags=pending.doc_tags if pending.status == "active" else None,
                ),
                "pending",
            )
            if owner is None:
                core._atomic_write(paths.owner, core.owner_payload(vault_root, store_root), "owner")
                owner = core.owner_payload(vault_root, store_root)
            core.validate_store(vault_root, store_root, require_db=True)
            reports = _open_and_apply(runtime, core.canonical_path(store_root), staged, plan)
            checkpoint_id = target_checkpoint_id

        core._atomic_write(
            paths.state,
            core._state_payload(vault_root, store_root, notes, doc_tags, checkpoint_id),
            "state",
        )
        if owner is None:
            core._atomic_write(paths.owner, core.owner_payload(vault_root, store_root), "owner")
        core.clear_pending(paths.pending)

        payload = core.result_payload(
            runtime,
            vault_root,
            store_root,
            paths,
            notes,
            plan,
            doc_tags,
            True,
            "none",
            reports,
        )
        print(json.dumps(payload, indent=2))
        if not args.json:
            print("ORION_VAULT_MARKDOWN_INGEST=APPLY_PASS")
        return 0
    except AdapterError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"status": "error", "error": str(exc)}))
        else:
            print(f"ORION_VAULT_MARKDOWN_INGEST=FAIL:{exc}", file=sys.stderr)
        return 1
    finally:
        if staged is not None:
            try:
                staged.close()
            except OSError as exc:
                print(
                    f"ORION_VAULT_MARKDOWN_INGEST=STAGE_CLEANUP_WARNING:{type(exc).__name__}",
                    file=sys.stderr,
                )
        if lock is not None:
            try:
                lock.close()
            except OSError as exc:
                print(
                    f"ORION_VAULT_MARKDOWN_INGEST=LOCK_RELEASE_WARNING:{type(exc).__name__}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())
