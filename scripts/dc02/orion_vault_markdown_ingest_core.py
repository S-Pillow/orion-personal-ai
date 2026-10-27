#!/usr/bin/env python3
"""Internal DC-02 Markdown-ingestion primitives.

This module contains source admission, planning, recovery metadata, locking, and
native iai primitive helpers only. It is not an ingestion transaction entry
point. The only supported CLI is ``orion_vault_markdown_ingest.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
import re
import secrets
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping

EXPECTED_IAI_VERSION = "3.3.0"
SESSION_ID = "vault-study"
DEFAULT_VAULT_ROOT = Path(r"C:\Personal\Me")
MAX_VAULT_FILES = 5000
MAX_SOURCE_FILE_BYTES = 2_000_000
STATE_SCHEMA_VERSION = 2
PENDING_SCHEMA_VERSION = 2
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AdapterError(RuntimeError):
    """Fail-closed adapter preflight or synchronization error."""


@dataclass(frozen=True)
class NoteSnapshot:
    relative_path: str
    absolute_path: str
    size: int
    mtime_ns: int
    sha256: str

    def state_value(self, doc_tag: str) -> dict[str, Any]:
        return {
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
            "doc_tag": doc_tag,
        }


@dataclass(frozen=True)
class SyncPlan:
    new: tuple[str, ...]
    changed: tuple[str, ...]
    unchanged: tuple[str, ...]
    deleted: tuple[str, ...]

    @property
    def mutation_count(self) -> int:
        return len(self.new) + len(self.changed) + len(self.deleted)


@dataclass(frozen=True)
class IaiRuntime:
    version: str
    doc_tag: Callable[[str], str]
    study_document: Callable[..., dict[str, Any]]
    open_store: Callable[[Path], Any]


class _ApplyLockHandle:
    """Own one cross-process advisory byte/file lock for an apply run."""

    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self.fd = fd
        self.closed = False

    def close(self) -> None:
        if self.closed:
            return
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(self.fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                try:
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            os.close(self.fd)
            self.closed = True


class _ApplyLocksHandle:
    """Own the deterministic set of state/store apply locks for one run."""

    def __init__(self, handles: Iterable[_ApplyLockHandle]) -> None:
        self.handles = tuple(handles)
        self.closed = False

    def close(self) -> None:
        if self.closed:
            return
        first_error: OSError | None = None
        for handle in reversed(self.handles):
            try:
                handle.close()
            except OSError as exc:
                if first_error is None:
                    first_error = exc
        self.closed = True
        if first_error is not None:
            raise first_error


def _canonical_path_text(path: Path) -> str:
    return str(path.expanduser().resolve(strict=False))


def _is_reparse_point(path: Path) -> bool:
    """Return True for symlinks/junctions/reparse points or unreadable entries."""
    try:
        info = os.lstat(path)
    except OSError:
        return True
    if stat.S_ISLNK(info.st_mode):
        return True
    attrs = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse_flag)


def _contained(path: Path, root_real: Path) -> bool:
    try:
        path.relative_to(root_real)
    except ValueError:
        return False
    return True


def _strict_utf8_snapshot(
    path: Path,
    root_real: Path,
    *,
    max_file_bytes: int = MAX_SOURCE_FILE_BYTES,
) -> NoteSnapshot:
    """Read one Markdown file through the strict Orion source boundary."""
    if max_file_bytes < 1:
        raise AdapterError("max_file_bytes_must_be_positive")
    if _is_reparse_point(path):
        raise AdapterError(f"unsafe_reparse_markdown:{path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise AdapterError(f"markdown_resolve_failed:{path}:{type(exc).__name__}") from exc
    if not _contained(resolved, root_real):
        raise AdapterError(f"markdown_escaped_vault:{path}")

    try:
        before = resolved.stat()
        if not stat.S_ISREG(before.st_mode):
            raise AdapterError(f"markdown_not_regular_file:{resolved}")
        if before.st_size > max_file_bytes:
            raise AdapterError(
                f"markdown_file_too_large:{resolved.relative_to(root_real).as_posix()}:"
                f"{before.st_size}>{max_file_bytes}"
            )
        data = resolved.read_bytes()
        if len(data) > max_file_bytes:
            raise AdapterError(
                f"markdown_file_too_large:{resolved.relative_to(root_real).as_posix()}:"
                f"{len(data)}>{max_file_bytes}"
            )
        data.decode("utf-8")
        after = resolved.stat()
    except UnicodeDecodeError as exc:
        raise AdapterError(f"markdown_not_utf8:{resolved}") from exc
    except AdapterError:
        raise
    except OSError as exc:
        raise AdapterError(f"markdown_read_failed:{resolved}:{type(exc).__name__}") from exc

    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise AdapterError(f"markdown_changed_during_snapshot:{resolved}")
    if after.st_size != len(data):
        raise AdapterError(f"markdown_changed_during_snapshot:{resolved}")

    return NoteSnapshot(
        relative_path=resolved.relative_to(root_real).as_posix(),
        absolute_path=str(resolved),
        size=len(data),
        mtime_ns=after.st_mtime_ns,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def scan_markdown_vault(
    vault_root: Path,
    *,
    max_files: int = MAX_VAULT_FILES,
    max_file_bytes: int = MAX_SOURCE_FILE_BYTES,
) -> list[NoteSnapshot]:
    """Return a deterministic snapshot of contained, non-reparse ``*.md`` only."""
    if max_files < 1:
        raise AdapterError("max_files_must_be_positive")
    if max_file_bytes < 1:
        raise AdapterError("max_file_bytes_must_be_positive")
    if not vault_root.is_dir():
        raise AdapterError(f"vault_root_unavailable:{vault_root}")
    if _is_reparse_point(vault_root):
        raise AdapterError(f"vault_root_is_reparse_point:{vault_root}")
    try:
        root_real = vault_root.resolve(strict=True)
    except OSError as exc:
        raise AdapterError(f"vault_root_resolve_failed:{type(exc).__name__}") from exc

    notes: list[NoteSnapshot] = []
    seen_casefold: dict[str, str] = {}

    def _walk_error(exc: OSError) -> None:
        failed_path = getattr(exc, "filename", None) or str(root_real)
        raise AdapterError(f"vault_walk_failed:{failed_path}:{type(exc).__name__}") from exc

    for dirpath, dirnames, filenames in os.walk(
        root_real, topdown=True, onerror=_walk_error, followlinks=False
    ):
        current = Path(dirpath)
        safe_dirs: list[str] = []
        for name in sorted(dirnames, key=lambda value: (value.casefold(), value)):
            child = current / name
            if _is_reparse_point(child):
                raise AdapterError(f"unsafe_reparse_directory:{child}")
            try:
                child_real = child.resolve(strict=True)
            except OSError as exc:
                raise AdapterError(
                    f"directory_resolve_failed:{child}:{type(exc).__name__}"
                ) from exc
            if not _contained(child_real, root_real):
                raise AdapterError(f"directory_escaped_vault:{child}")
            safe_dirs.append(name)
        dirnames[:] = safe_dirs

        for name in sorted(filenames, key=lambda value: (value.casefold(), value)):
            path = current / name
            if path.suffix.casefold() != ".md":
                continue
            snap = _strict_utf8_snapshot(path, root_real, max_file_bytes=max_file_bytes)
            folded = snap.relative_path.casefold()
            previous = seen_casefold.get(folded)
            if previous is not None and previous != snap.relative_path:
                raise AdapterError(f"casefold_path_collision:{previous}:{snap.relative_path}")
            seen_casefold[folded] = snap.relative_path
            notes.append(snap)
            if len(notes) > max_files:
                raise AdapterError(f"vault_file_limit_exceeded:{len(notes)}>{max_files}")

    notes.sort(key=lambda item: (item.relative_path.casefold(), item.relative_path))
    return notes


def _vendor_doc_tag(relative_path: str, doc_tag_fn: Callable[[str], str]) -> str:
    try:
        tag = str(doc_tag_fn(relative_path))
    except Exception as exc:
        raise AdapterError(f"doc_tag_failed:{relative_path}:{type(exc).__name__}") from exc
    if not tag.startswith("doc:") or len(tag) <= 4:
        raise AdapterError(f"doc_tag_invalid:{relative_path}:{tag}")
    return tag


def validate_doc_tag_uniqueness(
    notes: Iterable[NoteSnapshot], doc_tag_fn: Callable[[str], str]
) -> dict[str, str]:
    by_tag: dict[str, str] = {}
    by_path: dict[str, str] = {}
    for note in notes:
        tag = _vendor_doc_tag(note.relative_path, doc_tag_fn)
        owner = by_tag.get(tag)
        if owner is not None and owner != note.relative_path:
            raise AdapterError(f"doc_tag_collision:{tag}:{owner}:{note.relative_path}")
        by_tag[tag] = note.relative_path
        by_path[note.relative_path] = tag
    return by_path


def _default_store_root() -> Path:
    raw = os.environ.get("IAI_MCP_STORE")
    return Path(raw).expanduser() if raw else Path.home() / ".iai-mcp"


def _default_state_file(store_root: Path) -> Path:
    return store_root / "orion" / "vault-markdown-ingest-state.json"


def _pending_file_for(state_file: Path) -> Path:
    return state_file.with_name(state_file.name + ".pending.json")


def _apply_lock_file_for(state_file: Path) -> Path:
    return state_file.with_name(state_file.name + ".apply.lock")


def _store_apply_lock_file_for(store_root: Path) -> Path:
    return store_root / "orion" / "vault-markdown-ingest-store.apply.lock"


def _acquire_apply_lock(lock_file: Path) -> _ApplyLockHandle:
    """Acquire one nonblocking cross-process advisory lock."""
    fd: int | None = None
    canonical = Path(_canonical_path_text(lock_file))
    try:
        canonical.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(canonical), os.O_CREAT | os.O_RDWR, 0o600)
        if os.name == "nt":
            import msvcrt

            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
                os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _ApplyLockHandle(canonical, fd)
    except OSError as exc:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        raise AdapterError(f"apply_lock_unavailable:{canonical}:{type(exc).__name__}") from exc


def _acquire_apply_locks(lock_files: Iterable[Path]) -> _ApplyLocksHandle:
    """Acquire state and store locks in deterministic canonical-path order."""
    by_key: dict[str, Path] = {}
    for raw in lock_files:
        canonical = Path(_canonical_path_text(raw))
        key = os.path.normcase(str(canonical))
        by_key[key] = canonical
    ordered = [by_key[key] for key in sorted(by_key)]
    handles: list[_ApplyLockHandle] = []
    try:
        for path in ordered:
            handles.append(_acquire_apply_lock(path))
    except AdapterError:
        for handle in reversed(handles):
            try:
                handle.close()
            except OSError:
                pass
        raise
    return _ApplyLocksHandle(handles)


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
        return True
    except (OSError, ValueError):
        return False


def validate_state_location(state_file: Path, vault_root: Path) -> None:
    if _path_is_within(state_file, vault_root):
        raise AdapterError(f"state_file_inside_vault:{state_file}")


def validate_store_location(store_root: Path, vault_root: Path) -> None:
    if _path_is_within(store_root, vault_root):
        raise AdapterError(f"store_root_inside_vault:{store_root}")


def _validate_state_source_name(relative_path: str) -> None:
    if not relative_path or "\\" in relative_path:
        raise AdapterError(f"state_source_name_invalid:{relative_path}")
    posix = PurePosixPath(relative_path)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise AdapterError(f"state_source_name_invalid:{relative_path}")
    if posix.suffix.casefold() != ".md":
        raise AdapterError(f"state_source_name_not_markdown:{relative_path}")


def _vault_source_path(vault_root: Path, relative_path: str) -> Path:
    """Map one already-vetted POSIX source name back under the vault root."""
    _validate_state_source_name(relative_path)
    root_real = vault_root.resolve(strict=True)
    return root_real.joinpath(*PurePosixPath(relative_path).parts)


def _validate_success_timestamp(value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise AdapterError("state_success_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdapterError("state_success_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        raise AdapterError("state_success_timestamp_invalid")


def _validate_state_files(files: Mapping[str, Any]) -> None:
    seen_casefold: dict[str, str] = {}
    seen_tags: dict[str, str] = {}
    for raw_rel, raw_meta in files.items():
        if not isinstance(raw_rel, str):
            raise AdapterError("state_source_name_invalid_type")
        _validate_state_source_name(raw_rel)
        folded = raw_rel.casefold()
        previous = seen_casefold.get(folded)
        if previous is not None and previous != raw_rel:
            raise AdapterError(f"state_casefold_path_collision:{previous}:{raw_rel}")
        seen_casefold[folded] = raw_rel
        if not isinstance(raw_meta, Mapping):
            raise AdapterError(f"state_file_entry_invalid:{raw_rel}")
        size = raw_meta.get("size")
        mtime_ns = raw_meta.get("mtime_ns")
        sha256 = raw_meta.get("sha256")
        doc_tag = raw_meta.get("doc_tag")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise AdapterError(f"state_file_size_invalid:{raw_rel}")
        if not isinstance(mtime_ns, int) or isinstance(mtime_ns, bool) or mtime_ns < 0:
            raise AdapterError(f"state_file_mtime_invalid:{raw_rel}")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            raise AdapterError(f"state_file_sha256_invalid:{raw_rel}")
        if not isinstance(doc_tag, str) or not doc_tag.startswith("doc:") or len(doc_tag) <= 4:
            raise AdapterError(f"state_file_doc_tag_invalid:{raw_rel}")
        tag_owner = seen_tags.get(doc_tag)
        if tag_owner is not None and tag_owner != raw_rel:
            raise AdapterError(f"state_doc_tag_collision:{doc_tag}:{tag_owner}:{raw_rel}")
        seen_tags[doc_tag] = raw_rel


def _empty_state(vault_root: Path, store_root: Path | None = None) -> dict[str, Any]:
    effective_store = store_root if store_root is not None else _default_store_root()
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "session_id": SESSION_ID,
        "vault_root": str(vault_root.resolve(strict=True)),
        "store_root": _canonical_path_text(effective_store),
        "iai_version": EXPECTED_IAI_VERSION,
        "successful_run_utc": None,
        "files": {},
    }


def _checkpoint_identity(state: Mapping[str, Any]) -> str:
    """Return a stable successful-checkpoint generation identity.

    New checkpoints carry an explicit random identity. Empty checkpoints derive
    a deterministic identity from their validated source/store metadata so an
    interrupted first bootstrap can still be recognized on retry.
    """
    explicit = state.get("checkpoint_id")
    if explicit is not None:
        if not isinstance(explicit, str) or not _SHA256_RE.fullmatch(explicit):
            raise AdapterError("state_checkpoint_id_invalid")
        return explicit
    files = state.get("files")
    if not isinstance(files, Mapping):
        raise AdapterError("state_files_invalid")
    base = {
        "schema_version": state.get("schema_version"),
        "session_id": state.get("session_id"),
        "vault_root": state.get("vault_root"),
        "store_root": state.get("store_root"),
        "iai_version": state.get("iai_version"),
        "successful_run_utc": state.get("successful_run_utc"),
        "files": files,
    }
    encoded = json.dumps(
        base, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_state(
    state_file: Path,
    vault_root: Path,
    store_root: Path | None = None,
) -> dict[str, Any]:
    if not state_file.exists():
        return _empty_state(vault_root, store_root)
    try:
        raw = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"state_read_failed:{type(exc).__name__}") from exc
    if not isinstance(raw, dict):
        raise AdapterError("state_invalid_shape")
    if raw.get("schema_version") != STATE_SCHEMA_VERSION:
        raise AdapterError("state_schema_mismatch")
    if raw.get("session_id") != SESSION_ID:
        raise AdapterError("state_session_mismatch")
    if raw.get("iai_version") != EXPECTED_IAI_VERSION:
        raise AdapterError("state_iai_version_mismatch")
    expected_root = str(vault_root.resolve(strict=True))
    stored_root = str(raw.get("vault_root") or "")
    if os.path.normcase(stored_root) != os.path.normcase(expected_root):
        raise AdapterError(f"state_vault_root_mismatch:{stored_root}:{expected_root}")
    stored_store = raw.get("store_root")
    if store_root is not None:
        expected_store = _canonical_path_text(store_root)
        stored_store_text = str(stored_store or "")
        if os.path.normcase(stored_store_text) != os.path.normcase(expected_store):
            raise AdapterError(
                f"state_store_root_mismatch:{stored_store_text}:{expected_store}"
            )
    elif stored_store is not None and not isinstance(stored_store, str):
        raise AdapterError("state_store_root_invalid")
    _validate_success_timestamp(raw.get("successful_run_utc"))
    files = raw.get("files")
    if not isinstance(files, dict):
        raise AdapterError("state_files_invalid")
    _validate_state_files(files)
    _checkpoint_identity(raw)
    return raw


def validate_cross_generation_doc_tags(
    state: Mapping[str, Any],
    current_doc_tags: Mapping[str, str],
    doc_tag_fn: Callable[[str], str],
) -> None:
    previous_raw = state.get("files") if isinstance(state, Mapping) else None
    if not isinstance(previous_raw, Mapping):
        raise AdapterError("state_files_invalid")
    current_by_tag: dict[str, str] = {}
    for current_path, tag in current_doc_tags.items():
        owner = current_by_tag.get(tag)
        if owner is not None and owner != current_path:
            raise AdapterError(f"doc_tag_collision:{tag}:{owner}:{current_path}")
        current_by_tag[tag] = current_path
    for raw_path, raw_meta in previous_raw.items():
        if not isinstance(raw_path, str) or not isinstance(raw_meta, Mapping):
            raise AdapterError("state_file_entry_invalid")
        stored_tag = raw_meta.get("doc_tag")
        if not isinstance(stored_tag, str):
            raise AdapterError(f"state_file_doc_tag_invalid:{raw_path}")
        expected_tag = _vendor_doc_tag(raw_path, doc_tag_fn)
        if stored_tag != expected_tag:
            raise AdapterError(
                f"state_doc_tag_vendor_mismatch:{raw_path}:{stored_tag}:{expected_tag}"
            )
        current_owner = current_by_tag.get(stored_tag)
        if current_owner is not None and current_owner != raw_path:
            raise AdapterError(
                f"historical_doc_tag_collision:{stored_tag}:{raw_path}:{current_owner}"
            )


def build_plan(notes: Iterable[NoteSnapshot], state: Mapping[str, Any]) -> SyncPlan:
    current = {note.relative_path: note for note in notes}
    previous_raw = state.get("files") if isinstance(state, Mapping) else {}
    previous = previous_raw if isinstance(previous_raw, Mapping) else {}
    new: list[str] = []
    changed: list[str] = []
    unchanged: list[str] = []
    for rel in sorted(current, key=lambda value: (value.casefold(), value)):
        old = previous.get(rel)
        if not isinstance(old, Mapping):
            new.append(rel)
        elif str(old.get("sha256") or "") != current[rel].sha256:
            changed.append(rel)
        else:
            unchanged.append(rel)
    deleted = sorted(
        (str(rel) for rel in previous.keys() if rel not in current),
        key=lambda value: (value.casefold(), value),
    )
    return SyncPlan(tuple(new), tuple(changed), tuple(unchanged), tuple(deleted))


def _state_files_payload(
    notes: Iterable[NoteSnapshot], doc_tags: Mapping[str, str]
) -> dict[str, Any]:
    return {
        note.relative_path: note.state_value(doc_tags[note.relative_path])
        for note in sorted(notes, key=lambda item: (item.relative_path.casefold(), item.relative_path))
    }


def _files_digest(files: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        files, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _state_payload(
    vault_root: Path,
    notes: Iterable[NoteSnapshot],
    doc_tags: Mapping[str, str],
    iai_version: str,
    checkpoint_id: str,
    *,
    store_root: Path | None = None,
) -> dict[str, Any]:
    if not _SHA256_RE.fullmatch(checkpoint_id):
        raise AdapterError("state_checkpoint_id_invalid")
    effective_store = store_root if store_root is not None else _default_store_root()
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "session_id": SESSION_ID,
        "vault_root": str(vault_root.resolve(strict=True)),
        "store_root": _canonical_path_text(effective_store),
        "iai_version": iai_version,
        "successful_run_utc": _utc_now_iso(),
        "checkpoint_id": checkpoint_id,
        "files": _state_files_payload(notes, doc_tags),
    }


def _pending_payload(
    *,
    vault_root: Path,
    store_root: Path,
    state: Mapping[str, Any],
    notes: Iterable[NoteSnapshot],
    doc_tags: Mapping[str, str],
    plan: SyncPlan,
    iai_version: str,
    doc_tag_fn: Callable[[str], str],
    target_checkpoint_id: str,
) -> dict[str, Any]:
    previous_raw = state.get("files") if isinstance(state, Mapping) else None
    if not isinstance(previous_raw, Mapping):
        raise AdapterError("state_files_invalid")
    if not _SHA256_RE.fullmatch(target_checkpoint_id):
        raise AdapterError("pending_target_checkpoint_id_invalid")
    target_files = _state_files_payload(notes, doc_tags)
    affected = sorted(
        set((*plan.new, *plan.changed, *plan.deleted)),
        key=lambda value: (value.casefold(), value),
    )
    if not affected:
        raise AdapterError("pending_journal_empty")
    paths: dict[str, Any] = {}
    for rel in affected:
        tag = doc_tags.get(rel)
        if tag is None:
            old = previous_raw.get(rel)
            if isinstance(old, Mapping) and isinstance(old.get("doc_tag"), str):
                tag = str(old["doc_tag"])
            else:
                tag = _vendor_doc_tag(rel, doc_tag_fn)
        paths[rel] = {"doc_tag": tag}
    return {
        "schema_version": PENDING_SCHEMA_VERSION,
        "session_id": SESSION_ID,
        "vault_root": str(vault_root.resolve(strict=True)),
        "store_root": _canonical_path_text(store_root),
        "iai_version": iai_version,
        "started_run_utc": _utc_now_iso(),
        "base_checkpoint_id": _checkpoint_identity(state),
        "target_checkpoint_id": target_checkpoint_id,
        "base_files_sha256": _files_digest(previous_raw),
        "target_files_sha256": _files_digest(target_files),
        "paths": paths,
    }


def _write_atomic(path: Path, payload: Mapping[str, Any], error_prefix: str) -> None:
    tmp_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(path.parent), text=True
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    except (OSError, TypeError, ValueError) as exc:
        raise AdapterError(f"{error_prefix}:{type(exc).__name__}") from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def write_state_atomic(state_file: Path, payload: Mapping[str, Any]) -> None:
    _write_atomic(state_file, payload, "state_write_failed")


def write_pending_atomic(pending_file: Path, payload: Mapping[str, Any]) -> None:
    _write_atomic(pending_file, payload, "pending_write_failed")


def clear_pending_journal(pending_file: Path) -> None:
    try:
        pending_file.unlink(missing_ok=True)
    except OSError as exc:
        raise AdapterError(f"pending_clear_failed:{type(exc).__name__}") from exc


def load_pending_journal(
    pending_file: Path,
    *,
    vault_root: Path,
    store_root: Path,
    state: Mapping[str, Any],
    current_doc_tags: Mapping[str, str],
    doc_tag_fn: Callable[[str], str],
) -> tuple[tuple[str, ...], str]:
    if not pending_file.exists():
        return (), "none"
    try:
        raw = json.loads(pending_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError(f"pending_read_failed:{type(exc).__name__}") from exc
    if not isinstance(raw, dict):
        raise AdapterError("pending_invalid_shape")
    if raw.get("schema_version") != PENDING_SCHEMA_VERSION:
        raise AdapterError("pending_schema_mismatch")
    if raw.get("session_id") != SESSION_ID:
        raise AdapterError("pending_session_mismatch")
    if raw.get("iai_version") != EXPECTED_IAI_VERSION:
        raise AdapterError("pending_iai_version_mismatch")
    expected_root = str(vault_root.resolve(strict=True))
    stored_root = str(raw.get("vault_root") or "")
    if os.path.normcase(stored_root) != os.path.normcase(expected_root):
        raise AdapterError(f"pending_vault_root_mismatch:{stored_root}:{expected_root}")
    expected_store = _canonical_path_text(store_root)
    stored_store = str(raw.get("store_root") or "")
    if os.path.normcase(stored_store) != os.path.normcase(expected_store):
        raise AdapterError(f"pending_store_root_mismatch:{stored_store}:{expected_store}")

    base_checkpoint_id = raw.get("base_checkpoint_id")
    target_checkpoint_id = raw.get("target_checkpoint_id")
    if not isinstance(base_checkpoint_id, str) or not _SHA256_RE.fullmatch(base_checkpoint_id):
        raise AdapterError("pending_base_checkpoint_id_invalid")
    if not isinstance(target_checkpoint_id, str) or not _SHA256_RE.fullmatch(target_checkpoint_id):
        raise AdapterError("pending_target_checkpoint_id_invalid")
    if base_checkpoint_id == target_checkpoint_id:
        raise AdapterError("pending_checkpoint_identity_reused")
    base_digest = raw.get("base_files_sha256")
    target_digest = raw.get("target_files_sha256")
    if not isinstance(base_digest, str) or not _SHA256_RE.fullmatch(base_digest):
        raise AdapterError("pending_base_digest_invalid")
    if not isinstance(target_digest, str) or not _SHA256_RE.fullmatch(target_digest):
        raise AdapterError("pending_target_digest_invalid")

    paths_raw = raw.get("paths")
    if not isinstance(paths_raw, dict) or not paths_raw:
        raise AdapterError("pending_paths_invalid")
    seen_casefold: dict[str, str] = {}
    seen_tags: dict[str, str] = {}
    paths: list[str] = []
    for raw_rel, raw_meta in paths_raw.items():
        if not isinstance(raw_rel, str):
            raise AdapterError("pending_source_name_invalid_type")
        _validate_state_source_name(raw_rel)
        folded = raw_rel.casefold()
        previous = seen_casefold.get(folded)
        if previous is not None and previous != raw_rel:
            raise AdapterError(f"pending_casefold_path_collision:{previous}:{raw_rel}")
        seen_casefold[folded] = raw_rel
        if not isinstance(raw_meta, Mapping):
            raise AdapterError(f"pending_path_entry_invalid:{raw_rel}")
        stored_tag = raw_meta.get("doc_tag")
        if not isinstance(stored_tag, str):
            raise AdapterError(f"pending_doc_tag_invalid:{raw_rel}")
        expected_tag = _vendor_doc_tag(raw_rel, doc_tag_fn)
        if stored_tag != expected_tag:
            raise AdapterError(
                f"pending_doc_tag_vendor_mismatch:{raw_rel}:{stored_tag}:{expected_tag}"
            )
        tag_owner = seen_tags.get(stored_tag)
        if tag_owner is not None and tag_owner != raw_rel:
            raise AdapterError(f"pending_doc_tag_collision:{stored_tag}:{tag_owner}:{raw_rel}")
        seen_tags[stored_tag] = raw_rel
        paths.append(raw_rel)

    state_files = state.get("files") if isinstance(state, Mapping) else None
    if not isinstance(state_files, Mapping):
        raise AdapterError("state_files_invalid")
    state_digest = _files_digest(state_files)
    state_checkpoint_id = _checkpoint_identity(state)
    ordered = tuple(sorted(paths, key=lambda value: (value.casefold(), value)))
    if state_checkpoint_id == target_checkpoint_id:
        if state_digest != target_digest:
            raise AdapterError("pending_target_digest_mismatch")
        return ordered, "completed"
    if state_checkpoint_id == base_checkpoint_id:
        if state_digest != base_digest:
            raise AdapterError("pending_base_digest_mismatch")
        current_by_tag = {tag: rel for rel, tag in current_doc_tags.items()}
        for stored_tag, pending_owner in seen_tags.items():
            current_owner = current_by_tag.get(stored_tag)
            if current_owner is not None and current_owner != pending_owner:
                raise AdapterError(
                    f"pending_doc_tag_collision:{stored_tag}:{pending_owner}:{current_owner}"
                )
        return ordered, "active"
    raise AdapterError("pending_state_mismatch")


def reconcile_plan_with_pending(
    plan: SyncPlan,
    *,
    notes: Iterable[NoteSnapshot],
    state: Mapping[str, Any],
    pending_paths: Iterable[str],
) -> SyncPlan:
    pending = set(pending_paths)
    if not pending:
        return plan
    current = {note.relative_path for note in notes}
    previous_raw = state.get("files") if isinstance(state, Mapping) else None
    if not isinstance(previous_raw, Mapping):
        raise AdapterError("state_files_invalid")
    previous = set(str(rel) for rel in previous_raw)
    new = set(plan.new)
    changed = set(plan.changed)
    unchanged = set(plan.unchanged)
    deleted = set(plan.deleted)
    for rel in pending:
        if rel in current:
            deleted.discard(rel)
            unchanged.discard(rel)
            if rel in previous:
                new.discard(rel)
                changed.add(rel)
            else:
                changed.discard(rel)
                new.add(rel)
        else:
            new.discard(rel)
            changed.discard(rel)
            unchanged.discard(rel)
            deleted.add(rel)
    ordering = lambda value: (value.casefold(), value)
    return SyncPlan(
        tuple(sorted(new, key=ordering)),
        tuple(sorted(changed, key=ordering)),
        tuple(sorted(unchanged, key=ordering)),
        tuple(sorted(deleted, key=ordering)),
    )


def _report_count(report: Mapping[str, Any], key: str, relative_path: str) -> int:
    value = report.get(key, 0)
    try:
        number = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise AdapterError(f"study_report_invalid:{relative_path}:{key}") from exc
    if number < 0:
        raise AdapterError(f"study_report_invalid:{relative_path}:{key}")
    return number


def _validate_study_report(relative_path: str, report: Mapping[str, Any]) -> None:
    skipped = _report_count(report, "skipped", relative_path)
    chars_truncated = _report_count(report, "chars_truncated", relative_path)
    chunks_truncated = _report_count(report, "chunks_truncated", relative_path)
    if skipped or chars_truncated or chunks_truncated:
        raise AdapterError(
            "study_partial:"
            f"{relative_path}:skipped={skipped}:"
            f"chars_truncated={chars_truncated}:chunks_truncated={chunks_truncated}"
        )


def _resnapshot_matches(note: NoteSnapshot, vault_root: Path) -> bool:
    root_real = vault_root.resolve(strict=True)
    now = _strict_utf8_snapshot(
        Path(note.absolute_path), root_real, max_file_bytes=max(note.size, 1)
    )
    return (
        now.relative_path == note.relative_path
        and now.size == note.size
        and now.mtime_ns == note.mtime_ns
        and now.sha256 == note.sha256
    )


def apply_plan(
    *,
    store: Any,
    vault_root: Path,
    notes: Iterable[NoteSnapshot],
    plan: SyncPlan,
    study_document: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    by_rel = {note.relative_path: note for note in notes}
    reports: dict[str, Any] = {"studied": {}, "faded": {}}
    for rel in (*plan.new, *plan.changed):
        note = by_rel.get(rel)
        if note is None:
            raise AdapterError(f"plan_missing_current_note:{rel}")
        if not _resnapshot_matches(note, vault_root):
            raise AdapterError(f"markdown_changed_before_study:{rel}")
        try:
            report = study_document(
                store,
                path=Path(note.absolute_path),
                source_name=rel,
                session_id=SESSION_ID,
                critic=None,
            )
        except Exception as exc:
            raise AdapterError(f"study_call_failed:{rel}:{type(exc).__name__}") from exc
        if not isinstance(report, Mapping):
            raise AdapterError(f"study_invalid_report:{rel}")
        _validate_study_report(rel, report)
        if not _resnapshot_matches(note, vault_root):
            raise AdapterError(f"markdown_changed_during_study:{rel}")
        reports["studied"][rel] = dict(report)
    for rel in plan.deleted:
        source_path = _vault_source_path(vault_root, rel)
        if os.path.lexists(source_path):
            raise AdapterError(f"markdown_reappeared_before_fade:{rel}")
        try:
            report = study_document(
                store, text="", source_name=rel, session_id=SESSION_ID, critic=None
            )
        except Exception as exc:
            raise AdapterError(f"fade_call_failed:{rel}:{type(exc).__name__}") from exc
        if not isinstance(report, Mapping):
            raise AdapterError(f"fade_invalid_report:{rel}")
        _validate_study_report(rel, report)
        if os.path.lexists(source_path):
            raise AdapterError(f"markdown_reappeared_during_fade:{rel}")
        reports["faded"][rel] = dict(report)
    return reports


def _validate_vendor_contract(
    doc_tag_fn: Callable[[str], str],
    study_document: Callable[..., dict[str, Any]],
) -> None:
    try:
        doc_params = inspect.signature(doc_tag_fn).parameters
        study_params = inspect.signature(study_document).parameters
    except (TypeError, ValueError) as exc:
        raise AdapterError("iai_signature_unavailable") from exc
    if "source_name" not in doc_params:
        raise AdapterError("iai_doc_tag_signature_mismatch")
    required = {"store", "path", "text", "source_name", "session_id", "critic"}
    missing = sorted(required.difference(study_params))
    if missing:
        raise AdapterError(f"iai_study_signature_mismatch:{','.join(missing)}")


def load_iai_runtime(expected_version: str = EXPECTED_IAI_VERSION) -> IaiRuntime:
    try:
        version = importlib.metadata.version("iai-pme")
    except importlib.metadata.PackageNotFoundError as exc:
        raise AdapterError("iai_pme_not_installed") from exc
    if version != expected_version:
        raise AdapterError(f"iai_version_mismatch:{version}!={expected_version}")
    try:
        from iai_mcp.hippo import AccessMode
        from iai_mcp.store import MemoryStore
        from iai_mcp.study import _doc_tag, study_document
    except Exception as exc:
        raise AdapterError(f"iai_import_failed:{type(exc).__name__}") from exc
    _validate_vendor_contract(_doc_tag, study_document)

    def _open(store_root: Path):
        return MemoryStore(
            store_root, access_mode=AccessMode.SHARED, persist_index=False
        )

    return IaiRuntime(version, _doc_tag, study_document, _open)


def _print_plan(
    plan: SyncPlan,
    *,
    file_count: int,
    vault_root: Path,
    store_root: Path,
    state_file: Path,
    iai_version: str,
    apply: bool,
    canonical_store_present: bool,
) -> None:
    mode = "APPLY" if apply else "PLAN_ONLY"
    print(f"ORION_VAULT_MARKDOWN_INGEST_MODE={mode}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_VAULT={vault_root.resolve(strict=True)}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_STORE={store_root}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_STATE={state_file}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_SESSION={SESSION_ID}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_IAI_VERSION={iai_version}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_FILES={file_count}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_NEW={len(plan.new)}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_CHANGED={len(plan.changed)}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_UNCHANGED={len(plan.unchanged)}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_DELETED={len(plan.deleted)}")
    print("ORION_VAULT_MARKDOWN_INGEST_REJECTED=0")
    print("ORION_VAULT_MARKDOWN_INGEST_DOC_TAG_COLLISIONS=0")
    print(
        "ORION_VAULT_MARKDOWN_INGEST_CANONICAL_STORE_PRESENT="
        + str(canonical_store_present).lower()
    )
    print(
        "ORION_VAULT_MARKDOWN_INGEST_APPLY_PRECHECK_PERMITTED="
        + str(canonical_store_present).lower()
    )


def _json_result(
    *,
    runtime: IaiRuntime,
    vault_root: Path,
    store_root: Path,
    state_file: Path,
    notes: list[NoteSnapshot],
    doc_tags: Mapping[str, str],
    plan: SyncPlan,
    applied: bool,
    canonical_store_present: bool,
    reports: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "applied" if applied else "planned",
        "iai_version": runtime.version,
        "session_id": SESSION_ID,
        "vault_root": str(vault_root.resolve(strict=True)),
        "store_root": _canonical_path_text(store_root),
        "state_file": str(state_file),
        "file_count": len(notes),
        "rejected_files": 0,
        "doc_tag_collisions": 0,
        "canonical_store_present": canonical_store_present,
        "apply_precheck_permitted": canonical_store_present,
        "plan": asdict(plan),
        "doc_tags": dict(doc_tags),
        "reports": dict(reports or {}),
        "vault_mutation": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or apply Markdown-only vault ingestion through native iai study semantics."
    )
    parser.add_argument(
        "--vault-root",
        type=Path,
        default=Path(os.environ.get("ORION_VAULT_ROOT", str(DEFAULT_VAULT_ROOT))),
    )
    parser.add_argument("--store-root", type=Path, default=_default_store_root())
    parser.add_argument("--state-file", type=Path, default=None)
    parser.add_argument("--max-files", type=int, default=MAX_VAULT_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=MAX_SOURCE_FILE_BYTES)
    parser.add_argument("--expected-files", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


_DISABLED = (
    "ORION_VAULT_MARKDOWN_INGEST=FAIL:"
    "internal_core_entrypoint_disabled_use_orion_vault_markdown_ingest.py"
)


def main(_argv: list[str] | None = None) -> int:
    """Fail closed if the internal primitive module is invoked as a CLI."""
    print(_DISABLED, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
