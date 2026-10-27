"""DC-02 immutable model and portable source-name contract."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

EXPECTED_IAI_VERSION = "3.3.0"
SESSION_ID = "vault-study"
DEFAULT_VAULT_ROOT = Path(r"C:\Personal\Me")
MAX_VAULT_FILES = 5000
MAX_SOURCE_FILE_BYTES = 2_000_000
STATE_SCHEMA_VERSION = 3
PENDING_SCHEMA_VERSION = 3
OWNER_SCHEMA_VERSION = 2
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_INVALID_CHARS = frozenset('<>:"\\|?*')
_WINDOWS_RESERVED_STEMS = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
    | {f"COM{i}" for i in "¹²³"}
    | {f"LPT{i}" for i in "¹²³"}
)


class AdapterError(RuntimeError):
    """Fail-closed admission, recovery, or transaction error."""


@dataclass(frozen=True)
class NoteSnapshot:
    relative_path: str
    absolute_path: str
    size: int
    mtime_ns: int
    sha256: str

    def state_value(self, doc_tag: str) -> dict[str, Any]:
        validate_source_name(self.relative_path)
        if not isinstance(self.size, int) or isinstance(self.size, bool) or self.size < 0:
            raise AdapterError(f"snapshot_size_invalid:{self.relative_path}")
        if not isinstance(self.mtime_ns, int) or isinstance(self.mtime_ns, bool) or self.mtime_ns < 0:
            raise AdapterError(f"snapshot_mtime_invalid:{self.relative_path}")
        if not isinstance(self.sha256, str) or not _SHA256_RE.fullmatch(self.sha256):
            raise AdapterError(f"snapshot_sha256_invalid:{self.relative_path}")
        if not isinstance(doc_tag, str) or not doc_tag.startswith("doc:") or len(doc_tag) <= 4:
            raise AdapterError(f"snapshot_doc_tag_invalid:{self.relative_path}")
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
    study_document: Callable[..., Mapping[str, Any]]
    open_store: Callable[[Path], Any]


@dataclass(frozen=True)
class MetadataPaths:
    root: Path
    state: Path
    pending: Path
    owner: Path
    lock: Path


@dataclass(frozen=True)
class PendingStatus:
    status: str
    paths: tuple[str, ...]
    doc_tags: Mapping[str, str]


def canonical_path(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except OSError as exc:
        raise AdapterError(f"canonical_path_failed:{path}:{type(exc).__name__}") from exc


def vault_root_text(vault_root: Path) -> str:
    try:
        return str(vault_root.resolve(strict=True))
    except OSError as exc:
        raise AdapterError(f"vault_root_resolve_failed:{type(exc).__name__}") from exc


def metadata_paths(store_root: Path) -> MetadataPaths:
    root = canonical_path(store_root) / "orion"
    return MetadataPaths(
        root=root,
        state=root / "vault-markdown-ingest-state.json",
        pending=root / "vault-markdown-ingest-pending.json",
        owner=root / "vault-markdown-ingest-owner.json",
        lock=root / "vault-markdown-ingest.apply.lock",
    )


def validate_source_name(relative_path: str) -> str:
    """Validate one canonical POSIX source name against the Windows vault grammar."""
    if not isinstance(relative_path, str) or not relative_path or "\\" in relative_path:
        raise AdapterError(f"source_name_invalid:{relative_path}")
    try:
        relative_path.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise AdapterError("source_name_invalid_unicode") from exc
    posix = PurePosixPath(relative_path)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise AdapterError(f"source_name_invalid:{relative_path}")
    if posix.as_posix() != relative_path:
        raise AdapterError(f"source_name_noncanonical:{relative_path}")
    if posix.suffix.casefold() != ".md":
        raise AdapterError(f"source_name_not_markdown:{relative_path}")
    for part in posix.parts:
        if part.endswith((" ", ".")):
            raise AdapterError(f"source_name_windows_trailing_char:{relative_path}")
        if any(ord(ch) < 32 or ch in _WINDOWS_INVALID_CHARS for ch in part):
            raise AdapterError(f"source_name_windows_invalid_char:{relative_path}")
        stem = part.split(".", 1)[0].rstrip(" .").upper()
        if stem in _WINDOWS_RESERVED_STEMS:
            raise AdapterError(f"source_name_windows_reserved:{relative_path}")
    return relative_path
