from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def emit(key: str, value: object) -> None:
    if isinstance(value, bool):
        value = "true" if value else "false"
    print(f"{key}={value}", flush=True)


def static_probe(repo_root: Path) -> int:
    worker_path = repo_root / "cron" / "scheduler_worker_env.py"
    startup_path = repo_root / "gateway" / "run_startup.py"

    if not worker_path.is_file():
        raise AssertionError(f"missing pinned target source: {worker_path}")
    if not startup_path.is_file():
        raise AssertionError(f"missing pinned target source: {startup_path}")

    worker = worker_path.read_text(encoding="utf-8")
    startup = startup_path.read_text(encoding="utf-8")

    worker_pins_runtime_site = "selected_venv" in worker and "site_packages" in worker
    warmup_releases_gate = "opening inbound gate anyway" in startup

    emit("P6_UPG_03_TARGET_WORKER_PINS_RUNTIME_SITE", worker_pins_runtime_site)
    emit("P6_UPG_03_TARGET_WARMUP_CAN_RELEASE_GATE", warmup_releases_gate)

    if worker_pins_runtime_site:
        emit("P6_UPG_03_WORKER_RISK_STATIC", "not_present")
    else:
        emit("P6_UPG_03_WORKER_RISK_STATIC", "present")

    if not warmup_releases_gate:
        emit("P6_UPG_03_WARMUP_RISK_STATIC", "not_present")
    else:
        emit("P6_UPG_03_WARMUP_RISK_STATIC", "present")

    # The open source-completion-pending issue remains a production-upgrade
    # operational guard, but hermes_cli/venv_sync.py is not present in the
    # exact v2026.9.24 target tree. Do not infer exact-tag applicability by
    # reading a current-main path that the pinned target does not contain.
    emit("P6_UPG_03_SOURCE_COMPLETION_MARKER_EXACT_TAG", "not_asserted")

    emit("P6_UPG_03_STATIC_RISK_PROBE", "PASS")
    return 0


def worker_probe(repo_root: Path, runtime_venv: Path, runtime_site: Path) -> int:
    # Parent-equivalent process: dependency-light interpreter with the runtime
    # dependency path injected in-process, matching the reported PM topology.
    import cron.scheduler_worker_env as worker_env
    import croniter  # noqa: F401
    import ruamel.yaml  # noqa: F401
    import pm.environments as environments

    environments.selected_venv = lambda _root: runtime_venv
    environments.site_packages = lambda _venv: runtime_site

    child_env = dict(os.environ)
    child_env.pop("PYTHONPATH", None)
    child_env.pop("PYTHONHOME", None)
    child_env.pop("VIRTUAL_ENV", None)

    child_env = worker_env.pin_hermes_tree_on_pythonpath(child_env, repo_root)

    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            (
                "import croniter, ruamel.yaml, cron.scheduler; "
                "print('P6_UPG_03_WORKER_CHILD_IMPORTS=PASS')"
            ),
        ],
        cwd=str(repo_root),
        env=child_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    emit("P6_UPG_03_WORKER_PARENT_IMPORTS", "PASS")
    emit("P6_UPG_03_WORKER_CHILD_RC", child.returncode)

    if child.stdout.strip():
        for line in child.stdout.splitlines():
            if line.strip():
                print(line.strip(), flush=True)

    stderr = child.stderr.lower()
    missing_dep = "modulenotfounderror" in stderr and (
        "ruamel" in stderr or "croniter" in stderr
    )
    emit("P6_UPG_03_WORKER_MISSING_RUNTIME_DEP", missing_dep)
    emit("P6_UPG_03_WORKER_CHILD_IMPORTS_PASS", child.returncode == 0)
    return 0


def _integrity_ok(db: Path) -> bool:
    try:
        uri = f"file:{db.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            rows = [str(row[0]) for row in conn.execute("PRAGMA integrity_check").fetchall()]
        finally:
            conn.close()
        return rows == ["ok"]
    except Exception:
        return False


def integrity_selftest() -> int:
    with tempfile.TemporaryDirectory(prefix="p6-upg-03-integrity-") as td:
        root = Path(td)
        good = root / "good.db"
        bad = root / "bad.db"

        with sqlite3.connect(good) as conn:
            conn.execute("CREATE TABLE sentinel(id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO sentinel(value) VALUES ('preserved')")
            conn.commit()

        bad.write_bytes(b"SQLite format 3\x00" + b"orion-invalid-db-image" * 64)

        if not _integrity_ok(good):
            raise AssertionError("fresh valid SQLite database failed integrity guard")
        if _integrity_ok(bad):
            raise AssertionError("invalid SQLite image unexpectedly passed integrity guard")

    emit("P6_UPG_03_POSTRESTART_INTEGRITY_GUARD_SELFTEST", "PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("static", "worker", "integrity"))
    parser.add_argument("--repo-root")
    parser.add_argument("--runtime-venv")
    parser.add_argument("--runtime-site")
    parser.add_argument("--work-root")
    args = parser.parse_args()

    if args.mode == "static":
        if not args.repo_root:
            parser.error("static requires --repo-root")
        return static_probe(Path(args.repo_root).resolve())

    if args.mode == "worker":
        if not args.repo_root or not args.runtime_venv or not args.runtime_site:
            parser.error("worker requires --repo-root, --runtime-venv, and --runtime-site")
        return worker_probe(
            Path(args.repo_root).resolve(),
            Path(args.runtime_venv).resolve(),
            Path(args.runtime_site).resolve(),
        )

    if not args.work_root:
        parser.error("integrity requires --work-root")
    return integrity_selftest(Path(args.work_root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
