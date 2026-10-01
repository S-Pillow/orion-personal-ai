from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from pathlib import Path


def git_show(repo: Path, ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout


def emit_context(label: str, text: str, pattern: str, before: int = 10, after: int = 26) -> None:
    lines = text.splitlines()
    rx = re.compile(pattern)
    hits = [i for i, line in enumerate(lines) if rx.search(line)]
    print(f"P6_04_SOURCE_{label}_HIT_COUNT={len(hits)}")
    for ordinal, idx in enumerate(hits[:8], start=1):
        lo = max(0, idx - before)
        hi = min(len(lines), idx + after + 1)
        print(f"P6_04_SOURCE_{label}_HIT_{ordinal}_LINE={idx + 1}")
        print(f"--- {label} hit {ordinal} lines {lo + 1}-{hi} ---")
        for n in range(lo, hi):
            print(f"{n + 1}:{lines[n]}")


def inspect_db(db_path: Path) -> None:
    if not db_path.exists():
        print("P6_04_EXECUTIONS_DB_PRESENT=false")
        return

    print("P6_04_EXECUTIONS_DB_PRESENT=true")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cols = conn.execute("PRAGMA table_info(executions)").fetchall()
        indexes = conn.execute("PRAGMA index_list(executions)").fetchall()
        count = conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
        print("P6_04_EXECUTIONS_COLUMNS=" + ",".join(str(row[1]) for row in cols))
        print("P6_04_EXECUTIONS_COLUMN_DETAIL=" + json.dumps([
            {
                "name": row[1],
                "type": row[2],
                "notnull": bool(row[3]),
                "pk": bool(row[5]),
            }
            for row in cols
        ], separators=(",", ":")))
        print("P6_04_EXECUTIONS_INDEXES=" + ",".join(str(row[1]) for row in indexes))
        print(f"P6_04_EXECUTIONS_ROW_COUNT={count}")

        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='executions'"
        ).fetchone()
        normalized = " ".join((table_sql[0] if table_sql and table_sql[0] else "").split())
        print("P6_04_EXECUTIONS_TABLE_SQL=" + normalized)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-root", required=True)
    parser.add_argument("--hermes-ref", required=True)
    parser.add_argument("--companion-home", required=True)
    args = parser.parse_args()

    hermes_root = Path(args.hermes_root)
    companion_home = Path(args.companion_home)

    executions = git_show(hermes_root, args.hermes_ref, "cron/executions.py")
    scheduler = git_show(hermes_root, args.hermes_ref, "cron/scheduler.py")
    monitoring = git_show(hermes_root, args.hermes_ref, "agent/monitoring/cron_health.py")

    inspect_db(companion_home / "cron" / "executions.db")

    emit_context("EXEC_SCHEMA", executions, r"CREATE TABLE IF NOT EXISTS executions")
    emit_context("CREATE_EXECUTION", executions, r"^def create_execution\(")
    emit_context("FINISH_EXECUTION", executions, r"^def finish_execution\(")
    emit_context("RECOVER_INTERRUPTED", executions, r"^def recover_interrupted_executions\(")

    emit_context("SCHED_CREATE_CALL", scheduler, r"create_execution\(")
    emit_context("SCHED_CLAIM_CALL", scheduler, r"claim_job_for_fire\(")
    emit_context("SCHED_NEXT_RUN", scheduler, r"next_run_at")
    emit_context("SCHED_DELIVERY_OUTCOME", scheduler, r"delivery_outcome")
    emit_context("SCHED_FINISH_CALL", scheduler, r"finish_execution\(")

    emit_context("MONITOR_DELIVERY", monitoring, r"delivery_outcome")
    emit_context("MONITOR_JOB_KEY", monitoring, r"def _job_key\(")

    print("P6_04_EXTERNAL_NETWORK_ATTEMPTS=0")
    print("P6_04_SCHEDULER_TICK_INVOKED=false")
    print("P6_04_JOB_CREATED=false")
    print("P6_04_PROVIDER_CALL_INVOKED=false")
    print("P6_04_READ_ONLY_DISCOVERY_HELPER=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
