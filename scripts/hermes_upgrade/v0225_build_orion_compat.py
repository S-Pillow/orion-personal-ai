#!/usr/bin/env python3
"""Build Orion's surviving Hermes v0.22.5 compatibility delta in a disposable checkout.

Fail-closed against the exact Hermes v0.22.5 release commit. Ports only:
- P6-03 exact jobs.json pre-repair byte preservation.
- P6-04A durable error_class persistence.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

EXPECTED_HERMES_COMMIT = "bf0203a794a07aac3ff764972ab9087baa4e4f4e"
EXPECTED_BASE_BLOBS = {
    "cron/jobs.py": "7fed57ffba88eaa65a5272168b5b51e89be6e778",
    "cron/executions.py": "a3dfc01f0dcb8c31d65dc8e12d38786677be8fdb",
    "agent/monitoring/cron_health.py": "1b43bdb0d2c619b431572f0f91eff32116eba21a",
}
EXPECTED_CHANGED = {
    "agent/monitoring/cron_health.py",
    "cron/error_classification.py",
    "cron/executions.py",
    "cron/jobs.py",
}

P603_MARKER = "ORION-HERMES-V0225-P6-03-EXACT-REPAIR-PRESERVATION-v1"
P604A_MARKER = "ORION-HERMES-V0225-P6-04A-DURABLE-ERROR-CLASS-v1"

ERROR_CLASSIFICATION_MODULE = f'''"""Shared deterministic cron execution error classification.

{P604A_MARKER}
"""

from __future__ import annotations

import re
from typing import Any, Callable

_AUTH_RE = re.compile(
    r"\\b(?:authentication|authenticated|authenticate|authorization|authorized|authorize|unauthorized|forbidden|bearer|401|403)\\b"
    r"|\\b(?:access|api|refresh) token\\b"
)


def _contains_any(*needles: str) -> Callable[[str], bool]:
    return lambda text: any(needle in text for needle in needles)


_CRON_ERROR_RULES: tuple[tuple[Callable[[str], bool], str], ...] = (
    (lambda s: _AUTH_RE.search(s) is not None, "auth_failed"),
    (_contains_any("rate limit", "429", "quota"), "rate_limited"),
    (_contains_any("timeout", "timed out"), "timeout"),
    (_contains_any("network", "connection", "dns", "socket", "unreachable"), "network_error"),
    (_contains_any("dispatch", "executor"), "dispatch_failed"),
    (_contains_any("interrupt", "owner exited", "restarted"), "interrupted"),
    (_contains_any("empty response"), "empty_response"),
    (_contains_any("config", "missing", "invalid"), "invalid_config"),
)


def classify_cron_error(raw: Any) -> str:
    text = str(raw or "").lower()
    return next((label for match, label in _CRON_ERROR_RULES if match(text)), "unknown")


__all__ = ["classify_cron_error"]
'''


def _run(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def _assert_base(root: Path) -> None:
    head = _run(root, "rev-parse", "HEAD")
    if head != EXPECTED_HERMES_COMMIT:
        raise RuntimeError(
            f"Hermes source identity mismatch: expected {EXPECTED_HERMES_COMMIT}, observed {head}"
        )
    if _run(root, "status", "--porcelain=v1"):
        raise RuntimeError("candidate source must be clean before transformation")
    for rel, expected in EXPECTED_BASE_BLOBS.items():
        observed = _run(root, "rev-parse", f"HEAD:{rel}")
        if observed != expected:
            raise RuntimeError(
                f"base blob mismatch for {rel}: expected {expected}, observed {observed}"
            )
    if (root / "cron" / "error_classification.py").exists():
        raise RuntimeError("unexpected pre-existing cron/error_classification.py")


def _patch_jobs(root: Path) -> None:
    path = root / "cron" / "jobs.py"
    text = path.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        "from dataclasses import dataclass, field\nimport json\n",
        "from dataclasses import dataclass, field\nimport hashlib\nimport json\n",
        "jobs hashlib import",
    )
    text = _replace_once(
        text,
        "import threading\nimport time\nimport os\n",
        "import threading\nimport time\nimport os\nimport tempfile\n",
        "jobs tempfile import",
    )

    old_parse = '''def _parse_jobs_file(jobs_file: Path) -> tuple[Any, bool]:
    """Tolerant jobs.json parse -> ``(data, used_strict_fallback)``: utf-8-sig absorbs a BOM, strict
    failure retries with ``strict=False``. IO/fallback errors propagate (caller decides repair vs
    bail)."""
    with open(jobs_file, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        return json.loads(raw, strict=False), True
'''
    new_parse = f'''# {P603_MARKER}
def _parse_jobs_bytes(raw: bytes) -> tuple[Any, bool]:
    """Tolerantly parse exact jobs.json bytes without losing the repair pre-image."""
    text = raw.decode("utf-8-sig")
    try:
        return json.loads(text), False
    except json.JSONDecodeError:
        return json.loads(text, strict=False), True


def _parse_jobs_file(jobs_file: Path) -> tuple[Any, bool]:
    """Repair-free file parser used by callers that do not need exact pre-image bytes."""
    return _parse_jobs_bytes(jobs_file.read_bytes())


def _preserve_jobs_bytes_before_repair(
    jobs_file: Path, original_bytes: bytes, reason: str,
) -> Path:
    """Durably preserve the exact bytes that triggered an automatic repair rewrite."""
    recovery_dir = jobs_file.parent / "recovery"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    safe_reason = re.sub(r"[^a-z0-9_-]+", "-", str(reason).strip().lower()).strip("-")
    if not safe_reason:
        safe_reason = "unspecified-repair"
    source_hash = hashlib.sha256(original_bytes).hexdigest()
    final_path = recovery_dir / (
        f"jobs.json.{{time.time_ns()}}.{{os.getpid()}}.{{safe_reason}}."
        f"{{source_hash}}.{{uuid.uuid4().hex}}.original"
    )
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{{final_path.name}}.", suffix=".tmp", dir=str(recovery_dir)
    )
    try:
        with os.fdopen(fd, "wb") as dst:
            dst.write(original_bytes)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(temp_name, final_path)
        fsync_directory(recovery_dir)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return final_path
'''
    text = _replace_once(text, old_parse, new_parse, "jobs parse/preservation block")
    text = _replace_once(
        text,
        "        data, _strict_retry = _parse_jobs_file(jobs_file)\n",
        "        raw_bytes = jobs_file.read_bytes()\n"
        "        data, _strict_retry = _parse_jobs_bytes(raw_bytes)\n",
        "jobs load exact bytes",
    )
    text = _replace_once(
        text,
        '''        try:
            save_jobs(jobs, replace=unmergeable and _peek_jobs_unlocked() is None)
            logger.warning("Auto-repaired jobs.json (%s)", repair)
''',
        '''        try:
            _preserve_jobs_bytes_before_repair(jobs_file, raw_bytes, repair)
            save_jobs(jobs, replace=unmergeable and _peek_jobs_unlocked() is None)
            logger.warning("Auto-repaired jobs.json (%s)", repair)
''',
        "jobs preserve-before-repair write",
    )
    compile(text, str(path), "exec")
    path.write_text(text, encoding="utf-8", newline="\n")


def _patch_error_classification(root: Path) -> None:
    module_path = root / "cron" / "error_classification.py"
    module_path.write_text(ERROR_CLASSIFICATION_MODULE, encoding="utf-8", newline="\n")
    compile(ERROR_CLASSIFICATION_MODULE, str(module_path), "exec")

    health_path = root / "agent" / "monitoring" / "cron_health.py"
    text = health_path.read_text(encoding="utf-8")
    text = _replace_once(text, "import logging\nimport re\n", "import logging\n", "cron health re import")
    text = _replace_once(
        text,
        "from agent.monitoring.gateway_health import GatewayMetric, _contains_any, _safe_instance_id\n",
        "from agent.monitoring.gateway_health import GatewayMetric, _safe_instance_id\n"
        "from cron.error_classification import classify_cron_error\n",
        "cron health classifier import",
    )
    start = text.find("_AUTH_RE = re.compile(")
    end = text.find("\ndef _parse_time(", start)
    if start < 0 or end < 0:
        raise RuntimeError("cron health classifier block anchors not found")
    text = text[:start] + text[end + 1 :]
    compile(text, str(health_path), "exec")
    health_path.write_text(text, encoding="utf-8", newline="\n")


def _patch_executions(root: Path) -> None:
    path = root / "cron" / "executions.py"
    text = path.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        "from typing import Any, Dict, Iterator, List, Optional\n\nfrom hermes_constants import get_hermes_home\n",
        "from typing import Any, Dict, Iterator, List, Optional\n\n"
        "from cron.error_classification import classify_cron_error\n"
        "from hermes_constants import get_hermes_home\n",
        "executions classifier import",
    )
    text = _replace_once(
        text,
        '    add_column_if_missing(conn, "executions", "progress_at", "progress_at TEXT")\n',
        '    add_column_if_missing(conn, "executions", "progress_at", "progress_at TEXT")\n'
        f'    # {P604A_MARKER}\n'
        '    add_column_if_missing(conn, "executions", "error_class", "error_class TEXT")\n',
        "executions error_class schema",
    )

    old_finish = '''    now = _hermes_now().isoformat()
    status = "completed" if success else "failed"
    detail = None if success else (str(error) if error else "unknown failure")
    with _transaction() as conn:
        owner = (_PROCESS_ID, os.getpid())
        cur = conn.execute(
            """UPDATE executions
               SET status=?, finished_at=?, error=?, handoff_pending=0,
                   handoff_started_at=NULL, delivery_outcome=?
               WHERE id=? AND status IN ('claimed','running')
                 AND process_id=? AND pid=?""",
            (status, now, detail, delivery_outcome, execution_id, *owner),
        )
'''
    new_finish = '''    now = _hermes_now().isoformat()
    status = "completed" if success else "failed"
    detail = None if success else (str(error) if error else "unknown failure")
    error_class = None if success else classify_cron_error(detail)
    with _transaction() as conn:
        owner = (_PROCESS_ID, os.getpid())
        cur = conn.execute(
            """UPDATE executions
               SET status=?, finished_at=?, error=?, handoff_pending=0,
                   handoff_started_at=NULL, delivery_outcome=?, error_class=?
               WHERE id=? AND status IN ('claimed','running')
                 AND process_id=? AND pid=?""",
            (status, now, detail, delivery_outcome, error_class, execution_id, *owner),
        )
'''
    text = _replace_once(text, old_finish, new_finish, "finish_execution error_class")

    old_receipt = '''    now = _hermes_now().isoformat()
    with _transaction() as conn:
        row = _recoverable_row(conn, execution_id, job_id)
        if row is None or _row_owner_live(row):
            return None
        conn.execute(
            """UPDATE executions SET status=?, finished_at=?, error=?, handoff_pending=0,
               handoff_started_at=NULL, delivery_outcome=? WHERE id=?""",
            ('completed' if success else 'failed', now, None if success else (str(error) if error else 'unknown failure'),
             delivery_outcome, execution_id))
'''
    new_receipt = '''    now = _hermes_now().isoformat()
    detail = None if success else (str(error) if error else "unknown failure")
    error_class = None if success else classify_cron_error(detail)
    with _transaction() as conn:
        row = _recoverable_row(conn, execution_id, job_id)
        if row is None or _row_owner_live(row):
            return None
        conn.execute(
            """UPDATE executions SET status=?, finished_at=?, error=?, handoff_pending=0,
               handoff_started_at=NULL, delivery_outcome=?, error_class=? WHERE id=?""",
            ('completed' if success else 'failed', now, detail,
             delivery_outcome, error_class, execution_id))
'''
    text = _replace_once(text, old_receipt, new_receipt, "recover_receipted_execution error_class")

    text = _replace_once(
        text,
        '''                """UPDATE executions
                   SET status='unknown', finished_at=?, error=?,
                       handoff_pending=0, handoff_started_at=NULL
                   WHERE id=? AND status=? AND process_id=? AND pid=?
                     AND handoff_pending=?
                     AND handoff_started_at IS ?
                     AND claimed_at=? AND progress_at IS ?""",
                (now, reason, row["id"], row["status"], row["process_id"], row["pid"],
''',
        '''                """UPDATE executions
                   SET status='unknown', finished_at=?, error=?, error_class=?,
                       handoff_pending=0, handoff_started_at=NULL
                   WHERE id=? AND status=? AND process_id=? AND pid=?
                     AND handoff_pending=?
                     AND handoff_started_at IS ?
                     AND claimed_at=? AND progress_at IS ?""",
                (now, reason, classify_cron_error(reason),
                 row["id"], row["status"], row["process_id"], row["pid"],
''',
        "recover_interrupted_executions error_class",
    )
    text = _replace_once(
        text,
        '''            """UPDATE executions
               SET status='unknown', finished_at=?, error=?,
                   handoff_pending=0, handoff_started_at=NULL
               WHERE id=? AND status=? AND process_id=? AND pid=?""",
            (now, reason, row["id"], row["status"], row["process_id"], row["pid"]),
''',
        '''            """UPDATE executions
               SET status='unknown', finished_at=?, error=?, error_class=?,
                   handoff_pending=0, handoff_started_at=NULL
               WHERE id=? AND status=? AND process_id=? AND pid=?""",
            (now, reason, classify_cron_error(reason),
             row["id"], row["status"], row["process_id"], row["pid"]),
''',
        "terminalize_dead_owner error_class",
    )
    text = _replace_once(
        text,
        '''            """UPDATE executions SET status='unknown', finished_at=?, error=?,
                   handoff_pending=0, handoff_started_at=NULL
               WHERE id=? AND status IN ('claimed','running') AND process_id=? AND pid=?""",
            (now, reason, str(execution_id), _PROCESS_ID, os.getpid()))
''',
        '''            """UPDATE executions SET status='unknown', finished_at=?, error=?, error_class=?,
                   handoff_pending=0, handoff_started_at=NULL
               WHERE id=? AND status IN ('claimed','running') AND process_id=? AND pid=?""",
            (now, reason, classify_cron_error(reason),
             str(execution_id), _PROCESS_ID, os.getpid()))
''',
        "give_up_execution error_class",
    )
    compile(text, str(path), "exec")
    path.write_text(text, encoding="utf-8", newline="\n")


def _verify(root: Path) -> None:
    status_lines = [line for line in _run(root, "status", "--porcelain=v1").splitlines() if line]
    names = {line[3:] for line in status_lines}
    if names != EXPECTED_CHANGED:
        raise RuntimeError(
            f"changed path scope mismatch: expected {sorted(EXPECTED_CHANGED)}, observed {sorted(names)}"
        )

    jobs = (root / "cron" / "jobs.py").read_text(encoding="utf-8")
    executions = (root / "cron" / "executions.py").read_text(encoding="utf-8")
    health = (root / "agent" / "monitoring" / "cron_health.py").read_text(encoding="utf-8")
    classifier = (root / "cron" / "error_classification.py").read_text(encoding="utf-8")
    for marker in (
        P603_MARKER,
        "_preserve_jobs_bytes_before_repair(jobs_file, raw_bytes, repair)",
        "raw_bytes = jobs_file.read_bytes()",
        "source_hash = hashlib.sha256(original_bytes).hexdigest()",
    ):
        if marker not in jobs:
            raise RuntimeError(f"jobs verification missing: {marker}")
    for marker in (
        P604A_MARKER,
        'add_column_if_missing(conn, "executions", "error_class", "error_class TEXT")',
        "error_class = None if success else classify_cron_error(detail)",
        "classify_cron_error(reason)",
    ):
        if marker not in executions:
            raise RuntimeError(f"executions verification missing: {marker}")
    if "from cron.error_classification import classify_cron_error" not in health:
        raise RuntimeError("cron health is not re-exporting the shared classifier")
    if P604A_MARKER not in classifier:
        raise RuntimeError("shared classifier marker missing")

    for func in (
        "finish_execution",
        "recover_receipted_execution",
        "recover_interrupted_executions",
        "terminalize_dead_owner",
        "give_up_execution",
    ):
        start = executions.find(f"def {func}(")
        if start < 0:
            raise RuntimeError(f"missing terminal writer: {func}")
        next_def = executions.find("\ndef ", start + 5)
        block = executions[start : next_def if next_def >= 0 else len(executions)]
        if "error_class" not in block:
            raise RuntimeError(f"{func} does not persist error_class")

    _run(root, "diff", "--check")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    args = parser.parse_args()
    root = Path(args.source_root).resolve()

    _assert_base(root)
    _patch_jobs(root)
    _patch_error_classification(root)
    _patch_executions(root)
    _verify(root)

    print("HERMES_V0225_ORION_COMPAT_TRANSFORM=PASS")
    print(f"HERMES_BASE_COMMIT={EXPECTED_HERMES_COMMIT}")
    print("PORT_P603_EXACT_REPAIR_PRESERVATION=PASS")
    print("PORT_P604A_DURABLE_ERROR_CLASS=PASS")
    print("RETIRED_P4_AUDIO_PATCH=true")
    print("RETIRED_P5_APPROVAL_PATCH=true")
    print("RETIRED_P604_OLD_LEDGER_PATCH=true")
    print("CHANGED_PATHS=" + ",".join(sorted(EXPECTED_CHANGED)))
    for rel in sorted(EXPECTED_CHANGED):
        data = (root / rel).read_bytes()
        print(f"POST_SHA256_{rel.replace('/', '_')}={hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
