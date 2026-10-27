#!/usr/bin/env python3
"""Orion DC-02 hardened transaction coordinator.

The implementation primitives live in ``orion_vault_markdown_ingest_core.py``.
This public entry point adds durable store ownership and coordinates recovery so
metadata is durable before any direct-store open/mutation can occur.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

_CORE_PATH = Path(__file__).with_name("orion_vault_markdown_ingest_core.py")
_CORE_SPEC = importlib.util.spec_from_file_location(
    "orion_vault_markdown_ingest_core", _CORE_PATH
)
if _CORE_SPEC is None or _CORE_SPEC.loader is None:
    raise RuntimeError(f"dc02_core_import_unavailable:{_CORE_PATH}")
_core = importlib.util.module_from_spec(_CORE_SPEC)
sys.modules[_CORE_SPEC.name] = _core
_CORE_SPEC.loader.exec_module(_core)

# Re-export the tested implementation surface so existing callers/tests continue
# to import this public module while the transaction coordinator remains small.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

STORE_OWNER_SCHEMA_VERSION = 1


def _store_owner_file_for(store_root: Path) -> Path:
    return Path(_canonical_path_text(store_root)) / "orion" / "vault-markdown-ingest-owner.json"


def _store_owner_payload(
    *, vault_root: Path, store_root: Path, state_file: Path
) -> dict[str, Any]:
    return {
        "schema_version": STORE_OWNER_SCHEMA_VERSION,
        "session_id": SESSION_ID,
        "vault_root": str(vault_root.resolve(strict=True)),
        "store_root": _canonical_path_text(store_root),
        "state_file": _canonical_path_text(state_file),
        "iai_version": EXPECTED_IAI_VERSION,
    }


def load_store_owner(
    owner_file: Path,
    *,
    vault_root: Path,
    store_root: Path,
    state_file: Path,
) -> dict[str, Any] | None:
    """Validate the durable one-vault/one-state ownership of the iai store."""
    if not owner_file.exists():
        return None
    try:
        raw = json.loads(owner_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"store_owner_read_failed:{type(exc).__name__}") from exc
    if not isinstance(raw, dict):
        raise AdapterError("store_owner_invalid_shape")
    if raw.get("schema_version") != STORE_OWNER_SCHEMA_VERSION:
        raise AdapterError("store_owner_schema_mismatch")
    if raw.get("session_id") != SESSION_ID:
        raise AdapterError("store_owner_session_mismatch")
    if raw.get("iai_version") != EXPECTED_IAI_VERSION:
        raise AdapterError("store_owner_iai_version_mismatch")

    expected_vault = str(vault_root.resolve(strict=True))
    stored_vault = str(raw.get("vault_root") or "")
    if os.path.normcase(stored_vault) != os.path.normcase(expected_vault):
        raise AdapterError(
            f"store_owner_vault_root_mismatch:{stored_vault}:{expected_vault}"
        )

    expected_store = _canonical_path_text(store_root)
    stored_store = str(raw.get("store_root") or "")
    if os.path.normcase(stored_store) != os.path.normcase(expected_store):
        raise AdapterError(
            f"store_owner_store_root_mismatch:{stored_store}:{expected_store}"
        )

    expected_state = _canonical_path_text(state_file)
    stored_state = str(raw.get("state_file") or "")
    if os.path.normcase(stored_state) != os.path.normcase(expected_state):
        raise AdapterError(
            f"store_owner_state_file_mismatch:{stored_state}:{expected_state}"
        )
    return raw


def write_store_owner_atomic(owner_file: Path, payload: Mapping[str, Any]) -> None:
    _write_atomic(owner_file, payload, "store_owner_write_failed")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    vault_root = args.vault_root.expanduser()
    store_root = args.store_root.expanduser()
    state_file = (
        args.state_file.expanduser()
        if args.state_file is not None
        else _default_state_file(store_root)
    )
    pending_file = _pending_file_for(state_file)
    state_lock_file = _apply_lock_file_for(state_file)
    store_lock_file = _store_apply_lock_file_for(store_root)
    owner_file = _store_owner_file_for(store_root)
    apply_locks: _ApplyLocksHandle | None = None

    try:
        runtime = load_iai_runtime()
        notes = scan_markdown_vault(
            vault_root, max_files=args.max_files, max_file_bytes=args.max_file_bytes
        )
        if args.expected_files is not None and len(notes) != args.expected_files:
            raise AdapterError(
                f"expected_file_count_mismatch:{len(notes)}!={args.expected_files}"
            )

        validate_state_location(state_file, vault_root)
        validate_state_location(pending_file, vault_root)
        validate_state_location(state_lock_file, vault_root)
        validate_state_location(store_lock_file, vault_root)
        validate_state_location(owner_file, vault_root)
        validate_store_location(store_root, vault_root)

        db_path = store_root / "hippo" / "brain.sqlite3"
        canonical_store_present = db_path.is_file()
        if args.apply:
            if not canonical_store_present:
                raise AdapterError(f"canonical_store_missing:{db_path}")
            apply_locks = _acquire_apply_locks((state_lock_file, store_lock_file))

        doc_tags = validate_doc_tag_uniqueness(notes, runtime.doc_tag)
        state = load_state(state_file, vault_root, store_root)
        validate_cross_generation_doc_tags(state, doc_tags, runtime.doc_tag)
        pending_paths, pending_status = load_pending_journal(
            pending_file,
            vault_root=vault_root,
            store_root=store_root,
            state=state,
            current_doc_tags=doc_tags,
            doc_tag_fn=runtime.doc_tag,
        )
        plan = build_plan(notes, state)
        if pending_status == "active":
            plan = reconcile_plan_with_pending(
                plan, notes=notes, state=state, pending_paths=pending_paths
            )

        owner = load_store_owner(
            owner_file,
            vault_root=vault_root,
            store_root=store_root,
            state_file=state_file,
        )

        if not args.apply:
            result = _json_result(
                runtime=runtime,
                vault_root=vault_root,
                store_root=store_root,
                state_file=state_file,
                notes=notes,
                doc_tags=doc_tags,
                plan=plan,
                applied=False,
                canonical_store_present=canonical_store_present,
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                _print_plan(
                    plan,
                    file_count=len(notes),
                    vault_root=vault_root,
                    store_root=store_root,
                    state_file=state_file,
                    iai_version=runtime.version,
                    apply=False,
                    canonical_store_present=canonical_store_present,
                )
                print("ORION_VAULT_MARKDOWN_INGEST_VAULT_MUTATION=false")
                print("ORION_VAULT_MARKDOWN_INGEST_STORE_MUTATION=false")
                print("ORION_VAULT_MARKDOWN_INGEST=PLAN_PASS")
            return 0

        # Claim an unowned store only after every source/state/pending preflight
        # has succeeded and while the store-wide lock is held. A crash after this
        # write is safe: it only reserves the store for the same configuration.
        if owner is None:
            write_store_owner_atomic(
                owner_file,
                _store_owner_payload(
                    vault_root=vault_root,
                    store_root=store_root,
                    state_file=state_file,
                ),
            )

        if pending_status == "completed":
            clear_pending_journal(pending_file)

        reports: dict[str, Any] = {"studied": {}, "faded": {}}
        checkpoint_id = _checkpoint_identity(state)
        if plan.mutation_count:
            target_checkpoint_id = secrets.token_hex(32)

            # The recovery journal must be durable before *opening* the native
            # store, not merely before study_document(). This keeps direct-store
            # recovery fail-closed even if store construction performs writes or
            # fails partway through initialization.
            write_pending_atomic(
                pending_file,
                _pending_payload(
                    vault_root=vault_root,
                    store_root=store_root,
                    state=state,
                    notes=notes,
                    doc_tags=doc_tags,
                    plan=plan,
                    iai_version=runtime.version,
                    doc_tag_fn=runtime.doc_tag,
                    target_checkpoint_id=target_checkpoint_id,
                ),
            )
            try:
                store = runtime.open_store(store_root)
            except Exception as exc:
                raise AdapterError(f"store_open_failed:{type(exc).__name__}:{exc}") from exc
            try:
                reports = apply_plan(
                    store=store,
                    vault_root=vault_root,
                    notes=notes,
                    plan=plan,
                    study_document=runtime.study_document,
                )
            except Exception as apply_exc:
                try:
                    store.close()
                except Exception as close_exc:
                    raise AdapterError(
                        f"store_close_failed_after_apply_error:{type(close_exc).__name__}"
                    ) from apply_exc
                raise
            else:
                try:
                    store.close()
                except Exception as exc:
                    raise AdapterError(f"store_close_failed:{type(exc).__name__}") from exc
            checkpoint_id = target_checkpoint_id
        elif pending_status != "completed" and state.get("successful_run_utc") is None:
            checkpoint_id = secrets.token_hex(32)

        final_notes = scan_markdown_vault(
            vault_root, max_files=args.max_files, max_file_bytes=args.max_file_bytes
        )
        if final_notes != notes:
            raise AdapterError("vault_changed_before_checkpoint")

        payload = _state_payload(
            vault_root,
            notes,
            doc_tags,
            runtime.version,
            checkpoint_id,
            store_root=store_root,
        )
        write_state_atomic(state_file, payload)
        clear_pending_journal(pending_file)

        result = _json_result(
            runtime=runtime,
            vault_root=vault_root,
            store_root=store_root,
            state_file=state_file,
            notes=notes,
            doc_tags=doc_tags,
            plan=plan,
            applied=True,
            canonical_store_present=True,
            reports=reports,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            _print_plan(
                plan,
                file_count=len(notes),
                vault_root=vault_root,
                store_root=store_root,
                state_file=state_file,
                iai_version=runtime.version,
                apply=True,
                canonical_store_present=True,
            )
            print("ORION_VAULT_MARKDOWN_INGEST_VAULT_MUTATION=false")
            print("ORION_VAULT_MARKDOWN_INGEST_STORE_MUTATION=true")
            print("ORION_VAULT_MARKDOWN_INGEST=APPLY_PASS")
        return 0
    except AdapterError as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}))
        else:
            print(f"ORION_VAULT_MARKDOWN_INGEST=FAIL:{exc}", file=sys.stderr)
        return 1
    finally:
        if apply_locks is not None:
            try:
                apply_locks.close()
            except OSError as exc:
                print(
                    f"ORION_VAULT_MARKDOWN_INGEST=LOCK_RELEASE_WARNING:{type(exc).__name__}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())
