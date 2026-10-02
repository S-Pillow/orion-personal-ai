from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch


UPSTREAM_SEED_JOB_ID = "p6-upg-02-upstream-seed"
UPSTREAM_SEED_INSTANT = "2026-10-02T12:00:00+00:00"


def recovery_artifacts(home: Path) -> list[Path]:
    recovery = home / "cron" / "recovery"
    if not recovery.exists():
        return []
    return sorted(recovery.glob("jobs.*.original"))


def sqlite_columns(db: Path) -> list[str]:
    with sqlite3.connect(db) as conn:
        return [
            str(row[1])
            for row in conn.execute("PRAGMA table_info(executions)").fetchall()
        ]


def seed_upstream(home: Path, db: Path) -> int:
    os.environ["HERMES_HOME"] = str(home)
    home.mkdir(parents=True, exist_ok=True)
    db.parent.mkdir(parents=True, exist_ok=True)

    from cron import executions as E

    E.EXECUTIONS_FILE = db
    row = E.create_execution(
        UPSTREAM_SEED_JOB_ID,
        source="builtin",
        scheduled_instant=UPSTREAM_SEED_INSTANT,
    )
    if E.mark_execution_running(row["id"]) is None:
        raise AssertionError("upstream seed could not enter running state")
    finished = E.finish_execution(
        row["id"],
        success=True,
        delivery_outcome="not_configured",
    )
    if finished is None:
        raise AssertionError("upstream seed could not finish")

    columns = sqlite_columns(db)
    if "error_class" in columns:
        raise AssertionError(
            "unmodified v0.21.5 unexpectedly already contains error_class"
        )

    print("P6_UPG_02_UPSTREAM_NATIVE_DB_SEEDED=PASS")
    print("P6_UPG_02_UPSTREAM_NATIVE_COLUMNS=" + ",".join(columns))
    return 0


def syntax_check(candidate_root: Path) -> int:
    paths = [
        candidate_root / "cron" / "jobs.py",
        candidate_root / "cron" / "error_classification.py",
        candidate_root / "cron" / "executions.py",
        candidate_root / "agent" / "monitoring" / "cron_health.py",
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")
    print("P6_UPG_02_TRANSFORMED_SYNTAX=PASS")
    return 0


def qualify(home: Path, upstream_db: Path) -> int:
    os.environ["HERMES_HOME"] = str(home)
    cron = home / "cron"
    cron.mkdir(parents=True, exist_ok=True)

    # Verify this database is genuinely the upstream-created fixture before
    # importing the transformed ledger and allowing migration to run.
    before_columns = sqlite_columns(upstream_db)
    if "error_class" in before_columns:
        raise AssertionError("upstream fixture was already migrated")
    for required in (
        "handoff_pending",
        "handoff_started_at",
        "delivery_outcome",
        "scheduled_instant",
    ):
        if required not in before_columns:
            raise AssertionError(
                f"upstream-native fixture missing expected column: {required}"
            )

    with sqlite3.connect(upstream_db) as conn:
        seed_before = conn.execute(
            """
            SELECT status, scheduled_instant, delivery_outcome, error
            FROM executions WHERE job_id=?
            """,
            (UPSTREAM_SEED_JOB_ID,),
        ).fetchone()

    if seed_before != (
        "completed",
        UPSTREAM_SEED_INSTANT,
        "not_configured",
        None,
    ):
        raise AssertionError(f"unexpected upstream seed row: {seed_before!r}")

    from cron import executions as E
    from cron import jobs as J
    from cron.error_classification import classify_cron_error
    from agent.monitoring.cron_health import (
        classify_cron_error as telemetry_classifier,
    )

    # One classifier grammar, shared by monitoring and durable execution.
    cases = {
        "authentication failed": "auth_failed",
        "HTTP 429 rate limit": "rate_limited",
        "request timed out": "timeout",
        "network connection unreachable": "network_error",
        "executor dispatch failed": "dispatch_failed",
        "scheduler restarted after owner exited": "interrupted",
        "empty response": "empty_response",
        "invalid config": "invalid_config",
        "different failure": "unknown",
    }
    for raw, expected in cases.items():
        if classify_cron_error(raw) != expected:
            raise AssertionError((raw, classify_cron_error(raw), expected))
        if telemetry_classifier(raw) != expected:
            raise AssertionError((raw, telemetry_classifier(raw), expected))

    print("P6_UPG_02_CLASSIFIER_PARITY=PASS")

    # Real upstream-native DB -> transformed schema.
    E.EXECUTIONS_FILE = upstream_db
    E.list_executions(limit=10)

    after_columns = sqlite_columns(upstream_db)
    if set(after_columns) != set(before_columns) | {"error_class"}:
        raise AssertionError(
            f"unexpected upstream migration columns: {after_columns!r}"
        )
    if after_columns.count("error_class") != 1:
        raise AssertionError("error_class migration is not idempotent/additive")

    with sqlite3.connect(upstream_db) as conn:
        seed_after = conn.execute(
            """
            SELECT status, scheduled_instant, delivery_outcome, error, error_class
            FROM executions WHERE job_id=?
            """,
            (UPSTREAM_SEED_JOB_ID,),
        ).fetchone()

    if seed_after != (
        "completed",
        UPSTREAM_SEED_INSTANT,
        "not_configured",
        None,
        None,
    ):
        raise AssertionError(f"upstream seed changed during migration: {seed_after!r}")

    print("P6_UPG_02_REAL_UPSTREAM_SCHEMA_MIGRATION=PASS")

    # P6-03 exact-byte preservation.
    jobs_file = cron / "jobs.json"
    with J.use_cron_store(home):
        jobs_file.write_bytes(
            b'{"jobs":[{"id":"canonical","prompt":"ok","enabled":true}]}'
        )
        before = list(recovery_artifacts(home))
        loaded = J.load_jobs()
        if loaded[0]["id"] != "canonical":
            raise AssertionError("canonical jobs read changed behavior")
        if recovery_artifacts(home) != before:
            raise AssertionError("canonical read created recovery evidence")

    print("P6_UPG_02_CANONICAL_READ_NO_ARTIFACT=PASS")

    fixtures = [
        (
            "control",
            b'{"jobs":[{"id":"control","prompt":"a'
            + bytes([1])
            + b'b","enabled":true}]}',
        ),
        (
            "bare",
            b'[{"id":"bare","prompt":"ok","enabled":true}]',
        ),
        (
            "map",
            b'{"jobs":{"mapped":{"prompt":"ok","enabled":true}}}',
        ),
    ]

    for label, raw in fixtures:
        with J.use_cron_store(home):
            jobs_file.write_bytes(raw)
            before = set(recovery_artifacts(home))
            loaded = J.load_jobs()
            created = [
                path
                for path in recovery_artifacts(home)
                if path not in before
            ]
            if len(created) != 1:
                raise AssertionError((label, created))
            if created[0].read_bytes() != raw:
                raise AssertionError(f"{label}: retained bytes differ")
            if hashlib.sha256(created[0].read_bytes()).digest() != hashlib.sha256(raw).digest():
                raise AssertionError(f"{label}: retained digest differs")
            if not loaded:
                raise AssertionError(f"{label}: repair returned no jobs")

            # Re-presenting the same malformed source must reuse retained evidence.
            jobs_file.write_bytes(raw)
            count_before = len(recovery_artifacts(home))
            J.load_jobs()
            if len(recovery_artifacts(home)) != count_before:
                raise AssertionError(f"{label}: duplicate evidence accumulated")

    print("P6_UPG_02_EXACT_BYTE_REPAIR_AND_DEDUP=PASS")

    # A preservation failure must stop before repair rewrite.
    with J.use_cron_store(home):
        raw = b'[{"id":"failclosed","prompt":"ok"}]'
        jobs_file.write_bytes(raw)

        with patch.object(
            J,
            "_preserve_jobs_bytes_before_repair",
            side_effect=OSError("synthetic preservation failure"),
        ):
            try:
                J.load_jobs()
            except OSError:
                pass
            else:
                raise AssertionError("repair did not fail closed")

        if jobs_file.read_bytes() != raw:
            raise AssertionError("fail-closed repair changed source bytes")

    print("P6_UPG_02_REPAIR_FAIL_CLOSED=PASS")

    # Directly exercise the bounded evidence cap with distinct evidence.
    with J.use_cron_store(home):
        for index in range(40):
            payload = f"retention-evidence-{index}".encode("utf-8")
            J._preserve_jobs_bytes_before_repair(
                jobs_file,
                payload,
                "retention-test",
            )

    retained = recovery_artifacts(home)
    if len(retained) > 32:
        raise AssertionError(f"recovery retention exceeded cap: {len(retained)}")

    print("P6_UPG_02_RECOVERY_RETENTION_CAP=PASS")

    # Current Orion live schema -> upstream v0.21.5 additive migration.
    current_db = cron / "current-orion.db"
    if current_db.exists():
        current_db.unlink()

    with sqlite3.connect(current_db) as conn:
        conn.execute(
            """
            CREATE TABLE executions (
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
              delivery_outcome TEXT,
              error_class TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO executions
            VALUES (
              'historical','legacy','builtin','old',1,NULL,'failed',
              '2026-10-01T00:00:00+00:00',
              NULL,NULL,'request timed out',
              '2026-10-01T00:00:00+00:00','failed','timeout'
            )
            """
        )

    E.EXECUTIONS_FILE = current_db
    E.list_executions(limit=10)

    current_columns = sqlite_columns(current_db)
    for required in (
        "scheduled_at",
        "delivery_outcome",
        "error_class",
        "handoff_pending",
        "handoff_started_at",
        "scheduled_instant",
    ):
        if required not in current_columns:
            raise AssertionError(
                f"current Orion migration missing column: {required}"
            )

    with sqlite3.connect(current_db) as conn:
        historical = conn.execute(
            """
            SELECT scheduled_at, delivery_outcome, error_class, error
            FROM executions WHERE id='historical'
            """
        ).fetchone()

    if historical != (
        "2026-10-01T00:00:00+00:00",
        "failed",
        "timeout",
        "request timed out",
    ):
        raise AssertionError(
            f"historical Orion evidence changed: {historical!r}"
        )

    print("P6_UPG_02_CURRENT_ORION_SCHEMA_MIGRATION=PASS")

    failed = E.create_execution(
        "failed",
        source="builtin",
        scheduled_instant="2026-10-02T14:00:00+00:00",
    )
    if E.mark_execution_running(failed["id"]) is None:
        raise AssertionError("failed-row fixture did not enter running state")
    failed_done = E.finish_execution(
        failed["id"],
        success=False,
        error="request timed out",
        delivery_outcome="failed",
    )
    if failed_done is None:
        raise AssertionError("failed-row fixture did not finish")
    if failed_done["error_class"] != "timeout":
        raise AssertionError(failed_done)
    if failed_done["scheduled_instant"] != "2026-10-02T14:00:00+00:00":
        raise AssertionError(failed_done)
    if failed_done["scheduled_at"] is not None:
        raise AssertionError("new v0.21.5 row unexpectedly wrote scheduled_at")

    success = E.create_execution("success", source="direct")
    if E.mark_execution_running(success["id"]) is None:
        raise AssertionError("success-row fixture did not enter running state")
    success_done = E.finish_execution(
        success["id"],
        success=True,
        delivery_outcome="not_configured",
    )
    if success_done is None or success_done["error_class"] is not None:
        raise AssertionError(success_done)

    print("P6_UPG_02_TERMINAL_CLASSIFICATION=PASS")

    if E.finish_execution(
        failed["id"],
        success=True,
        delivery_outcome="delivered",
    ) is not None:
        raise AssertionError("terminal row was rewritten")
    if E.get_execution(failed["id"])["error_class"] != "timeout":
        raise AssertionError("terminal classification changed")

    print("P6_UPG_02_TERMINAL_IMMUTABILITY=PASS")

    dead = E.create_execution("dead-owner", source="builtin")
    with sqlite3.connect(current_db) as conn:
        conn.execute(
            """
            UPDATE executions
            SET process_id='dead-owner-process', pid=99999999
            WHERE id=?
            """,
            (dead["id"],),
        )

    with patch.object(E, "_owner_is_live", return_value=False):
        if E.recover_interrupted_executions() < 1:
            raise AssertionError("dead-owner recovery changed no rows")

    dead_after = E.get_execution(dead["id"])
    if dead_after["status"] != "unknown":
        raise AssertionError(dead_after)
    if dead_after["error_class"] != "interrupted":
        raise AssertionError(dead_after)

    wedged = E.create_execution("wedged-owner", source="builtin")
    with sqlite3.connect(current_db) as conn:
        conn.execute(
            """
            UPDATE executions
            SET process_id='other-live-process',
                pid=55555,
                claimed_at=?
            WHERE id=?
            """,
            (
                (E._hermes_now() - timedelta(hours=3)).isoformat(),
                wedged["id"],
            ),
        )

    with patch.object(E, "_owner_is_live", return_value=True), patch.object(
        E,
        "_live_owner_stale_after_seconds",
        return_value=1.0,
    ):
        if E.recover_interrupted_executions() < 1:
            raise AssertionError("wedged-owner recovery changed no rows")

    wedged_after = E.get_execution(wedged["id"])
    if wedged_after["status"] != "unknown":
        raise AssertionError(wedged_after)
    if wedged_after["error_class"] != "interrupted":
        raise AssertionError(wedged_after)

    print("P6_UPG_02_RECOVERY_CLASSIFICATION=PASS")
    print("P6_UPG_02_CUSTOM_QUALIFICATION=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=("seed-upstream", "syntax", "qualify"),
    )
    parser.add_argument("--home")
    parser.add_argument("--upstream-db")
    parser.add_argument("--candidate-root")
    args = parser.parse_args()

    if args.mode == "seed-upstream":
        if not args.home or not args.upstream_db:
            parser.error("seed-upstream requires --home and --upstream-db")
        return seed_upstream(
            Path(args.home).resolve(),
            Path(args.upstream_db).resolve(),
        )

    if args.mode == "syntax":
        if not args.candidate_root:
            parser.error("syntax requires --candidate-root")
        return syntax_check(Path(args.candidate_root).resolve())

    if not args.home or not args.upstream_db:
        parser.error("qualify requires --home and --upstream-db")
    return qualify(
        Path(args.home).resolve(),
        Path(args.upstream_db).resolve(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
