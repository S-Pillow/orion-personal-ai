#!/usr/bin/env python3
"""Orion DC-02 hardened transaction coordinator.

The implementation primitives live in ``orion_vault_markdown_ingest_core.py``.
This public entry point owns the transaction boundary: durable store ownership,
recovery ordering, metadata integrity, and the only supported native-store apply.
"""

from __future__ import annotations

import importlib.util
import json
import os
import secrets
import stat
import sys
import tempfile
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

# Re-export the tested primitive surface. The core's fail-closed ``main`` is not
# exported: transaction execution belongs to this coordinator only.
for _name in dir(_core):
    if not _name.startswith("__") and _name != "main":
        globals()[_name] = getattr(_core, _name)

STORE_OWNER_SCHEMA_VERSION = 1
IAI_MIN_CAPTURE_CHARS = 12


def _store_owner_file_for(store_root: Path) -> Path:
    return (
        Path(_canonical_path_text(store_root))
        / "orion"
        / "vault-markdown-ingest-owner.json"
    )


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


def _canonical_path_is_within(path: Path, root: Path) -> bool:
    candidate = Path(_canonical_path_text(path))
    boundary = Path(_canonical_path_text(root))
    try:
        candidate.relative_to(boundary)
    except ValueError:
        return False
    return True


def validate_state_store_namespace(state_file: Path, store_root: Path) -> None:
    """Keep custom state metadata out of native semantic-store namespaces."""
    if not _canonical_path_is_within(state_file, store_root):
        return
    allowed = Path(_canonical_path_text(store_root)) / "orion"
    if not _canonical_path_is_within(state_file, allowed):
        raise AdapterError(
            f"state_file_inside_semantic_store_namespace:{_canonical_path_text(state_file)}"
        )


def validate_metadata_path_integrity(path: Path, role: str) -> None:
    """Reject existing metadata sidecars that are links/reparse/special files."""
    if not os.path.lexists(path):
        return
    if _is_reparse_point(path):
        raise AdapterError(f"metadata_path_is_reparse_point:{role}:{path}")
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise AdapterError(
            f"metadata_path_stat_failed:{role}:{type(exc).__name__}"
        ) from exc
    if not stat.S_ISREG(info.st_mode):
        raise AdapterError(f"metadata_path_not_regular:{role}:{path}")


def validate_store_metadata_root(store_root: Path) -> None:
    """Require the adapter's store-local metadata directory to be a real dir."""
    metadata_root = Path(_canonical_path_text(store_root)) / "orion"
    if not os.path.lexists(metadata_root):
        return
    if _is_reparse_point(metadata_root):
        raise AdapterError(f"store_metadata_root_is_reparse_point:{metadata_root}")
    try:
        info = os.lstat(metadata_root)
    except OSError as exc:
        raise AdapterError(
            f"store_metadata_root_stat_failed:{type(exc).__name__}"
        ) from exc
    if not stat.S_ISDIR(info.st_mode):
        raise AdapterError(f"store_metadata_root_not_directory:{metadata_root}")


def validate_metadata_path_disjointness(paths: Mapping[str, Path]) -> None:
    """Reject canonical path reuse across state/recovery/owner/store roles."""
    seen: dict[str, str] = {}
    for role, path in paths.items():
        canonical = _canonical_path_text(path)
        key = os.path.normcase(canonical)
        prior_role = seen.get(key)
        if prior_role is not None:
            raise AdapterError(
                f"metadata_path_collision:{prior_role}:{role}:{canonical}"
            )
        seen[key] = role


def validate_store_semantic_boundary(
    store_root: Path, vault_root: Path, db_path: Path
) -> None:
    """Reject semantic-store aliases that escape the selected store boundary."""
    hippo_dir = store_root / "hippo"
    if _is_reparse_point(hippo_dir):
        raise AdapterError(f"canonical_store_hippo_is_reparse_point:{hippo_dir}")
    if _is_reparse_point(db_path):
        raise AdapterError(f"canonical_store_db_is_reparse_point:{db_path}")
    try:
        db_real = db_path.resolve(strict=True)
    except OSError as exc:
        raise AdapterError(
            f"canonical_store_db_resolve_failed:{type(exc).__name__}"
        ) from exc
    store_real = Path(_canonical_path_text(store_root))
    if not _contained(db_real, store_real):
        raise AdapterError(f"canonical_store_db_escaped_root:{db_real}:{store_real}")
    if _path_is_within(db_path, vault_root):
        raise AdapterError(f"canonical_store_db_inside_vault:{db_real}")


def validate_owned_store_recovery_presence(
    owner: Mapping[str, Any] | None,
    *,
    state_file: Path,
    pending_file: Path,
) -> None:
    """Do not reinterpret an owned store with lost metadata as a fresh bootstrap."""
    if owner is None:
        return
    if not state_file.exists() and not pending_file.exists():
        raise AdapterError("owned_store_missing_state_and_pending")


def _replace_atomic_durable(source: Path, destination: Path) -> None:
    """Atomically replace a metadata file with crash-durable rename semantics."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        move_file_ex = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        move_file_ex.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        move_file_ex.restype = wintypes.BOOL
        flags = 0x00000001 | 0x00000008  # REPLACE_EXISTING | WRITE_THROUGH
        if not move_file_ex(str(source), str(destination), flags):
            error = ctypes.get_last_error()
            raise OSError(
                error, f"MoveFileExW failed with error {error}", str(destination)
            )
        return

    os.replace(source, destination)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(str(destination.parent), directory_flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _write_atomic(path: Path, payload: Mapping[str, Any], error_prefix: str) -> None:
    """Write metadata via fsynced temp file + durable atomic replacement."""
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
        _replace_atomic_durable(tmp_path, path)
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


def write_store_owner_atomic(owner_file: Path, payload: Mapping[str, Any]) -> None:
    _write_atomic(owner_file, payload, "store_owner_write_failed")


def clear_pending_journal(pending_file: Path) -> None:
    """Clear recovery metadata; fsync the directory on POSIX after unlink."""
    existed = pending_file.exists() or pending_file.is_symlink()
    try:
        pending_file.unlink(missing_ok=True)
        if existed and os.name != "nt":
            directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            directory_fd = os.open(str(pending_file.parent), directory_flags)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except OSError as exc:
        raise AdapterError(f"pending_clear_failed:{type(exc).__name__}") from exc


def _validate_native_chunk_floor(relative_path: str, note: NoteSnapshot) -> None:
    """Fail before iai can supersede a nonempty document that yields no chunk."""
    try:
        text = Path(note.absolute_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AdapterError(
            f"markdown_chunk_floor_read_failed:{relative_path}:{type(exc).__name__}"
        ) from exc
    stripped = text.strip()
    if stripped and len(stripped) < IAI_MIN_CAPTURE_CHARS:
        raise AdapterError(
            f"markdown_below_iai_capture_floor:{relative_path}:"
            f"{len(stripped)}<{IAI_MIN_CAPTURE_CHARS}"
        )


def _validate_native_study_accounting(
    relative_path: str,
    note: NoteSnapshot,
    report: Mapping[str, Any],
) -> None:
    """Reject vendor reports that would silently checkpoint missing source data."""
    if "chunks_total" not in report:
        return
    total = _report_count(report, "chunks_total", relative_path)
    if note.size > 0 and total == 0:
        raise AdapterError(f"study_no_chunks_for_nonempty_source:{relative_path}")
    if all(key in report for key in ("inserted", "reinforced", "skipped")):
        accounted = sum(
            _report_count(report, key, relative_path)
            for key in ("inserted", "reinforced", "skipped")
        )
        if accounted != total:
            raise AdapterError(
                f"study_chunk_accounting_mismatch:{relative_path}:{accounted}!={total}"
            )


def apply_plan(
    *,
    store: Any,
    vault_root: Path,
    notes: Any,
    plan: SyncPlan,
    study_document: Any,
) -> dict[str, Any]:
    """Apply the native plan with source-race and report-accounting fences."""
    note_list = list(notes)
    by_rel = {note.relative_path: note for note in note_list}
    reports: dict[str, Any] = {"studied": {}, "faded": {}}

    for rel in (*plan.new, *plan.changed):
        note = by_rel.get(rel)
        if note is None:
            raise AdapterError(f"plan_missing_current_note:{rel}")
        if not _resnapshot_matches(note, vault_root):
            raise AdapterError(f"markdown_changed_before_study:{rel}")
        _validate_native_chunk_floor(rel, note)
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
        _validate_native_study_accounting(rel, note, report)
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
            vault_root,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
        )
        if args.expected_files is not None and len(notes) != args.expected_files:
            raise AdapterError(
                f"expected_file_count_mismatch:{len(notes)}!={args.expected_files}"
            )

        validate_store_location(store_root, vault_root)
        validate_store_metadata_root(store_root)

        metadata_paths = {
            "state": state_file,
            "pending": pending_file,
            "state_lock": state_lock_file,
            "store_lock": store_lock_file,
            "store_owner": owner_file,
        }
        for role, path in metadata_paths.items():
            validate_metadata_path_integrity(path, role)
            validate_state_location(path, vault_root)
        validate_state_store_namespace(state_file, store_root)

        db_path = store_root / "hippo" / "brain.sqlite3"
        validate_metadata_path_disjointness(
            {**metadata_paths, "semantic_db": db_path}
        )

        canonical_store_present = db_path.is_file()
        if canonical_store_present:
            validate_store_semantic_boundary(store_root, vault_root, db_path)
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
                plan,
                notes=notes,
                state=state,
                pending_paths=pending_paths,
            )

        owner = load_store_owner(
            owner_file,
            vault_root=vault_root,
            store_root=store_root,
            state_file=state_file,
        )
        validate_owned_store_recovery_presence(
            owner,
            state_file=state_file,
            pending_file=pending_file,
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

        if pending_status == "completed":
            clear_pending_journal(pending_file)

        reports: dict[str, Any] = {"studied": {}, "faded": {}}
        checkpoint_id = _checkpoint_identity(state)
        owner_claimed_for_mutation = False

        if plan.mutation_count:
            target_checkpoint_id = secrets.token_hex(32)

            # Recovery must exist before either the durable owner claim or native
            # store open. Thus a crash cannot leave an owned-but-unrecoverable
            # first bootstrap, and any later store open is journal-covered.
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
            if owner is None:
                write_store_owner_atomic(
                    owner_file,
                    _store_owner_payload(
                        vault_root=vault_root,
                        store_root=store_root,
                        state_file=state_file,
                    ),
                )
                owner_claimed_for_mutation = True

            try:
                store = runtime.open_store(store_root)
            except Exception as exc:
                raise AdapterError(
                    f"store_open_failed:{type(exc).__name__}:{exc}"
                ) from exc
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
                    raise AdapterError(
                        f"store_close_failed:{type(exc).__name__}"
                    ) from exc
            checkpoint_id = target_checkpoint_id
        elif pending_status != "completed" and state.get("successful_run_utc") is None:
            checkpoint_id = secrets.token_hex(32)

        final_notes = scan_markdown_vault(
            vault_root,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
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

        # A no-mutation first apply claims ownership only after its successful
        # checkpoint exists. A mutating first apply already claimed ownership
        # after the pending journal was durable and before store open.
        if owner is None and not owner_claimed_for_mutation:
            write_store_owner_atomic(
                owner_file,
                _store_owner_payload(
                    vault_root=vault_root,
                    store_root=store_root,
                    state_file=state_file,
                ),
            )

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
                    "ORION_VAULT_MARKDOWN_INGEST=LOCK_RELEASE_WARNING:"
                    f"{type(exc).__name__}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())
