#!/usr/bin/env python3
"""Orion DC-02 Markdown-only native iai ingestion adapter.

This adapter intentionally owns only the source boundary and sync checkpoint.
iai owns extraction, chunking, embedding, deduplication, doc tags, graph
weaving, supersession, recall self-test, and persistence.

Default mode is read-only planning. Pass --apply to mutate the iai store.
The vault itself is never written.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

EXPECTED_IAI_VERSION = "3.3.0"
SESSION_ID = "vault-study"
DEFAULT_VAULT_ROOT = Path(r"C:\Personal\Me")
MAX_VAULT_FILES = 5000
MAX_SOURCE_FILE_BYTES = 2_000_000
STATE_SCHEMA_VERSION = 1


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


def _is_reparse_point(path: Path) -> bool:
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


def _strict_utf8_snapshot(path: Path, root_real: Path) -> NoteSnapshot:
    if _is_reparse_point(path):
        raise AdapterError(f"unsafe_reparse_markdown:{path}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise AdapterError(f"markdown_resolve_failed:{path}:{type(exc).__name__}") from exc
    if not _contained(resolved, root_real):
        raise AdapterError(f"markdown_escaped_vault:{path}")
    try:
        data = resolved.read_bytes()
        # Retrieval currently decodes source notes as strict UTF-8. Enforce the
        # same contract at ingestion so every indexed note remains resolvable.
        data.decode("utf-8")
        info = resolved.stat()
    except UnicodeDecodeError as exc:
        raise AdapterError(f"markdown_not_utf8:{resolved}") from exc
    except OSError as exc:
        raise AdapterError(f"markdown_read_failed:{resolved}:{type(exc).__name__}") from exc
    return NoteSnapshot(
        relative_path=resolved.relative_to(root_real).as_posix(),
        absolute_path=str(resolved),
        size=len(data),
        mtime_ns=info.st_mtime_ns,
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

    for dirpath, dirnames, filenames in os.walk(root_real, followlinks=False):
        current = Path(dirpath)
        safe_dirs: list[str] = []
        for name in sorted(dirnames):
            child = current / name
            if _is_reparse_point(child):
                continue
            try:
                child_real = child.resolve(strict=True)
            except OSError:
                continue
            if _contained(child_real, root_real):
                safe_dirs.append(name)
        dirnames[:] = safe_dirs

        for name in sorted(filenames):
            path = current / name
            if path.suffix.casefold() != ".md":
                continue
            if _is_reparse_point(path):
                continue
            snap = _strict_utf8_snapshot(path, root_real)
            if snap.size > max_file_bytes:
                raise AdapterError(
                    f"markdown_file_too_large:{snap.relative_path}:{snap.size}>{max_file_bytes}"
                )
            folded = snap.relative_path.casefold()
            previous = seen_casefold.get(folded)
            if previous is not None and previous != snap.relative_path:
                raise AdapterError(
                    f"casefold_path_collision:{previous}:{snap.relative_path}"
                )
            seen_casefold[folded] = snap.relative_path
            notes.append(snap)
            if len(notes) > max_files:
                raise AdapterError(f"vault_file_limit_exceeded:{len(notes)}>{max_files}")

    notes.sort(key=lambda item: item.relative_path.casefold())
    return notes


def validate_doc_tag_uniqueness(
    notes: Iterable[NoteSnapshot],
    doc_tag_fn: Callable[[str], str],
) -> dict[str, str]:
    """Return path->doc_tag, refusing vendor doc-tag collisions."""
    by_tag: dict[str, str] = {}
    by_path: dict[str, str] = {}
    for note in notes:
        tag = str(doc_tag_fn(note.relative_path))
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


def load_state(state_file: Path, vault_root: Path) -> dict[str, Any]:
    if not state_file.exists():
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "session_id": SESSION_ID,
            "vault_root": str(vault_root.resolve(strict=True)),
            "files": {},
        }
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
    expected_root = str(vault_root.resolve(strict=True))
    stored_root = str(raw.get("vault_root") or "")
    if os.path.normcase(stored_root) != os.path.normcase(expected_root):
        raise AdapterError(f"state_vault_root_mismatch:{stored_root}:{expected_root}")
    files = raw.get("files")
    if not isinstance(files, dict):
        raise AdapterError("state_files_invalid")
    return raw


def build_plan(
    notes: Iterable[NoteSnapshot],
    state: Mapping[str, Any],
) -> SyncPlan:
    current = {note.relative_path: note for note in notes}
    previous_raw = state.get("files") if isinstance(state, Mapping) else {}
    previous = previous_raw if isinstance(previous_raw, Mapping) else {}

    new: list[str] = []
    changed: list[str] = []
    unchanged: list[str] = []

    for rel in sorted(current, key=str.casefold):
        old = previous.get(rel)
        if not isinstance(old, Mapping):
            new.append(rel)
        elif str(old.get("sha256") or "") != current[rel].sha256:
            changed.append(rel)
        else:
            unchanged.append(rel)

    deleted = sorted(
        (str(rel) for rel in previous.keys() if rel not in current),
        key=str.casefold,
    )
    return SyncPlan(
        new=tuple(new),
        changed=tuple(changed),
        unchanged=tuple(unchanged),
        deleted=tuple(deleted),
    )


def _state_payload(
    vault_root: Path,
    notes: Iterable[NoteSnapshot],
    doc_tags: Mapping[str, str],
    iai_version: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "session_id": SESSION_ID,
        "vault_root": str(vault_root.resolve(strict=True)),
        "iai_version": iai_version,
        "files": {
            note.relative_path: note.state_value(doc_tags[note.relative_path])
            for note in sorted(notes, key=lambda item: item.relative_path.casefold())
        },
    }


def write_state_atomic(state_file: Path, payload: Mapping[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=state_file.name + ".",
        suffix=".tmp",
        dir=str(state_file.parent),
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, state_file)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _validate_study_report(relative_path: str, report: Mapping[str, Any]) -> None:
    skipped = int(report.get("skipped") or 0)
    chars_truncated = int(report.get("chars_truncated") or 0)
    chunks_truncated = int(report.get("chunks_truncated") or 0)
    if skipped or chars_truncated or chunks_truncated:
        raise AdapterError(
            "study_partial:"
            f"{relative_path}:skipped={skipped}:"
            f"chars_truncated={chars_truncated}:chunks_truncated={chunks_truncated}"
        )


def _resnapshot_matches(note: NoteSnapshot, vault_root: Path) -> bool:
    root_real = vault_root.resolve(strict=True)
    now = _strict_utf8_snapshot(Path(note.absolute_path), root_real)
    return now.sha256 == note.sha256 and now.relative_path == note.relative_path


def apply_plan(
    *,
    store: Any,
    vault_root: Path,
    notes: Iterable[NoteSnapshot],
    plan: SyncPlan,
    study_document: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Apply current/new files first, then fade deletions, matching iai watch order."""
    by_rel = {note.relative_path: note for note in notes}
    reports: dict[str, Any] = {"studied": {}, "faded": {}}

    for rel in (*plan.new, *plan.changed):
        note = by_rel[rel]
        report = study_document(
            store,
            path=Path(note.absolute_path),
            source_name=rel,
            session_id=SESSION_ID,
            critic=None,
        )
        if not isinstance(report, Mapping):
            raise AdapterError(f"study_invalid_report:{rel}")
        _validate_study_report(rel, report)
        if not _resnapshot_matches(note, vault_root):
            raise AdapterError(f"markdown_changed_during_study:{rel}")
        reports["studied"][rel] = dict(report)

    # Renames intentionally appear as "new current path" + "deleted old path".
    # Processing current paths first allows iai shared ownership to attach the
    # new doc tag before the old owner is disowned/faded.
    for rel in plan.deleted:
        report = study_document(
            store,
            text="",
            source_name=rel,
            session_id=SESSION_ID,
            critic=None,
        )
        if not isinstance(report, Mapping):
            raise AdapterError(f"fade_invalid_report:{rel}")
        _validate_study_report(rel, report)
        reports["faded"][rel] = dict(report)

    return reports


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
    except Exception as exc:  # noqa: BLE001 - runtime preflight must fail closed
        raise AdapterError(f"iai_import_failed:{type(exc).__name__}") from exc

    def _open(store_root: Path):
        return MemoryStore(
            store_root,
            access_mode=AccessMode.SHARED,
            persist_index=False,
        )

    return IaiRuntime(
        version=version,
        doc_tag=_doc_tag,
        study_document=study_document,
        open_store=_open,
    )


def _print_plan(plan: SyncPlan, *, file_count: int, state_file: Path, apply: bool) -> None:
    mode = "APPLY" if apply else "PLAN_ONLY"
    print(f"ORION_VAULT_MARKDOWN_INGEST_MODE={mode}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_FILES={file_count}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_NEW={len(plan.new)}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_CHANGED={len(plan.changed)}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_UNCHANGED={len(plan.unchanged)}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_DELETED={len(plan.deleted)}")
    print(f"ORION_VAULT_MARKDOWN_INGEST_STATE={state_file}")


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
    reports: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "applied" if applied else "planned",
        "iai_version": runtime.version,
        "session_id": SESSION_ID,
        "vault_root": str(vault_root),
        "store_root": str(store_root),
        "state_file": str(state_file),
        "file_count": len(notes),
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    vault_root = args.vault_root.expanduser()
    store_root = args.store_root.expanduser()
    state_file = (
        args.state_file.expanduser()
        if args.state_file is not None
        else _default_state_file(store_root)
    )

    try:
        runtime = load_iai_runtime()
        notes = scan_markdown_vault(
            vault_root,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
        )
        if args.expected_files is not None and len(notes) != args.expected_files:
            raise AdapterError(
                f"expected_file_count_mismatch:{len(notes)}!={args.expected_files}"
            )
        validate_state_location(state_file, vault_root)
        validate_store_location(store_root, vault_root)
        doc_tags = validate_doc_tag_uniqueness(notes, runtime.doc_tag)
        state = load_state(state_file, vault_root)
        plan = build_plan(notes, state)

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
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                _print_plan(
                    plan,
                    file_count=len(notes),
                    state_file=state_file,
                    apply=False,
                )
                print("ORION_VAULT_MARKDOWN_INGEST_VAULT_MUTATION=false")
                print("ORION_VAULT_MARKDOWN_INGEST_STORE_MUTATION=false")
                print("ORION_VAULT_MARKDOWN_INGEST=PLAN_PASS")
            return 0

        db_path = store_root / "hippo" / "brain.sqlite3"
        if not db_path.is_file():
            raise AdapterError(f"canonical_store_missing:{db_path}")

        reports: dict[str, Any] = {"studied": {}, "faded": {}}
        if plan.mutation_count:
            try:
                store = runtime.open_store(store_root)
            except Exception as exc:  # noqa: BLE001 - lock/backend errors fail closed
                raise AdapterError(f"store_open_failed:{type(exc).__name__}:{exc}") from exc
            try:
                reports = apply_plan(
                    store=store,
                    vault_root=vault_root,
                    notes=notes,
                    plan=plan,
                    study_document=runtime.study_document,
                )
            finally:
                try:
                    store.close()
                except Exception as exc:  # noqa: BLE001
                    raise AdapterError(f"store_close_failed:{type(exc).__name__}") from exc

        payload = _state_payload(
            vault_root,
            notes,
            doc_tags,
            runtime.version,
        )
        write_state_atomic(state_file, payload)

        result = _json_result(
            runtime=runtime,
            vault_root=vault_root,
            store_root=store_root,
            state_file=state_file,
            notes=notes,
            doc_tags=doc_tags,
            plan=plan,
            applied=True,
            reports=reports,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            _print_plan(
                plan,
                file_count=len(notes),
                state_file=state_file,
                apply=True,
            )
            print("ORION_VAULT_MARKDOWN_INGEST_VAULT_MUTATION=false")
            print("ORION_VAULT_MARKDOWN_INGEST=APPLY_PASS")
        return 0
    except AdapterError as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}))
        else:
            print(f"ORION_VAULT_MARKDOWN_INGEST=FAIL:{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
