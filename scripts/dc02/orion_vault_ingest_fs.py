"""DC-02 filesystem admission, immutable staging, durability, and one apply lock."""
from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping

from orion_vault_ingest_model import (
    AdapterError,
    MAX_SOURCE_FILE_BYTES,
    MAX_VAULT_FILES,
    MetadataPaths,
    NoteSnapshot,
    SyncPlan,
    canonical_path,
    validate_source_name,
    vault_root_text,
)


class ApplyLock:
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


class StagedSources:
    def __init__(self, tempdir: tempfile.TemporaryDirectory[str], paths: Mapping[str, Path]) -> None:
        self._tempdir = tempdir
        self.paths = dict(paths)

    def close(self) -> None:
        self._tempdir.cleanup()


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return True
    if stat.S_ISLNK(info.st_mode):
        return True
    attrs = getattr(info, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & flag)


def _contained(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_regular_file(path: Path, *, max_bytes: int) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if os.name != "nt":
        flags |= getattr(os, "O_NONBLOCK", 0)
    fd: int | None = None
    try:
        fd = os.open(str(path), flags)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise AdapterError(f"markdown_not_regular_file:{path}")
        if getattr(before, "st_nlink", 1) > 1:
            raise AdapterError(f"markdown_has_multiple_links:{path}")
        if before.st_size > max_bytes:
            raise AdapterError(f"markdown_file_too_large:{path}:{before.st_size}>{max_bytes}")
        with os.fdopen(fd, "rb") as handle:
            fd = None
            data = handle.read(max_bytes + 1)
            after = os.fstat(handle.fileno())
        if len(data) > max_bytes:
            raise AdapterError(f"markdown_file_too_large:{path}:{len(data)}>{max_bytes}")
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or getattr(after, "st_nlink", 1) > 1
            or len(data) != after.st_size
        ):
            raise AdapterError(f"markdown_changed_during_snapshot:{path}")
        return data, after
    except AdapterError:
        raise
    except OSError as exc:
        raise AdapterError(f"markdown_read_failed:{path}:{type(exc).__name__}") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _snapshot_with_data(path: Path, root_real: Path, *, max_file_bytes: int) -> tuple[NoteSnapshot, bytes]:
    if _is_reparse_point(path):
        raise AdapterError(f"unsafe_reparse_markdown:{path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise AdapterError(f"markdown_resolve_failed:{path}:{type(exc).__name__}") from exc
    if not _contained(resolved, root_real):
        raise AdapterError(f"markdown_escaped_vault:{path}")
    try:
        relative = path.relative_to(root_real).as_posix()
    except ValueError as exc:
        raise AdapterError(f"markdown_lexically_outside_vault:{path}") from exc
    validate_source_name(relative)
    # Open the lexical vault pathname, not the resolved target, so O_NOFOLLOW
    # still protects the final component if it is swapped after the precheck.
    data, info = _read_regular_file(path, max_bytes=max_file_bytes)
    try:
        if _is_reparse_point(path):
            raise AdapterError(f"markdown_changed_during_snapshot:{relative}")
        path_after = os.stat(path, follow_symlinks=False)
        resolved_after = path.resolve(strict=True)
    except AdapterError:
        raise
    except OSError as exc:
        raise AdapterError(f"markdown_changed_during_snapshot:{relative}") from exc
    if (
        resolved_after != resolved
        or path_after.st_dev != info.st_dev
        or path_after.st_ino != info.st_ino
        or path_after.st_size != info.st_size
        or path_after.st_mtime_ns != info.st_mtime_ns
        or getattr(path_after, "st_nlink", 1) > 1
    ):
        raise AdapterError(f"markdown_changed_during_snapshot:{relative}")
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AdapterError(f"markdown_not_utf8:{relative}") from exc
    return (
        NoteSnapshot(relative, str(path), len(data), info.st_mtime_ns, hashlib.sha256(data).hexdigest()),
        data,
    )


def snapshot_file(path: Path, root_real: Path, *, max_file_bytes: int) -> NoteSnapshot:
    note, _ = _snapshot_with_data(path, root_real, max_file_bytes=max_file_bytes)
    return note


def _walk_error(exc: OSError) -> None:
    failed = getattr(exc, "filename", None) or "<vault>"
    raise AdapterError(f"vault_walk_failed:{failed}:{type(exc).__name__}") from exc


def scan_markdown_vault(
    vault_root: Path,
    *,
    max_files: int = MAX_VAULT_FILES,
    max_file_bytes: int = MAX_SOURCE_FILE_BYTES,
) -> list[NoteSnapshot]:
    if max_files < 1:
        raise AdapterError("max_files_must_be_positive")
    if max_file_bytes < 1:
        raise AdapterError("max_file_bytes_must_be_positive")
    if not vault_root.is_dir():
        raise AdapterError(f"vault_root_unavailable:{vault_root}")
    if _is_reparse_point(vault_root):
        raise AdapterError(f"vault_root_is_reparse_point:{vault_root}")
    root_real = Path(vault_root_text(vault_root))
    notes: list[NoteSnapshot] = []
    seen_casefold: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(
        root_real, topdown=True, onerror=_walk_error, followlinks=False
    ):
        current = Path(dirpath)
        safe_dirs: list[str] = []
        for name in sorted(dirnames, key=lambda value: (value.casefold(), value)):
            child = current / name
            validate_source_name(child.relative_to(root_real).as_posix() + "/x.md")
            if _is_reparse_point(child):
                raise AdapterError(f"unsafe_reparse_directory:{child}")
            try:
                child_real = child.resolve(strict=True)
            except OSError as exc:
                raise AdapterError(f"directory_resolve_failed:{child}:{type(exc).__name__}") from exc
            if not _contained(child_real, root_real):
                raise AdapterError(f"directory_escaped_vault:{child}")
            safe_dirs.append(name)
        dirnames[:] = safe_dirs
        for name in sorted(filenames, key=lambda value: (value.casefold(), value)):
            path = current / name
            if path.suffix.casefold() != ".md":
                continue
            note = snapshot_file(path, root_real, max_file_bytes=max_file_bytes)
            folded = note.relative_path.casefold()
            prior = seen_casefold.get(folded)
            if prior is not None and prior != note.relative_path:
                raise AdapterError(f"casefold_path_collision:{prior}:{note.relative_path}")
            seen_casefold[folded] = note.relative_path
            notes.append(note)
            if len(notes) > max_files:
                raise AdapterError(f"vault_file_limit_exceeded:{len(notes)}>{max_files}")
    notes.sort(key=lambda item: (item.relative_path.casefold(), item.relative_path))
    return notes


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_directory_durable(path: Path) -> None:
    missing: list[Path] = []
    cursor = path
    while not os.path.lexists(cursor):
        missing.append(cursor)
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        for created in reversed(missing):
            _fsync_directory(created.parent)
        _fsync_directory(path)


def _replace_durable(source: Path, destination: Path) -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        move = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        move.restype = wintypes.BOOL
        if not move(str(source), str(destination), 0x00000001 | 0x00000008):
            err = ctypes.get_last_error()
            raise OSError(err, f"MoveFileExW failed with error {err}", str(destination))
        return
    os.replace(source, destination)
    _fsync_directory(destination.parent)


def _atomic_write(path: Path, payload: Mapping[str, object], label: str) -> None:
    _ensure_directory_durable(path.parent)
    tmp: Path | None = None
    try:
        import json
        fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent), text=True)
        tmp = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _replace_durable(tmp, path)
        tmp = None
    except (OSError, TypeError, ValueError) as exc:
        raise AdapterError(f"{label}_write_failed:{type(exc).__name__}") from exc
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


def clear_pending(path: Path) -> None:
    existed = path.exists() or path.is_symlink()
    try:
        path.unlink(missing_ok=True)
        if existed and os.name != "nt":
            _fsync_directory(path.parent)
    except OSError as exc:
        raise AdapterError(f"pending_clear_failed:{type(exc).__name__}") from exc


def _validate_fixed_file(path: Path, label: str) -> None:
    if not os.path.lexists(path):
        return
    if _is_reparse_point(path):
        raise AdapterError(f"{label}_is_reparse_point:{path}")
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise AdapterError(f"{label}_stat_failed:{type(exc).__name__}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise AdapterError(f"{label}_not_regular:{path}")
    if getattr(info, "st_nlink", 1) > 1:
        raise AdapterError(f"{label}_has_multiple_links:{path}")


def validate_metadata_namespace(paths: MetadataPaths, vault_root: Path, store_root: Path) -> None:
    if os.path.lexists(paths.root):
        if _is_reparse_point(paths.root):
            raise AdapterError(f"metadata_root_is_reparse_point:{paths.root}")
        if not paths.root.is_dir():
            raise AdapterError(f"metadata_root_not_directory:{paths.root}")
    store = canonical_path(store_root)
    vault_real = Path(vault_root_text(vault_root))
    try:
        metadata_real = paths.root.resolve(strict=False)
    except OSError as exc:
        raise AdapterError(f"metadata_namespace_resolve_failed:{type(exc).__name__}") from exc
    if _contained(metadata_real, vault_real):
        raise AdapterError("metadata_root_inside_vault")
    if not _contained(metadata_real, store):
        raise AdapterError("metadata_root_outside_store")
    for label, path in (("state", paths.state), ("pending", paths.pending), ("owner", paths.owner), ("lock", paths.lock)):
        _validate_fixed_file(path, label)


def validate_store(vault_root: Path, store_root: Path, *, require_db: bool) -> Path:
    vault_real = Path(vault_root_text(vault_root))
    store = canonical_path(store_root)
    if _contained(store, vault_real):
        raise AdapterError("store_root_inside_vault")
    db = store / "hippo" / "brain.sqlite3"
    if not db.exists():
        if require_db:
            raise AdapterError(f"canonical_store_missing:{db}")
        return db
    _validate_fixed_file(db, "semantic_db")
    try:
        db_real = db.resolve(strict=True)
    except OSError as exc:
        raise AdapterError(f"semantic_db_resolve_failed:{type(exc).__name__}") from exc
    if not _contained(db_real, store):
        raise AdapterError("semantic_db_escaped_store")
    return db


def acquire_apply_lock(path: Path) -> ApplyLock:
    try:
        _ensure_directory_durable(path.parent)
    except OSError as exc:
        raise AdapterError(f"apply_lock_parent_failed:{type(exc).__name__}") from exc
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd: int | None = None
    try:
        fd = os.open(str(path), flags, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise AdapterError(f"apply_lock_not_regular:{path}")
        if getattr(info, "st_nlink", 1) > 1:
            raise AdapterError(f"apply_lock_has_multiple_links:{path}")
        if os.name == "nt":
            import msvcrt
            if info.st_size == 0:
                os.write(fd, b"\0")
                os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return ApplyLock(path, fd)
    except AdapterError:
        if fd is not None:
            os.close(fd)
        raise
    except OSError as exc:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        raise AdapterError(f"apply_lock_unavailable:{type(exc).__name__}") from exc


def _read_matching_snapshot(note: NoteSnapshot, vault_root: Path) -> bytes:
    current, data = _snapshot_with_data(
        Path(note.absolute_path), Path(vault_root_text(vault_root)), max_file_bytes=max(note.size, 1)
    )
    if (
        current.relative_path != note.relative_path
        or current.size != note.size
        or current.mtime_ns != note.mtime_ns
        or current.sha256 != note.sha256
    ):
        raise AdapterError(f"markdown_changed_before_staging:{note.relative_path}")
    return data


def stage_plan_sources(
    vault_root: Path,
    store_root: Path,
    notes: Iterable[NoteSnapshot],
    plan: SyncPlan,
) -> StagedSources:
    by_rel = {n.relative_path: n for n in notes}
    vault_real = Path(vault_root_text(vault_root))
    store_real = canonical_path(store_root)
    try:
        temp_base = Path(tempfile.gettempdir()).resolve(strict=True)
    except OSError as exc:
        raise AdapterError(f"staging_temp_root_failed:{type(exc).__name__}") from exc
    # Check the configured temp location before creating anything. A TEMP/TMP
    # directory under the read-only vault or canonical store is not admissible.
    if _contained(temp_base, vault_real):
        raise AdapterError(f"staging_temp_root_inside_vault:{temp_base}")
    if _contained(temp_base, store_real):
        raise AdapterError(f"staging_temp_root_inside_store:{temp_base}")
    try:
        tempdir = tempfile.TemporaryDirectory(
            prefix="orion-dc02-stage-", dir=str(temp_base), ignore_cleanup_errors=True
        )
        root = Path(tempdir.name).resolve(strict=True)
    except OSError as exc:
        raise AdapterError(f"staging_temp_create_failed:{type(exc).__name__}") from exc
    if _contained(root, vault_real) or _contained(root, store_real):
        tempdir.cleanup()
        raise AdapterError("staging_directory_boundary_violation")
    staged: dict[str, Path] = {}
    try:
        for index, rel in enumerate(plan.new + plan.changed):
            note = by_rel.get(rel)
            if note is None:
                raise AdapterError(f"plan_missing_current_note:{rel}")
            data = _read_matching_snapshot(note, vault_root)
            target = root / f"{index:06d}.md"
            try:
                with target.open("xb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.utime(target, ns=(note.mtime_ns, note.mtime_ns))
                verify = target.stat()
                staged_bytes = target.read_bytes()
            except OSError as exc:
                raise AdapterError(f"staging_io_failed:{rel}:{type(exc).__name__}") from exc
            if verify.st_size != note.size or verify.st_mtime_ns != note.mtime_ns:
                raise AdapterError(f"staging_metadata_mismatch:{rel}")
            if hashlib.sha256(staged_bytes).hexdigest() != note.sha256:
                raise AdapterError(f"staging_digest_mismatch:{rel}")
            staged[rel] = target
        return StagedSources(tempdir, staged)
    except Exception:
        tempdir.cleanup()
        raise


def validate_deleted_absence(vault_root: Path, plan: SyncPlan) -> None:
    root = Path(vault_root_text(vault_root))
    for rel in plan.deleted:
        validate_source_name(rel)
        candidate = root.joinpath(*PurePosixPath(rel).parts)
        if os.path.lexists(candidate):
            raise AdapterError(f"deleted_source_reappeared_before_apply:{rel}")
