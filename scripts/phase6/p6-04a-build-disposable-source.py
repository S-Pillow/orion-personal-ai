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
    classifier_path = source_root / "cron" / "error_classification.py"
    health_path = source_root / "agent" / "monitoring" / "cron_health.py"

    require(executions_path.is_file(), f"missing {executions_path}")
    require(health_path.is_file(), f"missing {health_path}")
    require(not classifier_path.exists(), f"unexpected pre-existing {classifier_path}")

    executions = executions_path.read_text(encoding="utf-8")
    health = health_path.read_text(encoding="utf-8")

    classifier = '''"""Shared deterministic cron execution error classification."""

from __future__ import annotations

import re
from typing import Any


def classify_cron_error(raw: Any) -> str:
    text = str(raw or "").lower()
    if (
        re.search(r"\\b(?:authentication|authenticated|authenticate|authorization|authorized|authorize|unauthorized|forbidden)\\b", text)
        or re.search(r"\\bbearer\\b", text)
        or re.search(r"\\b(?:access|api|refresh) token\\b", text)
        or re.search(r"\\b(?:401|403)\\b", text)
    ):
        return "auth_failed"
    if "rate limit" in text or "429" in text or "quota" in text:
        return "rate_limited"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if any(value in text for value in ("network", "connection", "dns", "socket", "unreachable")):
        return "network_error"
    if "dispatch" in text or "executor" in text:
        return "dispatch_failed"
    if "interrupt" in text or "owner exited" in text or "restarted" in text:
        return "interrupted"
    if "empty response" in text:
        return "empty_response"
    if any(value in text for value in ("config", "missing", "invalid")):
        return "invalid_config"
    return "unknown"


__all__ = ["classify_cron_error"]
'''

    health = replace_once(
        health,
        "import logging\nimport re\n",
        "import logging\n",
        "remove local regex import",
    )
    health = replace_once(
        health,
        "from cron.jobs import (\n",
        "from cron.error_classification import classify_cron_error\nfrom cron.jobs import (\n",
        "shared classifier import",
    )
    local_classifier = '''def classify_cron_error(raw: Any) -> str:
    text = str(raw or "").lower()
    if (
        re.search(r"\\b(?:authentication|authenticated|authenticate|authorization|authorized|authorize|unauthorized|forbidden)\\b", text)
        or re.search(r"\\bbearer\\b", text)
        or re.search(r"\\b(?:access|api|refresh) token\\b", text)
        or re.search(r"\\b(?:401|403)\\b", text)
    ):
        return "auth_failed"
    if "rate limit" in text or "429" in text or "quota" in text:
        return "rate_limited"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if any(value in text for value in ("network", "connection", "dns", "socket", "unreachable")):
        return "network_error"
    if "dispatch" in text or "executor" in text:
        return "dispatch_failed"
    if "interrupt" in text or "owner exited" in text or "restarted" in text:
        return "interrupted"
    if "empty response" in text:
        return "empty_response"
    if any(value in text for value in ("config", "missing", "invalid")):
        return "invalid_config"
    return "unknown"


'''
    health = replace_once(
        health,
        local_classifier,
        "",
        "remove duplicated classifier implementation",
    )

    executions = replace_once(
        executions,
        "from hermes_constants import get_hermes_home\n",
        "from cron.error_classification import classify_cron_error\nfrom hermes_constants import get_hermes_home\n",
        "classifier import into durable ledger",
    )
    executions = replace_once(
        executions,
        '''             error TEXT,
             scheduled_at TEXT,
             delivery_outcome TEXT
           )"""
    )
''',
        '''             error TEXT,
             scheduled_at TEXT,
             delivery_outcome TEXT,
             error_class TEXT
           )"""
    )
''',
        "base schema error_class",
    )
    executions = replace_once(
        executions,
        '''    if "delivery_outcome" not in existing_columns:
        conn.execute("ALTER TABLE executions ADD COLUMN delivery_outcome TEXT")
    conn.execute(
''',
        '''    if "delivery_outcome" not in existing_columns:
        conn.execute("ALTER TABLE executions ADD COLUMN delivery_outcome TEXT")
    if "error_class" not in existing_columns:
        conn.execute("ALTER TABLE executions ADD COLUMN error_class TEXT")
    conn.execute(
''',
        "error_class migration",
    )
    executions = replace_once(
        executions,
        '''    detail = None if success else (str(error) if error else "unknown failure")
    with _transaction() as conn:
        cur = conn.execute(
            """UPDATE executions SET status=?, finished_at=?, error=?, delivery_outcome=?
               WHERE id=? AND status IN ('claimed','running')""",
            (status, now, detail,
             str(delivery_outcome) if delivery_outcome is not None else None,
             execution_id),
        )
''',
        '''    detail = None if success else (str(error) if error else "unknown failure")
    error_class = None if success else classify_cron_error(detail)
    with _transaction() as conn:
        cur = conn.execute(
            """UPDATE executions
               SET status=?, finished_at=?, error=?, delivery_outcome=?, error_class=?
               WHERE id=? AND status IN ('claimed','running')""",
            (status, now, detail,
             str(delivery_outcome) if delivery_outcome is not None else None,
             error_class, execution_id),
        )
''',
        "finish_execution durable error classification",
    )
    executions = replace_once(
        executions,
        '''            cur = conn.execute(
                """UPDATE executions SET status='unknown', finished_at=?, error=?
                   WHERE id=? AND status IN ('claimed','running')""",
                (now,
                 "Scheduler restarted after this execution's owner exited before a durable "
                 "terminal state; whether side effects ran is unknown.",
                 row["id"]),
            )
''',
        '''            detail = (
                "Scheduler restarted after this execution's owner exited before a durable "
                "terminal state; whether side effects ran is unknown."
            )
            cur = conn.execute(
                """UPDATE executions
                   SET status='unknown', finished_at=?, error=?, error_class=?
                   WHERE id=? AND status IN ('claimed','running')""",
                (now, detail, classify_cron_error(detail), row["id"]),
            )
''',
        "recovery durable error classification",
    )

    classifier_path.write_text(classifier, encoding="utf-8", newline="\n")
    executions_path.write_text(executions, encoding="utf-8", newline="\n")
    health_path.write_text(health, encoding="utf-8", newline="\n")

    print(
        "P6_04A_SOURCE_TRANSFORM_CHANGED="
        "agent/monitoring/cron_health.py,cron/error_classification.py,cron/executions.py",
        flush=True,
    )
    print("P6_04A_SOURCE_TRANSFORM=PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
