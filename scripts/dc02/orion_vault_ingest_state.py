"""DC-02 successful checkpoint, ownership, planning, and explicit recovery journal."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from orion_vault_ingest_model import (
    AdapterError,
    EXPECTED_IAI_VERSION,
    OWNER_SCHEMA_VERSION,
    PENDING_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    SESSION_ID,
    PendingStatus,
    NoteSnapshot,
    SyncPlan,
    _SHA256_RE,
    canonical_path,
    validate_source_name,
    vault_root_text,
)


def _files_payload(notes: Iterable[NoteSnapshot], doc_tags: Mapping[str, str]) -> dict[str, Any]:
    return {
        note.relative_path: note.state_value(doc_tags[note.relative_path])
        for note in sorted(notes, key=lambda item: (item.relative_path.casefold(), item.relative_path))
    }


def _files_digest(files: Mapping[str, Any]) -> str:
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_utc_timestamp(value: Any, label: str, *, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, str) or not value:
        raise AdapterError(f"{label}_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdapterError(f"{label}_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        raise AdapterError(f"{label}_timestamp_invalid")


def _empty_state(vault_root: Path, store_root: Path) -> dict[str, Any]:
    vault = vault_root_text(vault_root)
    store = str(canonical_path(store_root))
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "session_id": SESSION_ID,
        "iai_version": EXPECTED_IAI_VERSION,
        "vault_root": vault,
        "store_root": store,
        "successful_run_utc": None,
        "checkpoint_id": hashlib.sha256((vault + "\0" + store).encode("utf-8")).hexdigest(),
        "files": {},
    }


def _read_json_file(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"{label}_read_failed:{type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise AdapterError(f"{label}_invalid_shape")
    return value


def _validate_file_map(files: Mapping[str, Any], *, label: str) -> None:
    seen_casefold: dict[str, str] = {}
    seen_tags: dict[str, str] = {}
    for rel, meta in files.items():
        if not isinstance(rel, str):
            raise AdapterError(f"{label}_source_name_invalid_type")
        validate_source_name(rel)
        folded = rel.casefold()
        prior = seen_casefold.get(folded)
        if prior is not None and prior != rel:
            raise AdapterError(f"{label}_casefold_collision:{prior}:{rel}")
        seen_casefold[folded] = rel
        if not isinstance(meta, Mapping):
            raise AdapterError(f"{label}_entry_invalid:{rel}")
        size, mtime_ns, digest, tag = (
            meta.get("size"), meta.get("mtime_ns"), meta.get("sha256"), meta.get("doc_tag")
        )
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise AdapterError(f"{label}_size_invalid:{rel}")
        if not isinstance(mtime_ns, int) or isinstance(mtime_ns, bool) or mtime_ns < 0:
            raise AdapterError(f"{label}_mtime_invalid:{rel}")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise AdapterError(f"{label}_sha256_invalid:{rel}")
        if not isinstance(tag, str) or not tag.startswith("doc:") or len(tag) <= 4:
            raise AdapterError(f"{label}_doc_tag_invalid:{rel}")
        owner = seen_tags.get(tag)
        if owner is not None and owner != rel:
            raise AdapterError(f"{label}_doc_tag_collision:{tag}:{owner}:{rel}")
        seen_tags[tag] = rel


def load_state(path: Path, vault_root: Path, store_root: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_state(vault_root, store_root)
    raw = dict(_read_json_file(path, "state"))
    if raw.get("schema_version") != STATE_SCHEMA_VERSION:
        raise AdapterError("state_schema_mismatch")
    if raw.get("session_id") != SESSION_ID or raw.get("iai_version") != EXPECTED_IAI_VERSION:
        raise AdapterError("state_runtime_mismatch")
    if os.path.normcase(str(raw.get("vault_root") or "")) != os.path.normcase(vault_root_text(vault_root)):
        raise AdapterError("state_vault_root_mismatch")
    if os.path.normcase(str(raw.get("store_root") or "")) != os.path.normcase(str(canonical_path(store_root))):
        raise AdapterError("state_store_root_mismatch")
    checkpoint = raw.get("checkpoint_id")
    if not isinstance(checkpoint, str) or not _SHA256_RE.fullmatch(checkpoint):
        raise AdapterError("state_checkpoint_id_invalid")
    files = raw.get("files")
    if not isinstance(files, dict):
        raise AdapterError("state_files_invalid")
    _validate_file_map(files, label="state")
    _validate_utc_timestamp(raw.get("successful_run_utc"), "state", allow_none=True)
    return raw


def vendor_doc_tag(relative_path: str, doc_tag_fn: Callable[[str], str]) -> str:
    validate_source_name(relative_path)
    try:
        tag = str(doc_tag_fn(relative_path))
    except Exception as exc:
        raise AdapterError(f"doc_tag_failed:{relative_path}:{type(exc).__name__}") from exc
    if not tag.startswith("doc:") or len(tag) <= 4:
        raise AdapterError(f"doc_tag_invalid:{relative_path}:{tag}")
    return tag


def validate_doc_tags(notes: Iterable[NoteSnapshot], state: Mapping[str, Any], doc_tag_fn: Callable[[str], str]) -> dict[str, str]:
    current: dict[str, str] = {}
    by_tag: dict[str, str] = {}
    for note in notes:
        tag = vendor_doc_tag(note.relative_path, doc_tag_fn)
        owner = by_tag.get(tag)
        if owner is not None and owner != note.relative_path:
            raise AdapterError(f"doc_tag_collision:{tag}:{owner}:{note.relative_path}")
        by_tag[tag] = note.relative_path
        current[note.relative_path] = tag
    previous = state.get("files")
    if not isinstance(previous, Mapping):
        raise AdapterError("state_files_invalid")
    for old_rel, old_meta in previous.items():
        if not isinstance(old_rel, str) or not isinstance(old_meta, Mapping):
            raise AdapterError("state_entry_invalid")
        expected = vendor_doc_tag(old_rel, doc_tag_fn)
        if old_meta.get("doc_tag") != expected:
            raise AdapterError(f"state_doc_tag_vendor_mismatch:{old_rel}")
        current_owner = by_tag.get(expected)
        if current_owner is not None and current_owner != old_rel:
            raise AdapterError(f"historical_doc_tag_collision:{expected}:{old_rel}:{current_owner}")
    return current


def build_plan(notes: Iterable[NoteSnapshot], state: Mapping[str, Any]) -> SyncPlan:
    current = {n.relative_path: n for n in notes}
    previous = state.get("files") if isinstance(state.get("files"), Mapping) else {}
    new: list[str] = []
    changed: list[str] = []
    unchanged: list[str] = []
    for rel in sorted(current, key=lambda s: (s.casefold(), s)):
        old = previous.get(rel)
        if not isinstance(old, Mapping):
            new.append(rel)
        elif old.get("sha256") != current[rel].sha256:
            changed.append(rel)
        else:
            unchanged.append(rel)
    deleted = sorted((str(r) for r in previous if r not in current), key=lambda s: (s.casefold(), s))
    return SyncPlan(tuple(new), tuple(changed), tuple(unchanged), tuple(deleted))


def reconcile_active_pending(plan: SyncPlan, notes: Iterable[NoteSnapshot], state: Mapping[str, Any], paths: Iterable[str]) -> SyncPlan:
    current = {n.relative_path for n in notes}
    previous = set(str(k) for k in (state.get("files") or {}))
    new, changed, unchanged, deleted = map(set, (plan.new, plan.changed, plan.unchanged, plan.deleted))
    for rel in paths:
        if rel in current:
            deleted.discard(rel); unchanged.discard(rel)
            if rel in previous:
                new.discard(rel); changed.add(rel)
            else:
                changed.discard(rel); new.add(rel)
        else:
            new.discard(rel); changed.discard(rel); unchanged.discard(rel); deleted.add(rel)
    key = lambda s: (s.casefold(), s)
    return SyncPlan(tuple(sorted(new, key=key)), tuple(sorted(changed, key=key)), tuple(sorted(unchanged, key=key)), tuple(sorted(deleted, key=key)))


def _state_payload(vault_root: Path, store_root: Path, notes: Iterable[NoteSnapshot], doc_tags: Mapping[str, str], checkpoint_id: str) -> dict[str, Any]:
    if not _SHA256_RE.fullmatch(checkpoint_id):
        raise AdapterError("state_checkpoint_id_invalid")
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "session_id": SESSION_ID,
        "iai_version": EXPECTED_IAI_VERSION,
        "vault_root": vault_root_text(vault_root),
        "store_root": str(canonical_path(store_root)),
        "successful_run_utc": _utc_now(),
        "checkpoint_id": checkpoint_id,
        "files": _files_payload(notes, doc_tags),
    }


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
) -> dict[str, Any]:
    previous = state.get("files")
    if not isinstance(previous, Mapping):
        raise AdapterError("state_files_invalid")
    base_id = state.get("checkpoint_id")
    if not isinstance(base_id, str) or not _SHA256_RE.fullmatch(base_id):
        raise AdapterError("state_checkpoint_id_invalid")
    if not _SHA256_RE.fullmatch(target_checkpoint_id) or target_checkpoint_id == base_id:
        raise AdapterError("pending_target_checkpoint_id_invalid")
    target_files = _files_payload(notes, doc_tags)
    affected = sorted(set(plan.new + plan.changed + plan.deleted), key=lambda s: (s.casefold(), s))
    if not affected:
        raise AdapterError("pending_empty")
    paths: dict[str, Any] = {}
    for rel in affected:
        validate_source_name(rel)
        if rel in doc_tags:
            tag = doc_tags[rel]
        else:
            old = previous.get(rel)
            if isinstance(old, Mapping) and isinstance(old.get("doc_tag"), str):
                tag = str(old["doc_tag"])
            elif recovery_doc_tags is not None and isinstance(recovery_doc_tags.get(rel), str):
                tag = str(recovery_doc_tags[rel])
            else:
                raise AdapterError(f"pending_missing_deleted_tag:{rel}")
        paths[rel] = {"doc_tag": tag}
    return {
        "schema_version": PENDING_SCHEMA_VERSION,
        "session_id": SESSION_ID,
        "iai_version": EXPECTED_IAI_VERSION,
        "vault_root": vault_root_text(vault_root),
        "store_root": str(canonical_path(store_root)),
        "started_run_utc": _utc_now(),
        "base_checkpoint_id": base_id,
        "target_checkpoint_id": target_checkpoint_id,
        "base_files_sha256": _files_digest(previous),
        "target_files_sha256": _files_digest(target_files),
        "paths": paths,
    }


def load_pending(path: Path, vault_root: Path, store_root: Path, state: Mapping[str, Any], current_doc_tags: Mapping[str, str], doc_tag_fn: Callable[[str], str]) -> PendingStatus:
    if not path.exists():
        return PendingStatus("none", (), {})
    raw = dict(_read_json_file(path, "pending"))
    if raw.get("schema_version") != PENDING_SCHEMA_VERSION:
        raise AdapterError("pending_schema_mismatch")
    if raw.get("session_id") != SESSION_ID or raw.get("iai_version") != EXPECTED_IAI_VERSION:
        raise AdapterError("pending_runtime_mismatch")
    if os.path.normcase(str(raw.get("vault_root") or "")) != os.path.normcase(vault_root_text(vault_root)):
        raise AdapterError("pending_vault_root_mismatch")
    if os.path.normcase(str(raw.get("store_root") or "")) != os.path.normcase(str(canonical_path(store_root))):
        raise AdapterError("pending_store_root_mismatch")
    _validate_utc_timestamp(raw.get("started_run_utc"), "pending")
    base_id, target_id = raw.get("base_checkpoint_id"), raw.get("target_checkpoint_id")
    if not isinstance(base_id, str) or not _SHA256_RE.fullmatch(base_id):
        raise AdapterError("pending_base_checkpoint_id_invalid")
    if not isinstance(target_id, str) or not _SHA256_RE.fullmatch(target_id) or target_id == base_id:
        raise AdapterError("pending_target_checkpoint_id_invalid")
    base_digest = raw.get("base_files_sha256")
    target_digest = raw.get("target_files_sha256")
    if not isinstance(base_digest, str) or not _SHA256_RE.fullmatch(base_digest):
        raise AdapterError("pending_base_digest_invalid")
    if not isinstance(target_digest, str) or not _SHA256_RE.fullmatch(target_digest):
        raise AdapterError("pending_target_digest_invalid")
    paths_raw = raw.get("paths")
    if not isinstance(paths_raw, dict) or not paths_raw:
        raise AdapterError("pending_paths_invalid")
    seen_tags: dict[str, str] = {}
    seen_casefold: dict[str, str] = {}
    path_tags: dict[str, str] = {}
    paths: list[str] = []
    for rel, meta in paths_raw.items():
        if not isinstance(rel, str):
            raise AdapterError("pending_source_name_invalid_type")
        validate_source_name(rel)
        folded = rel.casefold()
        prior_case = seen_casefold.get(folded)
        if prior_case is not None and prior_case != rel:
            raise AdapterError(f"pending_casefold_collision:{prior_case}:{rel}")
        seen_casefold[folded] = rel
        if not isinstance(meta, Mapping) or not isinstance(meta.get("doc_tag"), str):
            raise AdapterError(f"pending_entry_invalid:{rel}")
        expected = vendor_doc_tag(rel, doc_tag_fn)
        if meta.get("doc_tag") != expected:
            raise AdapterError(f"pending_doc_tag_vendor_mismatch:{rel}")
        prior = seen_tags.get(expected)
        if prior is not None and prior != rel:
            raise AdapterError(f"pending_doc_tag_collision:{expected}:{prior}:{rel}")
        seen_tags[expected] = rel
        path_tags[rel] = expected
        paths.append(rel)
    state_files = state.get("files")
    if not isinstance(state_files, Mapping):
        raise AdapterError("state_files_invalid")
    state_id = state.get("checkpoint_id")
    state_digest = _files_digest(state_files)
    if state_id == target_id:
        if state_digest != target_digest:
            raise AdapterError("pending_target_digest_mismatch")
        return PendingStatus("completed", tuple(sorted(paths, key=lambda s: (s.casefold(), s))), dict(path_tags))
    if state_id == base_id:
        if state_digest != base_digest:
            raise AdapterError("pending_base_digest_mismatch")
        current_by_tag = {tag: rel for rel, tag in current_doc_tags.items()}
        for tag, pending_owner in seen_tags.items():
            owner = current_by_tag.get(tag)
            if owner is not None and owner != pending_owner:
                raise AdapterError(f"pending_doc_tag_collision:{tag}:{pending_owner}:{owner}")
        return PendingStatus("active", tuple(sorted(paths, key=lambda s: (s.casefold(), s))), dict(path_tags))
    raise AdapterError("pending_state_mismatch")


def load_owner(path: Path, vault_root: Path, store_root: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    raw = _read_json_file(path, "owner")
    if raw.get("schema_version") != OWNER_SCHEMA_VERSION:
        raise AdapterError("owner_schema_mismatch")
    if raw.get("session_id") != SESSION_ID or raw.get("iai_version") != EXPECTED_IAI_VERSION:
        raise AdapterError("owner_runtime_mismatch")
    if os.path.normcase(str(raw.get("vault_root") or "")) != os.path.normcase(vault_root_text(vault_root)):
        raise AdapterError("owner_vault_root_mismatch")
    if os.path.normcase(str(raw.get("store_root") or "")) != os.path.normcase(str(canonical_path(store_root))):
        raise AdapterError("owner_store_root_mismatch")
    return raw


def owner_payload(vault_root: Path, store_root: Path) -> dict[str, Any]:
    return {
        "schema_version": OWNER_SCHEMA_VERSION,
        "session_id": SESSION_ID,
        "iai_version": EXPECTED_IAI_VERSION,
        "vault_root": vault_root_text(vault_root),
        "store_root": str(canonical_path(store_root)),
    }
