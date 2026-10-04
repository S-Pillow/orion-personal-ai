#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3


def emit(key: str, value: object) -> None:
    if isinstance(value, bool):
        value = "true" if value else "false"
    print(f"{key}={value}", flush=True)


def _job_count(home: Path) -> int:
    jobs = home / "cron" / "jobs.json"
    if not jobs.exists():
        return 0
    data = json.loads(jobs.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return len(data["jobs"])
    raise RuntimeError("jobs.json is not canonical")


def cron_guard(home: Path) -> int:
    db = home / "cron" / "executions.db"
    emit("P6_UPG_04_CRON_JOB_COUNT", _job_count(home))
    emit("P6_UPG_04_EXECUTIONS_DB_PRESENT", db.exists())
    if not db.exists():
        emit("P6_UPG_04_EXECUTION_ROW_COUNT", 0)
        emit("P6_UPG_04_ACTIVE_EXECUTION_COUNT", 0)
        emit("P6_UPG_04_EXECUTION_COLUMNS", "")
        emit("P6_UPG_04_CRON_GUARD", "PASS")
        return 0

    uri = f"file:{db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        columns = [
            str(row[1])
            for row in conn.execute("PRAGMA table_info(executions)").fetchall()
        ]
        total = int(conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0])
        active_terms = ["status IN ('claimed','running')"]
        if "handoff_pending" in columns:
            active_terms.append("COALESCE(handoff_pending,0) <> 0")
        active = int(
            conn.execute(
                "SELECT COUNT(*) FROM executions WHERE " + " OR ".join(active_terms)
            ).fetchone()[0]
        )
    finally:
        conn.close()

    emit("P6_UPG_04_EXECUTION_ROW_COUNT", total)
    emit("P6_UPG_04_ACTIVE_EXECUTION_COUNT", active)
    emit("P6_UPG_04_EXECUTION_COLUMNS", ",".join(columns))
    emit("P6_UPG_04_CRON_GUARD", "PASS" if active == 0 else "STOP_ACTIVE_EXECUTION")
    return 0 if active == 0 else 2


def sqlite_integrity(path: Path) -> int:
    path = path.resolve()
    emit("P6_UPG_04_SQLITE_PATH_NAME", path.name)
    emit("P6_UPG_04_SQLITE_PRESENT", path.exists())
    if not path.exists():
        emit("P6_UPG_04_SQLITE_INTEGRITY", "NOT_PRESENT")
        return 0

    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            rows = [str(row[0]) for row in conn.execute("PRAGMA integrity_check")]
        finally:
            conn.close()
    except Exception as exc:
        emit("P6_UPG_04_SQLITE_INTEGRITY", "FAIL")
        emit("P6_UPG_04_SQLITE_ERROR_TYPE", type(exc).__name__)
        return 2

    ok = rows == ["ok"]
    emit("P6_UPG_04_SQLITE_INTEGRITY", "PASS" if ok else "FAIL")
    emit("P6_UPG_04_SQLITE_INTEGRITY_ROW_COUNT", len(rows))
    return 0 if ok else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("cron", "sqlite-integrity"))
    parser.add_argument("--home")
    parser.add_argument("--db")
    args = parser.parse_args()

    if args.mode == "cron":
        if not args.home:
            parser.error("--home is required for cron mode")
        return cron_guard(Path(args.home).resolve())

    if not args.db:
        parser.error("--db is required for sqlite-integrity mode")
    return sqlite_integrity(Path(args.db))


if __name__ == "__main__":
    raise SystemExit(main())
