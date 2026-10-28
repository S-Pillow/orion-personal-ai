"""DC-02 pinned iai 3.3.0 adapter and native report acceptance."""
from __future__ import annotations

import importlib.metadata
import inspect
import os
import stat
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping

from orion_vault_ingest_model import (
    AdapterError,
    DEFAULT_VAULT_ROOT,
    EXPECTED_IAI_VERSION,
    IaiRuntime,
    MetadataPaths,
    NoteSnapshot,
    MAX_SOURCE_FILE_BYTES,
    MAX_VAULT_FILES,
    SESSION_ID,
    SyncPlan,
)


def _report_count(report: Mapping[str, Any], key: str, rel: str) -> int:
    value = report.get(key, 0)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AdapterError(f"study_report_invalid:{rel}:{key}")
    return value


def validate_study_report(rel: str, report: Mapping[str, Any], *, native: bool) -> None:
    for key in ("skipped", "chars_truncated", "chunks_truncated"):
        if _report_count(report, key, rel):
            raise AdapterError(f"study_partial:{rel}:{key}={report.get(key)}")
    if not native:
        return
    required = ("chunks_total", "inserted", "reinforced", "skipped", "recall_tested", "recall_verified")
    for key in required:
        if key not in report:
            raise AdapterError(f"study_report_missing:{rel}:{key}")
    total = _report_count(report, "chunks_total", rel)
    inserted = _report_count(report, "inserted", rel)
    reinforced = _report_count(report, "reinforced", rel)
    skipped = _report_count(report, "skipped", rel)
    if inserted + reinforced + skipped != total:
        raise AdapterError(f"study_chunk_accounting_mismatch:{rel}")
    tested = _report_count(report, "recall_tested", rel)
    verified = _report_count(report, "recall_verified", rel)
    expected = min(5, inserted + reinforced)
    if tested != expected:
        raise AdapterError(f"study_recall_test_count_mismatch:{rel}:{tested}!={expected}")
    if verified != tested:
        raise AdapterError(f"study_recall_self_test_miss:{rel}:{verified}!={tested}")


def _is_native_study(fn: Any) -> bool:
    return getattr(fn, "__module__", "") == "iai_mcp.study" and getattr(fn, "__name__", "") == "study_document"


def apply_plan(store: Any, staged: Mapping[str, Path], plan: SyncPlan, study_document: Callable[..., Mapping[str, Any]]) -> dict[str, Any]:
    reports: dict[str, Any] = {"studied": {}, "faded": {}}
    native = _is_native_study(study_document)
    for rel in plan.new + plan.changed:
        path = staged.get(rel)
        if path is None:
            raise AdapterError(f"staged_source_missing:{rel}")
        try:
            report = study_document(store, path=path, source_name=rel, session_id=SESSION_ID, critic=None)
        except Exception as exc:
            raise AdapterError(f"study_call_failed:{rel}:{type(exc).__name__}") from exc
        if not isinstance(report, Mapping):
            raise AdapterError(f"study_invalid_report:{rel}")
        validate_study_report(rel, report, native=native)
        reports["studied"][rel] = dict(report)
    for rel in plan.deleted:
        try:
            report = study_document(store, text="", source_name=rel, session_id=SESSION_ID, critic=None)
        except Exception as exc:
            raise AdapterError(f"fade_call_failed:{rel}:{type(exc).__name__}") from exc
        if not isinstance(report, Mapping):
            raise AdapterError(f"fade_invalid_report:{rel}")
        validate_study_report(rel, report, native=native)
        reports["faded"][rel] = dict(report)
    return reports


def _normalize_expected_identity(expected: Mapping[str, Any]) -> tuple[str, int, int]:
    path = expected.get("path")
    device = expected.get("device")
    inode = expected.get("inode")
    if not isinstance(path, str) or not path:
        raise AdapterError("open_store_expected_db_identity_invalid")
    if not isinstance(device, int) or isinstance(device, bool) or device < 0:
        raise AdapterError("open_store_expected_db_identity_invalid")
    if not isinstance(inode, int) or isinstance(inode, bool) or inode <= 0:
        raise AdapterError("open_store_expected_db_identity_invalid")
    return path, device, inode


def _open_descriptor_matches_identity(device: int, inode: int) -> bool | None:
    """Confirm a live process descriptor references the expected file instance.

    Linux exposes descriptors through /proc/self/fd; macOS and other POSIX
    systems commonly expose /dev/fd. Windows has no equivalent portable
    process-FD namespace, so its live-connection check relies on the driver
    connection plus the open-time path identity below.
    """
    if os.name == "nt":
        return None
    roots = (Path("/proc/self/fd"), Path("/dev/fd"))
    fd_root = next((root for root in roots if root.is_dir()), None)
    if fd_root is None:
        return None
    try:
        names = os.listdir(fd_root)
    except OSError as exc:
        raise AdapterError(f"open_store_fd_probe_failed:{type(exc).__name__}") from exc
    for name in names:
        if not name.isdigit():
            continue
        try:
            info = os.stat(fd_root / name)
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode) and int(info.st_dev) == device and int(info.st_ino) == inode:
            return True
    return False


def verify_open_store_db_identity(store: Any, expected: Mapping[str, Any]) -> None:
    """Bind the transaction identity to the DB used by the live native store.

    Pinned iai 3.3.0 exposes MemoryStore.db (HippoDB), whose _conn is the live
    writer connection and whose _db_path is the path passed to that connection.
    This probe runs after MemoryStore construction but before any study/fade call.
    It therefore closes the swap window between the surrounding pre-open and
    post-close filesystem identity checks.
    """
    wanted_path, wanted_dev, wanted_ino = _normalize_expected_identity(expected)
    db = getattr(store, "db", None)
    if db is None:
        raise AdapterError("open_store_db_handle_unavailable")
    conn = getattr(db, "_conn", None)
    db_path_text = getattr(db, "_db_path", None)
    driver = getattr(db, "_storage_driver", None)
    if conn is None or not isinstance(db_path_text, str) or not db_path_text:
        raise AdapterError("open_store_db_handle_unavailable")
    if driver not in {"stdlib", "lilli"}:
        raise AdapterError("open_store_storage_driver_unexpected")

    db_path = Path(db_path_text)
    try:
        resolved = db_path.resolve(strict=True)
        info = os.stat(db_path, follow_symlinks=False)
        wanted_resolved = Path(wanted_path).resolve(strict=True)
    except OSError as exc:
        raise AdapterError(f"open_store_db_identity_stat_failed:{type(exc).__name__}") from exc
    if os.path.normcase(str(resolved)) != os.path.normcase(str(wanted_resolved)):
        raise AdapterError("open_store_db_path_mismatch")
    if int(info.st_dev) != wanted_dev or int(info.st_ino) != wanted_ino:
        raise AdapterError("open_store_db_identity_mismatch")

    if driver == "stdlib":
        try:
            cursor = conn.execute("PRAGMA database_list")
            rows = cursor.fetchall()
        except Exception as exc:
            raise AdapterError(f"open_store_connection_probe_failed:{type(exc).__name__}") from exc
        main_paths: list[str] = []
        for row in rows:
            try:
                name = row[1]
                filename = row[2]
            except (IndexError, KeyError, TypeError):
                continue
            if str(name) == "main" and filename:
                main_paths.append(str(filename))
        if len(main_paths) != 1:
            raise AdapterError("open_store_connection_main_db_unavailable")
        try:
            connection_path = Path(main_paths[0]).resolve(strict=True)
        except OSError as exc:
            raise AdapterError(f"open_store_connection_path_failed:{type(exc).__name__}") from exc
        if os.path.normcase(str(connection_path)) != os.path.normcase(str(wanted_resolved)):
            raise AdapterError("open_store_connection_db_path_mismatch")

    descriptor_match = _open_descriptor_matches_identity(wanted_dev, wanted_ino)
    if descriptor_match is False:
        raise AdapterError("open_store_db_handle_identity_mismatch")
    if descriptor_match is None and os.name != "nt":
        raise AdapterError("open_store_db_handle_probe_unavailable")


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
    try:
        params = inspect.signature(study_document).parameters
        doc_params = inspect.signature(_doc_tag).parameters
    except (TypeError, ValueError) as exc:
        raise AdapterError("iai_signature_unavailable") from exc
    if "source_name" not in doc_params:
        raise AdapterError("iai_doc_tag_signature_mismatch")
    if not {"store", "path", "text", "source_name", "session_id", "critic"}.issubset(params):
        raise AdapterError("iai_study_signature_mismatch")

    def open_store(root: Path):
        return MemoryStore(root, access_mode=AccessMode.SHARED, persist_index=False)

    return IaiRuntime(
        version=version,
        doc_tag=_doc_tag,
        study_document=study_document,
        open_store=open_store,
        verify_open_store=verify_open_store_db_identity,
    )


def result_payload(
    runtime: IaiRuntime,
    vault_root: Path,
    store_root: Path,
    paths: MetadataPaths,
    notes: list[NoteSnapshot],
    plan: SyncPlan,
    doc_tags: Mapping[str, str],
    applied: bool,
    pending_status: str,
    reports: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the stable operator/result envelope without mutating any state."""
    return {
        "status": "applied" if applied else "planned",
        "iai_version": runtime.version,
        "session_id": SESSION_ID,
        "vault_root": str(vault_root.resolve(strict=True)),
        "store_root": str(store_root.expanduser().resolve(strict=False)),
        "state_file": str(paths.state),
        "pending_file": str(paths.pending),
        "file_count": len(notes),
        "pending_status": pending_status,
        "plan": asdict(plan),
        "doc_tags": dict(doc_tags),
        "reports": dict(reports or {}),
        "vault_mutation": False,
        "store_mutation": bool(applied and plan.mutation_count),
    }


def parse_args(argv: list[str] | None = None):
    import argparse
    parser = argparse.ArgumentParser(description="Plan or apply Orion Markdown ingestion through native iai 3.3.0.")
    parser.add_argument("--vault-root", type=Path, default=Path(os.environ.get("ORION_VAULT_ROOT", str(DEFAULT_VAULT_ROOT))))
    parser.add_argument("--store-root", type=Path, default=Path(os.environ.get("IAI_MCP_STORE", str(Path.home() / ".iai-mcp"))))
    parser.add_argument("--max-files", type=int, default=MAX_VAULT_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=MAX_SOURCE_FILE_BYTES)
    parser.add_argument("--expected-files", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)
