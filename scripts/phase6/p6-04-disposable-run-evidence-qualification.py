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


KNOWN_OUTCOMES = (
    "delivered",
    "failed",
    "suppressed",
    "suppressed_acked",
    "not_configured",
)


def emit(key: str, value: object) -> None:
    if isinstance(value, bool):
        value = "true" if value else "false"
    print(f"{key}={value}", flush=True)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def old_schema_sql() -> str:
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
        error TEXT
    )"""


def table_columns(db_path: Path) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        return [str(row[1]) for row in conn.execute("PRAGMA table_info(executions)").fetchall()]
    finally:
        conn.close()


def db_row(db_path: Path, execution_id: str) -> dict[str, object]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM executions WHERE id=?", (execution_id,)
        ).fetchone()
        require(row is not None, f"execution row missing: {execution_id}")
        return dict(row)
    finally:
        conn.close()


def set_home(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.environ["HERMES_HOME"] = str(path)
    os.environ.pop("HERMES_PROFILE", None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--disposable-home", required=True)
    parser.add_argument("--prepatched", action="store_true")
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    disposable_home = Path(args.disposable_home).resolve()
    executions_path = source_root / "cron" / "executions.py"
    scheduler_path = source_root / "cron" / "scheduler.py"

    require(executions_path.is_file(), f"missing {executions_path}")
    require(scheduler_path.is_file(), f"missing {scheduler_path}")

    executions_text = executions_path.read_text(encoding="utf-8")
    scheduler_text = scheduler_path.read_text(encoding="utf-8")

    require(
        "scheduled_at TEXT" in executions_text
        and "delivery_outcome TEXT" in executions_text
        and "ALTER TABLE executions ADD COLUMN scheduled_at TEXT" in executions_text
        and "ALTER TABLE executions ADD COLUMN delivery_outcome TEXT" in executions_text
        and "scheduled_at: Optional[str] = None" in executions_text
        and "delivery_outcome=?" in executions_text,
        "prepatched executions.py is missing P6-04 markers",
    )
    require(
        'scheduled_at=job.get("next_run_at")' in scheduler_text,
        "scheduler.py is missing pre-advance scheduled_at capture",
    )

    compile_dir = disposable_home / "compiled"
    compile_dir.mkdir(parents=True, exist_ok=True)
    py_compile.compile(
        str(executions_path),
        cfile=str(compile_dir / "executions.pyc"),
        doraise=True,
    )
    py_compile.compile(
        str(scheduler_path),
        cfile=str(compile_dir / "scheduler.pyc"),
        doraise=True,
    )
    emit("P6_04_PATCHED_SOURCE_PY_COMPILE", "PASS")

    external_attempts: list[str] = []
    real_connect = socket.socket.connect

    def guarded_connect(sock, address):
        host = str(address[0]) if isinstance(address, tuple) and address else str(address)
        if host not in {"127.0.0.1", "::1", "localhost"}:
            external_attempts.append(repr(address))
            raise RuntimeError(f"P6-04 blocked external network attempt: {address!r}")
        return real_connect(sock, address)

    socket.socket.connect = guarded_connect

    sys.path.insert(0, str(source_root))

    new_home = disposable_home / "new-db"
    set_home(new_home)
    executions = importlib.import_module("cron.executions")

    scheduled = "2026-10-01T05:00:00+00:00"
    captured_events: list[tuple[dict | None, str | None]] = []

    def capture_emit(record, *, delivery_outcome=None):
        captured_events.append((record, delivery_outcome))

    executions._emit_execution_state = capture_emit

    created = executions.create_execution(
        "job-new",
        source="builtin",
        scheduled_at=scheduled,
    )
    require(created["job_id"] == "job-new", "job correlation mismatch")
    require(created["scheduled_at"] == scheduled, "scheduled_at was not persisted")
    require(created["delivery_outcome"] is None, "new claim should not have delivery outcome")
    require(created["status"] == "claimed", "new claim status mismatch")
    execution_id = created["id"]

    cols = table_columns(new_home / "cron" / "executions.db")
    require("scheduled_at" in cols and "delivery_outcome" in cols, "new schema missing additive columns")
    emit("P6_04_FIXTURE_NEW_SCHEMA", "PASS")

    running = executions.mark_execution_running(execution_id)
    require(running is not None and running["status"] == "running", "running transition failed")

    completed = executions.finish_execution(
        execution_id,
        success=True,
        delivery_outcome="delivered",
    )
    require(completed is not None, "terminal completion missing")
    require(completed["status"] == "completed", "terminal status mismatch")
    require(completed["scheduled_at"] == scheduled, "terminal write lost scheduled_at")
    require(completed["delivery_outcome"] == "delivered", "delivery outcome not persisted")
    require(captured_events[-1][1] == "delivered", "monitoring projection did not receive delivery outcome")

    second = executions.finish_execution(
        execution_id,
        success=False,
        error="must not overwrite",
        delivery_outcome="failed",
    )
    require(second is None, "terminal immutability was not preserved")
    terminal = db_row(new_home / "cron" / "executions.db", execution_id)
    require(terminal["status"] == "completed", "terminal row was rewritten")
    require(terminal["delivery_outcome"] == "delivered", "terminal delivery outcome was rewritten")
    emit("P6_04_FIXTURE_TERMINAL_IMMUTABILITY", "PASS")

    for outcome in KNOWN_OUTCOMES:
        row = executions.create_execution(
            f"job-{outcome}",
            source="builtin",
            scheduled_at=scheduled,
        )
        executions.mark_execution_running(row["id"])
        result = executions.finish_execution(
            row["id"],
            success=(outcome != "failed"),
            error=("delivery failed" if outcome == "failed" else None),
            delivery_outcome=outcome,
        )
        require(result is not None, f"finish failed for {outcome}")
        require(result["delivery_outcome"] == outcome, f"outcome mismatch for {outcome}")
    emit("P6_04_FIXTURE_KNOWN_DELIVERY_OUTCOMES", "PASS")

    direct = executions.create_execution("job-direct", source="direct")
    require(direct["scheduled_at"] is None, "direct execution fabricated scheduled_at")
    executions.finish_execution(
        direct["id"],
        success=False,
        error="stopped before delivery truth was known",
    )
    direct_row = db_row(new_home / "cron" / "executions.db", direct["id"])
    require(direct_row["delivery_outcome"] is None, "unknown direct delivery state was fabricated")
    emit("P6_04_FIXTURE_NULL_UNKNOWN_FIELDS", "PASS")

    interrupted = executions.create_execution(
        "job-interrupted",
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

    recovered_count = executions.recover_interrupted_executions()
    require(recovered_count >= 1, "interrupted execution was not recovered")
    interrupted_row = db_row(db_path, interrupted["id"])
    require(interrupted_row["status"] == "unknown", "interrupted row not marked unknown")
    require(interrupted_row["scheduled_at"] == scheduled, "recovery lost scheduled_at")
    require(interrupted_row["delivery_outcome"] is None, "recovery fabricated delivery outcome")
    emit("P6_04_FIXTURE_INTERRUPTED_RECOVERY", "PASS")

    old_home = disposable_home / "old-schema"
    set_home(old_home)
    old_db = old_home / "cron" / "executions.db"
    old_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(old_db)
    try:
        conn.execute(old_schema_sql())
        conn.execute(
            """INSERT INTO executions
               (id, job_id, source, process_id, pid, process_started_at, status,
                claimed_at, started_at, finished_at, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-row",
                "legacy-job",
                "builtin",
                "legacy-process",
                123,
                None,
                "completed",
                "2026-09-01T00:00:00+00:00",
                "2026-09-01T00:00:01+00:00",
                "2026-09-01T00:00:02+00:00",
                None,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    migrated = executions.list_executions(job_id="legacy-job", limit=10)
    require(len(migrated) == 1, "legacy row missing after migration")
    require(migrated[0]["id"] == "legacy-row", "legacy row identity changed")
    require(migrated[0]["scheduled_at"] is None, "legacy scheduled_at should migrate null")
    require(migrated[0]["delivery_outcome"] is None, "legacy delivery_outcome should migrate null")
    migrated_cols = table_columns(old_db)
    require("scheduled_at" in migrated_cols and "delivery_outcome" in migrated_cols, "old schema was not migrated")
    emit("P6_04_FIXTURE_OLD_SCHEMA_MIGRATION", "PASS")

    source_anchor = 'execution = create_execution(\n                    job_id,\n                    source="builtin",\n                    scheduled_at=job.get("next_run_at"),\n                )'
    require(source_anchor in scheduler_text, "built-in scheduler scheduled_at seam drifted")
    due_index = scheduler_text.find("due_jobs = get_due_jobs()")
    advance_index = scheduler_text.find("advance_next_runs([job[\"id\"] for job in due_jobs])")
    create_index = scheduler_text.find(source_anchor)
    claim_index = scheduler_text.find('claimed = claim_job_for_fire(job["id"], return_job=True)')
    require(due_index >= 0 and advance_index > due_index, "due/advance ordering not found")
    require(create_index > advance_index, "execution creation ordering is unexpected")
    require(claim_index > create_index, "claim occurs before execution scheduled_at capture")
    emit("P6_04_FIXTURE_PRE_ADVANCE_SCHEDULED_TIME_SEAM", "PASS")

    latest = executions.latest_execution("legacy-job")
    require(latest is not None and latest["id"] == "legacy-row", "latest_execution additive compatibility failed")
    emit("P6_04_FIXTURE_LIST_LATEST_COMPATIBILITY", "PASS")

    require(not external_attempts, f"external network attempts observed: {external_attempts}")
    emit("P6_04_EXTERNAL_NETWORK_ATTEMPTS", 0)
    emit("P6_04_SCHEDULER_STARTED", False)
    emit("P6_04_SCHEDULER_TICK_INVOKED", False)
    emit("P6_04_JOB_RUN_INVOKED", False)
    emit("P6_04_PROVIDER_CALL_INVOKED", False)
    emit("P6_04_COMPANION_MUTATION", False)
    emit("P6_04_DISPOSABLE_RUN_EVIDENCE_QUALIFICATION", "PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
