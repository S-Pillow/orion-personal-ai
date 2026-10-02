from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path


EXPECTED_CLASSIFIER_BLOCK_SHA256 = (
    "9e153106740ca017fa8140c1b5a82a1cf530056fc157fd28f357b4983047cddc"
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def imported_roots(source: str) -> set[str]:
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", required=True)
    args = parser.parse_args()

    root = Path(args.candidate_root).resolve()

    jobs_path = root / "cron" / "jobs.py"
    executions_path = root / "cron" / "executions.py"
    health_path = root / "agent" / "monitoring" / "cron_health.py"
    classifier_path = root / "cron" / "error_classification.py"

    for path in (jobs_path, executions_path, health_path):
        if not path.is_file():
            raise RuntimeError(f"missing pinned candidate source: {path}")
    if classifier_path.exists():
        raise RuntimeError(
            "cron/error_classification.py unexpectedly exists in pinned candidate"
        )

    jobs = jobs_path.read_text(encoding="utf-8")

    required_imports = {"os", "re", "tempfile", "time", "uuid"}
    missing_imports = required_imports - imported_roots(jobs)
    if missing_imports:
        raise RuntimeError(
            "pinned jobs.py missing expected imports: "
            + ", ".join(sorted(missing_imports))
        )

    jobs = replace_once(
        jobs,
        "import contextlib\nimport copy\n",
        "import contextlib\nimport copy\nimport hashlib\n",
        "jobs hashlib import",
    )

    ticks = chr(96) * 2
    pinned_old_parser = f'''def _parse_jobs_file(jobs_file: Path) -> Tuple[Any, bool]:
    """Tolerant jobs.json parse -> {ticks}(data, used_strict_fallback){ticks}: utf-8-sig absorbs a BOM, strict
    failure retries with {ticks}strict=False{ticks}. IO/fallback errors propagate (caller decides repair vs
    bail)."""
    with open(jobs_file, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        return json.loads(raw, strict=False), True
'''

    new_parser = '''def _parse_jobs_bytes(raw: bytes) -> Tuple[Any, bool]:
    """Tolerantly parse exact jobs.json bytes and report strict-fallback use."""
    text = raw.decode("utf-8-sig")
    try:
        return json.loads(text), False
    except json.JSONDecodeError:
        return json.loads(text, strict=False), True


def _parse_jobs_file(jobs_file: Path) -> Tuple[Any, bool]:
    """Repair-free file parser shared with save-path inspection."""
    return _parse_jobs_bytes(jobs_file.read_bytes())


_MAX_RECOVERY_ARTIFACTS = 32


def _preserve_jobs_bytes_before_repair(
    jobs_file: Path, original_bytes: bytes, reason: str
) -> Path:
    """Preserve exact source bytes before automatic repair; identical bytes dedupe."""
    recovery_dir = jobs_file.parent / "recovery"
    recovery_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(original_bytes).hexdigest()
    short_digest = digest[:24]
    safe_reason = re.sub(
        r"[^a-z0-9_-]+", "-", str(reason).strip().lower()
    ).strip("-")[:32] or "repair"

    existing = sorted(recovery_dir.glob(f"jobs.*.{short_digest}.original"))
    if existing:
        return existing[-1]

    final_path = recovery_dir / (
        f"jobs.{time.time_ns()}.{safe_reason}.{short_digest}.original"
    )

    fd = None
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=".jobs-recovery-", suffix=".tmp", dir=str(recovery_dir)
        )
        with os.fdopen(fd, "wb") as dst:
            fd = None
            dst.write(original_bytes)
            dst.flush()
            os.fsync(dst.fileno())

        os.replace(tmp_name, final_path)
        tmp_name = None

        if os.name != "nt":
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            dir_fd = os.open(str(recovery_dir), flags)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

        artifacts = sorted(
            recovery_dir.glob("jobs.*.original"),
            key=lambda p: p.stat().st_mtime_ns,
            reverse=True,
        )
        for stale in artifacts[_MAX_RECOVERY_ARTIFACTS:]:
            try:
                stale.unlink()
            except OSError:
                logger.warning(
                    "Could not prune old cron recovery artifact %s", stale
                )

        return final_path
    except Exception:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise
'''

    jobs = replace_once(
        jobs,
        pinned_old_parser,
        new_parser,
        "jobs exact-byte parser/preservation helper",
    )

    jobs = replace_once(
        jobs,
        "        data, _strict_retry = _parse_jobs_file(jobs_file)\n",
        "        raw_bytes = jobs_file.read_bytes()\n"
        "        data, _strict_retry = _parse_jobs_bytes(raw_bytes)\n",
        "jobs exact-byte load",
    )

    old_repair = '''    if jobs and repair:
        save_jobs(jobs)
        logger.warning("Auto-repaired jobs.json (%s)", repair)
'''

    new_repair = '''    if jobs and repair:
        # The initial parse may have happened outside the cross-process store
        # lock. Re-enter under the existing lock and re-read before preserving
        # or replacing so a sibling writer cannot make us archive stale bytes.
        if not getattr(_jobs_lock_state, "depth", 0):
            with _jobs_lock():
                return load_jobs()
        _preserve_jobs_bytes_before_repair(jobs_file, raw_bytes, repair)
        save_jobs(jobs)
        logger.warning("Auto-repaired jobs.json (%s)", repair)
'''

    jobs = replace_once(
        jobs,
        old_repair,
        new_repair,
        "jobs repair transition",
    )

    ast.parse(jobs)
    jobs_path.write_text(jobs, encoding="utf-8", newline="\n")

    health = health_path.read_text(encoding="utf-8")

    classifier_start = health.find("_AUTH_RE = re.compile(")
    classifier_end = health.find("\n\ndef _parse_time(", classifier_start)
    if classifier_start < 0 or classifier_end < 0:
        raise RuntimeError("upstream classifier block anchors not found")

    classifier_block = health[classifier_start:classifier_end].rstrip() + "\n"
    classifier_hash = hashlib.sha256(
        classifier_block.encode("utf-8")
    ).hexdigest()
    if classifier_hash != EXPECTED_CLASSIFIER_BLOCK_SHA256:
        raise RuntimeError(
            "upstream classifier block drift: "
            f"{classifier_hash} != {EXPECTED_CLASSIFIER_BLOCK_SHA256}"
        )

    classifier_header = '''"""Shared deterministic cron execution error classification.

The rule block below is extracted unchanged from the pinned Hermes v0.21.5
cron-health implementation. The tiny _contains_any helper is duplicated here
with the same semantics to keep cron independent of agent.monitoring imports.
"""

from __future__ import annotations

import re
from typing import Any, Callable


def _contains_any(*needles: str) -> Callable[[str], bool]:
    return lambda text: any(needle in text for needle in needles)


'''

    classifier = (
        classifier_header
        + classifier_block
        + '\n__all__ = ["classify_cron_error"]\n'
    )
    ast.parse(classifier)
    classifier_path.write_text(classifier, encoding="utf-8", newline="\n")

    health = health[:classifier_start] + health[classifier_end + 2:]

    health = replace_once(
        health,
        "import logging\nimport re\n",
        "import logging\n",
        "cron_health remove re import",
    )

    health = replace_once(
        health,
        "from agent.monitoring.gateway_health import GatewayMetric, _contains_any, _safe_instance_id\n",
        "from agent.monitoring.gateway_health import GatewayMetric, _safe_instance_id\n",
        "cron_health remove gateway _contains_any import",
    )

    health = replace_once(
        health,
        "from cron.jobs import (\n",
        "from cron.error_classification import classify_cron_error\n"
        "from cron.jobs import (\n",
        "cron_health shared classifier import",
    )

    health_tree = ast.parse(health)
    if any(
        isinstance(node, ast.Name) and node.id == "re"
        for node in ast.walk(health_tree)
    ):
        raise RuntimeError("cron_health still references re after classifier extraction")

    if "def classify_cron_error(" in health:
        raise RuntimeError("cron_health still defines a second classifier")

    health_path.write_text(health, encoding="utf-8", newline="\n")

    executions = executions_path.read_text(encoding="utf-8")

    executions = replace_once(
        executions,
        "from hermes_constants import get_hermes_home\n",
        "from cron.error_classification import classify_cron_error\n"
        "from hermes_constants import get_hermes_home\n",
        "executions shared classifier import",
    )

    executions = replace_once(
        executions,
        '''    add_column_if_missing(conn, "executions", "scheduled_instant", "scheduled_instant TEXT")
    conn.execute(
''',
        '''    add_column_if_missing(conn, "executions", "scheduled_instant", "scheduled_instant TEXT")
    add_column_if_missing(conn, "executions", "error_class", "error_class TEXT")
    conn.execute(
''',
        "executions error_class migration",
    )

    executions = replace_once(
        executions,
        '''    detail = None if success else (str(error) if error else "unknown failure")
    with _transaction() as conn:
''',
        '''    detail = None if success else (str(error) if error else "unknown failure")
    error_class = None if success else classify_cron_error(detail)
    with _transaction() as conn:
''',
        "finish_execution classification",
    )

    executions = replace_once(
        executions,
        '''               SET status=?, finished_at=?, error=?, handoff_pending=0,
                   handoff_started_at=NULL, delivery_outcome=?
''',
        '''               SET status=?, finished_at=?, error=?, handoff_pending=0,
                   handoff_started_at=NULL, delivery_outcome=?, error_class=?
''',
        "finish_execution durable SQL",
    )

    executions = replace_once(
        executions,
        '''            (status, now, detail, delivery_outcome, execution_id, _PROCESS_ID, os.getpid()),
''',
        '''            (status, now, detail, delivery_outcome, error_class,
             execution_id, _PROCESS_ID, os.getpid()),
''',
        "finish_execution durable SQL parameters",
    )

    executions = replace_once(
        executions,
        '''                   SET status='unknown', finished_at=?, error=?,
                       handoff_pending=0, handoff_started_at=NULL
''',
        '''                   SET status='unknown', finished_at=?, error=?, error_class='interrupted',
                       handoff_pending=0, handoff_started_at=NULL
''',
        "recovery factual interrupted classification",
    )

    ast.parse(executions)
    executions_path.write_text(executions, encoding="utf-8", newline="\n")

    print(f"P6_UPG_02_CLASSIFIER_BLOCK_SHA256={classifier_hash}")
    print("P6_UPG_02_TRANSFORM=PASS")
    print("P6_UPG_02_CHANGED=agent/monitoring/cron_health.py")
    print("P6_UPG_02_CHANGED=cron/error_classification.py")
    print("P6_UPG_02_CHANGED=cron/executions.py")
    print("P6_UPG_02_CHANGED=cron/jobs.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
