#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
import py_compile
import socket
import sqlite3
import sys


EXPECTED_CLASSES = {
    "401 unauthorized": "auth_failed",
    "quota exceeded": "rate_limited",
    "request timed out": "timeout",
    "network unreachable": "network_error",
    "Executor dispatch failed": "dispatch_failed",
    "owner exited after restart": "interrupted",
    "empty response": "empty_response",
    "invalid config": "invalid_config",
    "other failure": "unknown",
}


def emit(key: str, value: object) -> None:
    if isinstance(value, bool):
        value = "true" if value else "false"
    print(f"{key}={value}", flush=True)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def set_home(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.environ["HERMES_HOME"] = str(path)
    os.environ.pop("HERMES_PROFILE", None)


def table_columns(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [str(row[1]) for row in conn.execute("PRAGMA table_info(executions)").fetchall()]
    finally:
        conn.close()


def row_for(db_path: Path, execution_id: str) -> dict[str, object]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM executions WHERE id=?", (execution_id,)).fetchone()
        require(row is not None, f"missing execution row {execution_id}")
        return dict(row)
    finally:
        conn.close()


def p604_schema_sql() -> str:
    return """CREATE TABLE executions (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL,
        source TEXT NOT NULL,
        process_id TEXT NOT NULL,
        pid INTEGER NOT NULL,
        process_started_at INTEGER,
        status TEXT NOT NULL CHECK(status IN
          ('claimed','running','completed','failed','unknown')),
        claimed_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        error TEXT,
        scheduled_at TEXT,
        delivery_outcome TEXT
    )"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--disposable-home", required=True)
    parser.add_argument("--prepatched", action="store_true")
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    disposable_home = Path(args.disposable_home).resolve()
    executions_path = source_root / "cron" / "executions.py"
    classifier_path = source_root / "cron" / "error_classification.py"
    health_path = source_root / "agent" / "monitoring" / "cron_health.py"

    for path in (executions_path, classifier_path, health_path):
        require(path.is_file(), f"missing {path}")

    executions_text = executions_path.read_text(encoding="utf-8")
    classifier_text = classifier_path.read_text(encoding="utf-8")
    health_text = health_path.read_text(encoding="utf-8")

    require("error_class TEXT" in executions_text, "durable schema missing error_class")
    require(
        "ALTER TABLE executions ADD COLUMN error_class TEXT" in executions_text,
        "idempotent migration missing error_class",
    )
    require(
        "error_class = None if success else classify_cron_error(detail)" in executions_text,
        "finish_execution does not classify failures durably",
    )
    require(
        "classify_cron_error(detail)" in executions_text,
        "interrupted recovery does not classify failures durably",
    )
    require(
        "from cron.error_classification import classify_cron_error" in executions_text,
        "executions.py is not using the shared classifier",
    )
    require(
        "from cron.error_classification import classify_cron_error" in health_text,
        "cron_health.py is not using the shared classifier",
    )
    require(
        "def classify_cron_error" not in health_text,
        "cron_health.py still has a duplicated classifier implementation",
    )
    require(
        "def classify_cron_error" in classifier_text,
        "shared classifier implementation missing",
    )

    compile_dir = disposable_home / "compiled"
    compile_dir.mkdir(parents=True, exist_ok=True)
    for path in (classifier_path, executions_path, health_path):
        py_compile.compile(
            str(path),
            cfile=str(compile_dir / (path.stem + ".pyc")),
            doraise=True,
        )
    emit("P6_04A_PATCHED_SOURCE_PY_COMPILE", "PASS")

    external_attempts: list[str] = []
    real_connect = socket.socket.connect

    def guarded_connect(sock, address):
        host = str(address[0]) if isinstance(address, tuple) and address else str(address)
        if host not in {"127.0.0.1", "::1", "localhost"}:
            external_attempts.append(repr(address))
            raise RuntimeError(f"P6-04A blocked external network attempt: {address!r}")
        return real_connect(sock, address)

    socket.socket.connect = guarded_connect
    sys.path.insert(0, str(source_root))

    classifier = importlib.import_module("cron.error_classification")
    for raw, expected in EXPECTED_CLASSES.items():
        actual = classifier.classify_cron_error(raw)
        require(actual == expected, f"classifier mismatch for {raw!r}: {actual} != {expected}")
    emit("P6_04A_FIXTURE_CLASSIFIER_SEMANTICS", "PASS")

    new_home = disposable_home / "new-db"
    set_home(new_home)
    executions = importlib.import_module("cron.executions")
    executions._emit_execution_state = lambda *args, **kwargs: None

    scheduled = "2026-10-01T12:00:00+00:00"
    success = executions.create_execution("success", source="builtin", scheduled_at=scheduled)
    executions.mark_execution_running(success["id"])
    success_done = executions.finish_execution(
        success["id"],
        success=True,
        delivery_outcome="delivered",
    )
    require(success_done is not None, "success terminal row missing")
    require(success_done["error_class"] is None, "successful execution fabricated error_class")
    require(success_done["delivery_outcome"] == "delivered", "P6-04 delivery outcome regressed")
    require(success_done["scheduled_at"] == scheduled, "P6-04 scheduled_at regressed")
    emit("P6_04A_FIXTURE_SUCCESS_NULL_CLASS", "PASS")

    for raw, expected in EXPECTED_CLASSES.items():
        created = executions.create_execution(
            f"fail-{expected}-{len(raw)}",
            source="builtin",
            scheduled_at=scheduled,
        )
        executions.mark_execution_running(created["id"])
        failed = executions.finish_execution(
            created["id"],
            success=False,
            error=raw,
            delivery_outcome="failed",
        )
        require(failed is not None, f"failed terminal row missing for {raw!r}")
        require(failed["error"] == raw, f"raw error changed for {raw!r}")
        require(failed["error_class"] == expected, f"durable class mismatch for {raw!r}")
        require(failed["delivery_outcome"] == "failed", "delivery outcome regressed on failure")
    emit("P6_04A_FIXTURE_FAILED_ROWS_CLASSIFIED", "PASS")

    immutable = executions.create_execution("immutable", source="builtin", scheduled_at=scheduled)
    executions.mark_execution_running(immutable["id"])
    first = executions.finish_execution(
        immutable["id"],
        success=False,
        error="request timed out",
        delivery_outcome="failed",
    )
    require(first is not None and first["error_class"] == "timeout", "first terminal write failed")
    second = executions.finish_execution(
        immutable["id"],
        success=False,
        error="401 unauthorized",
        delivery_outcome="failed",
    )
    require(second is None, "terminal immutability regressed")
    stored = row_for(new_home / "cron" / "executions.db", immutable["id"])
    require(stored["error_class"] == "timeout", "terminal error_class was rewritten")
    emit("P6_04A_FIXTURE_TERMINAL_IMMUTABILITY", "PASS")

    interrupted = executions.create_execution(
        "interrupted",
        source="builtin",
        scheduled_at=scheduled,
    )
    db_path = new_home / "cron" / "executions.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE executions SET process_id=?, pid=?, process_started_at=? WHERE id=?",
            ("dead-owner", 99999999, None, interrupted["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    recovered = executions.recover_interrupted_executions()
    require(recovered >= 1, "interrupted execution was not recovered")
    recovered_row = row_for(db_path, interrupted["id"])
    require(recovered_row["status"] == "unknown", "recovered row status mismatch")
    require(recovered_row["error_class"] == "interrupted", "recovered row lacks interrupted classification")
    require(recovered_row["delivery_outcome"] is None, "recovery fabricated delivery outcome")
    emit("P6_04A_FIXTURE_INTERRUPTED_CLASSIFIED", "PASS")

    migrated_home = disposable_home / "p6-04-schema"
    set_home(migrated_home)
    migrated_db = migrated_home / "cron" / "executions.db"
    migrated_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(migrated_db)
    try:
        conn.execute(p604_schema_sql())
        conn.execute(
            """INSERT INTO executions
               (id, job_id, source, process_id, pid, process_started_at, status,
                claimed_at, started_at, finished_at, error, scheduled_at, delivery_outcome)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-failure",
                "legacy-job",
                "builtin",
                "legacy-process",
                1,
                None,
                "failed",
                "2026-10-01T00:00:00+00:00",
                "2026-10-01T00:00:01+00:00",
                "2026-10-01T00:00:02+00:00",
                "request timed out",
                "2026-10-01T00:00:00+00:00",
                "failed",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    migrated = executions.list_executions(job_id="legacy-job", limit=10)
    require(len(migrated) == 1, "legacy P6-04 row missing after migration")
    require(migrated[0]["error_class"] is None, "migration fabricated classification for historical row")
    cols = table_columns(migrated_db)
    require(cols[-1] == "error_class", f"unexpected migrated column order: {cols}")
    emit("P6_04A_FIXTURE_P604_SCHEMA_MIGRATION", "PASS")

    health_spec = importlib.util.spec_from_file_location("p604a_cron_health", health_path)
    require(health_spec is not None and health_spec.loader is not None, "cron_health spec unavailable")
    # Do not execute cron_health here; source-level shared-import assertion above avoids
    # pulling the scheduler/runtime graph into this isolated classifier qualification.

    require(not external_attempts, f"external network attempts observed: {external_attempts}")
    emit("P6_04A_EXTERNAL_NETWORK_ATTEMPTS", 0)
    emit("P6_04A_SCHEDULER_STARTED", False)
    emit("P6_04A_SCHEDULER_TICK_INVOKED", False)
    emit("P6_04A_JOB_RUN_INVOKED", False)
    emit("P6_04A_PROVIDER_CALL_INVOKED", False)
    emit("P6_04A_COMPANION_MUTATION", False)
    emit("P6_04A_DISPOSABLE_ERROR_CLASSIFICATION_QUALIFICATION", "PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
