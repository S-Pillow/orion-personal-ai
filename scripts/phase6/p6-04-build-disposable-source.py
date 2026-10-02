#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    require(count == 1, f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    executions_path = source_root / "cron" / "executions.py"
    scheduler_path = source_root / "cron" / "scheduler.py"

    require(executions_path.is_file(), f"missing {executions_path}")
    require(scheduler_path.is_file(), f"missing {scheduler_path}")

    executions = executions_path.read_text(encoding="utf-8")
    scheduler = scheduler_path.read_text(encoding="utf-8")

    executions = replace_once(
        executions,
        '''             finished_at TEXT,
             error TEXT
           )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_executions_job_claimed "
''',
        '''             finished_at TEXT,
             error TEXT,
             scheduled_at TEXT,
             delivery_outcome TEXT
           )"""
    )
    existing_columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(executions)").fetchall()
    }
    if "scheduled_at" not in existing_columns:
        conn.execute("ALTER TABLE executions ADD COLUMN scheduled_at TEXT")
    if "delivery_outcome" not in existing_columns:
        conn.execute("ALTER TABLE executions ADD COLUMN delivery_outcome TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_executions_job_claimed "
''',
        "execution schema and migration",
    )

    executions = replace_once(
        executions,
        '''def create_execution(job_id: str, *, source: str) -> Dict[str, Any]:
    """Persist a claimed attempt before executor/provider dispatch."""
''',
        '''def create_execution(
    job_id: str, *, source: str, scheduled_at: Optional[str] = None
) -> Dict[str, Any]:
    """Persist a claimed attempt before executor/provider dispatch."""
''',
        "create_execution signature",
    )

    executions = replace_once(
        executions,
        '''            """INSERT INTO executions
               (id, job_id, source, process_id, pid, process_started_at,
                status, claimed_at)
               VALUES (?, ?, ?, ?, ?, ?, 'claimed', ?)""",
            (execution_id, str(job_id), str(source), _PROCESS_ID, pid,
             _process_start_time(pid), now),
''',
        '''            """INSERT INTO executions
               (id, job_id, source, process_id, pid, process_started_at,
                status, claimed_at, scheduled_at)
               VALUES (?, ?, ?, ?, ?, ?, 'claimed', ?, ?)""",
            (execution_id, str(job_id), str(source), _PROCESS_ID, pid,
             _process_start_time(pid), now,
             str(scheduled_at) if scheduled_at is not None else None),
''',
        "create_execution insert",
    )

    executions = replace_once(
        executions,
        '''        cur = conn.execute(
            """UPDATE executions SET status=?, finished_at=?, error=?
               WHERE id=? AND status IN ('claimed','running')""",
            (status, now, detail, execution_id),
        )
''',
        '''        cur = conn.execute(
            """UPDATE executions SET status=?, finished_at=?, error=?, delivery_outcome=?
               WHERE id=? AND status IN ('claimed','running')""",
            (status, now, detail,
             str(delivery_outcome) if delivery_outcome is not None else None,
             execution_id),
        )
''',
        "finish_execution durable delivery outcome",
    )

    scheduler = replace_once(
        scheduler,
        '''                execution = create_execution(job_id, source="builtin")
                dispatched_job = dict(job, execution_id=execution["id"])
''',
        '''                execution = create_execution(
                    job_id,
                    source="builtin",
                    scheduled_at=job.get("next_run_at"),
                )
                dispatched_job = dict(job, execution_id=execution["id"])
''',
        "builtin scheduled_at capture",
    )

    executions_path.write_text(executions, encoding="utf-8", newline="\n")
    scheduler_path.write_text(scheduler, encoding="utf-8", newline="\n")

    print("P6_04_SOURCE_TRANSFORM_CHANGED=cron/executions.py,cron/scheduler.py", flush=True)
    print("P6_04_SOURCE_TRANSFORM=PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
