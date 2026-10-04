from __future__ import annotations

import argparse
import importlib.util
import os
import sqlite3
import subprocess
import sys
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


def worker_probe(repo_root: Path, runtime_site: Path) -> int:
    stage = "preflight"
    try:
        runtime_site = runtime_site.resolve()
        sys_path_resolved = []
        for entry in sys.path:
            if not entry:
                continue
            try:
                sys_path_resolved.append(Path(entry).resolve())
            except OSError:
                continue

        runtime_on_parent_path = runtime_site in sys_path_resolved
        emit("P6_UPG_03_WORKER_RUNTIME_SITE_ON_PARENT_PATH", runtime_on_parent_path)
        if not runtime_on_parent_path:
            raise RuntimeError("disposable runtime site-packages is not active on parent sys.path")

        # Load only the exact helper file. Importing through cron.* would execute
        # cron/__init__.py and pull unrelated scheduler dependencies into the
        # harness before we have tested the worker environment itself.
        stage = "load_worker_env_helper"
        worker_path = repo_root / "cron" / "scheduler_worker_env.py"
        spec = importlib.util.spec_from_file_location(
            "p6_upg_03_scheduler_worker_env",
            worker_path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load worker-env helper: {worker_path}")
        worker_env = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker_env)
        emit("P6_UPG_03_WORKER_HELPER_LOAD", "PASS")

        # The parent/store process deliberately has the runtime dependency path
        # active. Avoid importing the full dependency stack here; the behavior
        # under test is whether the sanitized CHILD can still import it.
        stage = "build_child_env"
        child_env = dict(os.environ)
        child_env.pop("PYTHONPATH", None)
        child_env.pop("PYTHONHOME", None)
        child_env.pop("VIRTUAL_ENV", None)
        child_env = worker_env.pin_hermes_tree_on_pythonpath(child_env, repo_root)

        entries = [
            Path(entry).resolve()
            for entry in child_env.get("PYTHONPATH", "").split(os.pathsep)
            if entry
        ]
        emit("P6_UPG_03_WORKER_CHILD_HAS_REPO_ROOT", repo_root.resolve() in entries)
        emit("P6_UPG_03_WORKER_CHILD_HAS_RUNTIME_SITE", runtime_site in entries)

        stage = "spawn_child"
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

        emit("P6_UPG_03_WORKER_PARENT_PATH_PRECONDITION", "PASS")
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
        if child.returncode != 0 and not missing_dep:
            diagnostic = " | ".join(
                line.strip() for line in child.stderr.splitlines()[-4:] if line.strip()
            )
            emit("P6_UPG_03_WORKER_CHILD_UNEXPECTED_ERROR", diagnostic or "unknown")
        return 0
    except Exception as exc:
        emit("P6_UPG_03_WORKER_PROBE_STAGE", stage)
        emit("P6_UPG_03_WORKER_PROBE_ERROR_TYPE", type(exc).__name__)
        emit("P6_UPG_03_WORKER_PROBE_ERROR", str(exc).replace("\n", " | "))
        return 2


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


def integrity_selftest(work_root: Path) -> int:
    root = work_root / "integrity-selftest"
    root.mkdir(parents=True, exist_ok=False)

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

    # Keep fixtures under the disposable rehearsal root and let process exit
    # release any briefly retained Windows sqlite3 file handle. Immediate
    # TemporaryDirectory cleanup is not part of the integrity contract.
    emit("P6_UPG_03_INTEGRITY_FIXTURE_ROOT", root)
    emit("P6_UPG_03_POSTRESTART_INTEGRITY_GUARD_SELFTEST", "PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("static", "worker", "integrity"))
    parser.add_argument("--repo-root")
    parser.add_argument("--runtime-site")
    parser.add_argument("--work-root")
    args = parser.parse_args()

    if args.mode == "static":
        if not args.repo_root:
            parser.error("static requires --repo-root")
        return static_probe(Path(args.repo_root).resolve())

    if args.mode == "worker":
        if not args.repo_root or not args.runtime_site:
            parser.error("worker requires --repo-root and --runtime-site")
        return worker_probe(
            Path(args.repo_root).resolve(),
            Path(args.runtime_site).resolve(),
        )

    if not args.work_root:
        parser.error("integrity requires --work-root")
    return integrity_selftest(Path(args.work_root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
