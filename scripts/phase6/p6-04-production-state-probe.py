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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--companion-home", required=True)
    args = parser.parse_args()

    home = Path(args.companion_home).resolve()
    cron = home / "cron"
    jobs = cron / "jobs.json"
    db = cron / "executions.db"

    job_count = 0
    if jobs.exists():
        data = json.loads(jobs.read_text(encoding="utf-8-sig"))
        if isinstance(data, list):
            job_count = len(data)
        elif isinstance(data, dict) and isinstance(data.get("jobs"), list):
            job_count = len(data["jobs"])
        else:
            raise RuntimeError("COMPANION jobs.json is not canonical")

    emit("P6_04_PROD_STATE_JOB_COUNT", job_count)
    emit("P6_04_PROD_STATE_EXECUTIONS_DB_PRESENT", db.exists())

    if not db.exists():
        emit("P6_04_PROD_STATE_EXECUTION_COLUMNS", "")
        emit("P6_04_PROD_STATE_EXECUTION_ROWS", 0)
        emit("P6_04_PROD_STATE_SQLITE_MODE", "not_present")
        return 0

    uri = f"file:{db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        columns = [
            str(row[1])
            for row in conn.execute("PRAGMA table_info(executions)").fetchall()
        ]
        count = int(conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0])
    finally:
        conn.close()

    emit("P6_04_PROD_STATE_EXECUTION_COLUMNS", ",".join(columns))
    emit("P6_04_PROD_STATE_EXECUTION_ROWS", count)
    emit("P6_04_PROD_STATE_SQLITE_MODE", "read_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
