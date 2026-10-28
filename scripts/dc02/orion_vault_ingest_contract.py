"""DC-02 cross-module fail-closed transaction contract."""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Iterable, Mapping

import orion_vault_ingest_fs as _fs
import orion_vault_ingest_state as _state
from orion_vault_ingest_model import (
    AdapterError,
    NoteSnapshot,
    SyncPlan,
    canonical_path,
    vault_root_text,
)

_DB_IDENTITY_KEY = "semantic_db_identity"


def _normalize_db_identity(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdapterError(f"{label}_semantic_db_identity_invalid")
    path = value.get("path")
    device = value.get("device")
    inode = value.get("inode")
    if not isinstance(path, str) or not path:
        raise AdapterError(f"{label}_semantic_db_identity_invalid")
    if not isinstance(device, int) or isinstance(device, bool) or device < 0:
        raise AdapterError(f"{label}_semantic_db_identity_invalid")
    if not isinstance(inode, int) or isinstance(inode, bool) or inode <= 0:
        raise AdapterError(f"{label}_semantic_db_identity_invalid")
    return {"path": path, "device": device, "inode": inode}


def semantic_db_identity(db_path: Path) -> dict[str, Any]:
    """Return the stable filesystem identity of the canonical semantic DB file."""
    db = Path(db_path)
    if not os.path.lexists(db):
        raise AdapterError(f"semantic_db_identity_missing:{db}")
    if _fs._is_reparse_point(db.parent):
        raise AdapterError(f"semantic_store_hippo_is_reparse_point:{db.parent}")
    _fs._validate_fixed_file(db, "semantic_db")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd: int | None = None
    try:
        fd = os.open(str(db), flags)
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise AdapterError(f"semantic_db_not_regular:{db}")
        if getattr(opened, "st_nlink", 1) > 1:
            raise AdapterError(f"semantic_db_has_multiple_links:{db}")
        if not isinstance(opened.st_ino, int) or opened.st_ino <= 0:
            raise AdapterError("semantic_db_file_identity_unavailable")
        try:
            path_info = os.stat(db, follow_symlinks=False)
            resolved = db.resolve(strict=True)
        except OSError as exc:
            raise AdapterError(
                f"semantic_db_identity_stat_failed:{type(exc).__name__}"
            ) from exc
        if (
            path_info.st_dev != opened.st_dev
            or path_info.st_ino != opened.st_ino
            or getattr(path_info, "st_nlink", 1) > 1
        ):
            raise AdapterError("semantic_db_changed_during_identity_check")
        return {
            "path": str(resolved),
            "device": int(opened.st_dev),
            "inode": int(opened.st_ino),
        }
    except AdapterError:
        raise
    except OSError as exc:
        raise AdapterError(
            f"semantic_db_identity_open_failed:{type(exc).__name__}"
        ) from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def assert_semantic_db_identity(
    db_path: Path, expected: Mapping[str, Any]
) -> dict[str, Any]:
    wanted = _normalize_db_identity(expected, label="expected")
    current = semantic_db_identity(db_path)
    if current != wanted:
        raise AdapterError("semantic_db_identity_mismatch")
    return current


def _effective_db_identity(
    store_root: Path,
    supplied: Mapping[str, Any] | None,
    *,
    required: bool,
) -> dict[str, Any] | None:
    store = canonical_path(store_root)
    db = store / "hippo" / "brain.sqlite3"
    if supplied is not None:
        identity = _normalize_db_identity(supplied, label="supplied")
        expected_path = str(db.resolve(strict=True)) if db.exists() else str(db)
        if os.path.normcase(identity["path"]) != os.path.normcase(expected_path):
            raise AdapterError("semantic_db_identity_store_mismatch")
        return identity
    if db.exists():
        return semantic_db_identity(db)
    if required:
        raise AdapterError("semantic_db_identity_required")
    return None


def _require_stored_db_identity(
    payload: Mapping[str, Any],
    expected: Mapping[str, Any] | None,
    *,
    label: str,
) -> dict[str, Any]:
    wanted = _normalize_db_identity(expected, label="expected")
    stored = _normalize_db_identity(payload.get(_DB_IDENTITY_KEY), label=label)
    if stored != wanted:
        raise AdapterError(f"{label}_semantic_db_identity_mismatch")
    return stored


def validate_store(vault_root: Path, store_root: Path, *, require_db: bool) -> Path:
    """Require one physical semantic DB, one lock namespace, and no vault overlap."""
    store = canonical_path(store_root)
    vault = Path(vault_root_text(vault_root))
    if _fs._contained(store, vault) or _fs._contained(vault, store):
        raise AdapterError("vault_store_overlap")
    hippo = store / "hippo"
    if os.path.lexists(hippo):
        if _fs._is_reparse_point(hippo):
            raise AdapterError(f"semantic_store_hippo_is_reparse_point:{hippo}")
        try:
            info = os.lstat(hippo)
        except OSError as exc:
            raise AdapterError(
                f"semantic_store_hippo_stat_failed:{type(exc).__name__}"
            ) from exc
        if not stat.S_ISDIR(info.st_mode):
            raise AdapterError(f"semantic_store_hippo_not_directory:{hippo}")
    db = _fs.validate_store(vault_root, store, require_db=require_db)
    if db.exists():
        db_real = db.resolve(strict=True)
        if _fs._contained(db_real, vault):
            raise AdapterError("semantic_db_inside_vault")
    return db


def load_state(
    path: Path,
    vault_root: Path,
    store_root: Path,
    *,
    db_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load only a successful checkpoint bound to the current semantic DB file."""
    persisted = os.path.lexists(path)
    state = _state.load_state(path, vault_root, store_root)
    if not persisted:
        return state
    if state.get("successful_run_utc") is None:
        raise AdapterError("state_success_timestamp_invalid")
    expected = _effective_db_identity(store_root, db_identity, required=True)
    _require_stored_db_identity(state, expected, label="state")
    return state


def _state_payload(
    vault_root: Path,
    store_root: Path,
    notes: Iterable[NoteSnapshot],
    doc_tags: Mapping[str, str],
    checkpoint_id: str,
    *,
    db_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _state._state_payload(
        vault_root, store_root, notes, doc_tags, checkpoint_id
    )
    payload[_DB_IDENTITY_KEY] = _effective_db_identity(
        store_root, db_identity, required=False
    )
    return payload


def _pending_payload(
    vault_root: Path,
    store_root: Path,
    state: Mapping[str, Any],
    notes: Iterable[NoteSnapshot],
    doc_tags: Mapping[str, str],
    plan: SyncPlan,
    target_checkpoint_id: str,
    *,
    recovery_doc_tags: Mapping[str, str] | None = None,
    db_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _state._pending_payload(
        vault_root,
        store_root,
        state,
        notes,
        doc_tags,
        plan,
        target_checkpoint_id,
        recovery_doc_tags=recovery_doc_tags,
    )
    payload[_DB_IDENTITY_KEY] = _effective_db_identity(
        store_root, db_identity, required=True
    )
    return payload


def load_pending(
    path: Path,
    vault_root: Path,
    store_root: Path,
    state: Mapping[str, Any],
    current_doc_tags: Mapping[str, str],
    doc_tag_fn: Any,
    *,
    db_identity: Mapping[str, Any] | None = None,
):
    if not os.path.lexists(path):
        return _state.load_pending(
            path, vault_root, store_root, state, current_doc_tags, doc_tag_fn
        )
    raw = _state._read_json_file(path, "pending")
    expected = _effective_db_identity(store_root, db_identity, required=True)
    _require_stored_db_identity(raw, expected, label="pending")
    return _state.load_pending(
        path, vault_root, store_root, state, current_doc_tags, doc_tag_fn
    )


def owner_payload(
    vault_root: Path,
    store_root: Path,
    *,
    db_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _state.owner_payload(vault_root, store_root)
    payload[_DB_IDENTITY_KEY] = _effective_db_identity(
        store_root, db_identity, required=True
    )
    return payload


def load_owner(
    path: Path,
    vault_root: Path,
    store_root: Path,
    *,
    db_identity: Mapping[str, Any] | None = None,
):
    if not os.path.lexists(path):
        return _state.load_owner(path, vault_root, store_root)
    raw = _state._read_json_file(path, "owner")
    expected = _effective_db_identity(store_root, db_identity, required=True)
    _require_stored_db_identity(raw, expected, label="owner")
    return _state.load_owner(path, vault_root, store_root)
