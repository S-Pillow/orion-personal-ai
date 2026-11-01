#!/usr/bin/env python3
"""Isolated runtime contract for Orion's surviving Hermes v0.22.5 cron ports.

Exercises only disposable local filesystem/SQLite behavior:
- P6-03 exact jobs.json pre-repair byte preservation.
- P6-04A durable cron execution error_class persistence.

No gateway is launched and no production cron job, provider, model, memory, STT, or TTS call is made.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

import v0225_isolated_gateway_contract_smoke as base
import v0225_isolated_gateway_contract_smoke_v2 as v2
import v0225_isolated_gateway_contract_smoke_v5 as v5

PRODUCTION_PROFILE = v5.PRODUCTION_PROFILE
PREFIX = "orion-hermes-v0225-cron-compat-"


def _static_snapshot(root: Path, profile_home: Path) -> dict[str, str | None]:
    paths = [
        root / "config.yaml",
        root / ".env",
        root / "active_profile",
        profile_home / "config.yaml",
        profile_home / ".env",
    ]
    return {str(path): base.sha256(path) for path in paths}


def _pid_snapshot(root: Path, profile_home: Path) -> dict[str, str | None]:
    paths = [root / "gateway.pid", profile_home / "gateway.pid"]
    return {str(path): base.sha256(path) for path in paths}


def _child_env(scratch_home: Path) -> dict[str, str]:
    allow = {
        "SystemRoot", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP",
        "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PROGRAMDATA",
        "PROCESSOR_ARCHITECTURE", "PROCESSOR_ARCHITEW6432", "NUMBER_OF_PROCESSORS",
        "USERNAME",
    }
    env = {name: value for name, value in os.environ.items() if name in allow}
    env.update(
        {
            "HERMES_HOME": str(scratch_home),
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
            "NO_COLOR": "1",
        }
    )
    return env


def _run_contract(candidate: Path, runtime_python: Path, scratch_home: Path) -> list[str]:
    code = r'''
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

home = Path(os.environ["HERMES_HOME"]).resolve()
cron_dir = home / "cron"
cron_dir.mkdir(parents=True, exist_ok=True)

# P6-03: a valid bare-list store is a known auto-repair shape. Use a BOM + CRLF so
# byte preservation proves the pre-image is exact, not reconstructed from decoded JSON.
original = b"\xef\xbb\xbf[\r\n]\r\n"
jobs_file = cron_dir / "jobs.json"
jobs_file.write_bytes(original)
original_sha = hashlib.sha256(original).hexdigest()

from cron import jobs as jobs_mod

loaded = jobs_mod.load_jobs()
if loaded != []:
    raise RuntimeError(f"P6-03 repair returned unexpected jobs: {loaded!r}")

recovery_dir = cron_dir / "recovery"
recovery = sorted(recovery_dir.glob("jobs.json.*.original")) if recovery_dir.is_dir() else []
if len(recovery) != 1:
    raise RuntimeError(f"P6-03 expected one recovery pre-image; observed {len(recovery)}")
preserved = recovery[0].read_bytes()
if preserved != original:
    raise RuntimeError(
        "P6-03 recovery bytes differ from exact pre-repair bytes: "
        f"expected_sha={original_sha} observed_sha={hashlib.sha256(preserved).hexdigest()}"
    )
if original_sha not in recovery[0].name:
    raise RuntimeError("P6-03 recovery filename does not carry the source SHA-256")
if jobs_file.read_bytes() == original:
    raise RuntimeError("P6-03 repair did not rewrite the source jobs.json")

print("ORION_P603_TRIGGER=bare_list_wrapped_as_dict")
print("ORION_P603_SOURCE_SHA256=" + original_sha)
print("ORION_P603_RECOVERY_FILE=" + recovery[0].name)
print("ORION_P603_EXACT_PRE_REPAIR_BYTES=PASS")
print("ORION_P603_REPAIR_REWRITE=PASS")

# P6-04A: use the candidate's real execution ledger against a scratch DB.
from cron import executions as exec_mod

exec_db = cron_dir / "executions.db"
exec_mod.EXECUTIONS_FILE = exec_db

failed = exec_mod.create_execution("orion-p604a-failed", source="orion_qualification")
failed_id = failed["id"]
if exec_mod.mark_execution_running(failed_id) is None:
    raise RuntimeError("P6-04A could not transition failed test execution to running")
failed_final = exec_mod.finish_execution(
    failed_id,
    success=False,
    error="HTTP 429 quota exceeded",
    delivery_outcome="qualification_local_only",
)
if not isinstance(failed_final, dict):
    raise RuntimeError("P6-04A failed execution did not return a terminal record")
if failed_final.get("status") != "failed":
    raise RuntimeError(f"P6-04A failed status mismatch: {failed_final!r}")
if failed_final.get("error_class") != "rate_limited":
    raise RuntimeError(f"P6-04A returned error_class mismatch: {failed_final!r}")

succeeded = exec_mod.create_execution("orion-p604a-success", source="orion_qualification")
success_id = succeeded["id"]
if exec_mod.mark_execution_running(success_id) is None:
    raise RuntimeError("P6-04A could not transition success test execution to running")
success_final = exec_mod.finish_execution(
    success_id,
    success=True,
    delivery_outcome="qualification_local_only",
)
if not isinstance(success_final, dict) or success_final.get("status") != "completed":
    raise RuntimeError(f"P6-04A success status mismatch: {success_final!r}")
if success_final.get("error_class") is not None:
    raise RuntimeError(f"P6-04A successful execution received error_class: {success_final!r}")

con = sqlite3.connect(f"file:{exec_db.as_posix()}?mode=ro", uri=True, timeout=5.0)
try:
    columns = {row[1] for row in con.execute("PRAGMA table_info(executions)").fetchall()}
    if "error_class" not in columns:
        raise RuntimeError("P6-04A executions schema is missing error_class")
    failed_row = con.execute(
        "SELECT status, error, error_class FROM executions WHERE id=?", (failed_id,)
    ).fetchone()
    success_row = con.execute(
        "SELECT status, error, error_class FROM executions WHERE id=?", (success_id,)
    ).fetchone()
finally:
    con.close()

if failed_row != ("failed", "HTTP 429 quota exceeded", "rate_limited"):
    raise RuntimeError(f"P6-04A durable failed row mismatch: {failed_row!r}")
if success_row != ("completed", None, None):
    raise RuntimeError(f"P6-04A durable success row mismatch: {success_row!r}")

print("ORION_P604A_SCHEMA_ERROR_CLASS=PASS")
print("ORION_P604A_FAILED_CLASSIFICATION=rate_limited")
print("ORION_P604A_DURABLE_FAILED_ROW=PASS")
print("ORION_P604A_SUCCESS_NULL_CLASS=PASS")
print("ORION_CRON_PROVIDER_CALLS=0")
print("ORION_CRON_EXTERNAL_JOB_EXECUTION=false")
'''
    proc = subprocess.run(
        [str(runtime_python), "-B", "-c", code],
        cwd=str(candidate),
        env=_child_env(scratch_home),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "isolated cron compatibility child failed "
            f"(rc={proc.returncode})\n--- STDOUT ---\n{proc.stdout.rstrip()}\n"
            f"--- STDERR ---\n{proc.stderr.rstrip()}"
        )
    return [line for line in proc.stdout.splitlines() if line.startswith("ORION_")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--production-hermes-root", required=True)
    ap.add_argument("--candidate-root", required=True)
    ap.add_argument("--runtime-python", required=True)
    args = ap.parse_args()

    prod_root = Path(args.production_hermes_root).resolve()
    prod_profile = prod_root / "profiles" / PRODUCTION_PROFILE
    candidate = Path(args.candidate_root).resolve()
    runtime_python = Path(args.runtime_python).resolve()

    if not prod_root.is_dir() or not prod_profile.is_dir():
        raise RuntimeError("production Hermes root or COMPANION profile is missing")
    if not candidate.is_dir() or not (candidate / ".git").exists():
        raise RuntimeError("candidate root is not a Git checkout")
    if not runtime_python.is_file():
        raise RuntimeError("isolated runtime Python is missing")

    expected_paths = v2.verify_candidate(candidate)
    prod_static_before = _static_snapshot(prod_root, prod_profile)
    prod_pid_before = _pid_snapshot(prod_root, prod_profile)
    prod_health_before = v5.health_state(8642)

    scratch_home = Path(tempfile.mkdtemp(prefix=PREFIX)).resolve()

    print(f"CANDIDATE_HEAD={base.git_single(candidate, 'rev-parse', 'HEAD')}")
    print(f"PRODUCTION_8642_HEALTH_BASELINE={prod_health_before}")
    print("QUALIFICATION_SCOPE=p603_p604a_runtime_local_only")
    print(f"SCRATCH_HERMES_HOME={scratch_home}")
    print("GATEWAY_LAUNCHED=false")
    print("PRODUCTION_CRON_STORE_TOUCHED=false")
    print("PRODUCTION_CRON_JOB_EXECUTED=false")
    print("MODEL_PROVIDER_CALLS=0")
    print("MEMORY_CALLS=0")
    print("STT_PROVIDER_CALLS=0")
    print("TTS_PROVIDER_CALLS=0")

    markers = _run_contract(candidate, runtime_python, scratch_home)
    for marker in markers:
        print(marker)

    post_errors: list[str] = []
    prod_static_after = _static_snapshot(prod_root, prod_profile)
    prod_pid_after = _pid_snapshot(prod_root, prod_profile)
    prod_health_after = v5.health_state(8642)

    if prod_static_after != prod_static_before:
        post_errors.append("production static config changed during cron compatibility smoke")
    if prod_pid_after != prod_pid_before:
        post_errors.append("production gateway PID identity changed during cron compatibility smoke")
    if prod_health_after != prod_health_before:
        post_errors.append(
            "production health baseline changed: "
            f"{prod_health_before} -> {prod_health_after}"
        )
    if base.candidate_status_paths(candidate) != expected_paths:
        post_errors.append("candidate Git status changed during cron compatibility smoke")
    for rel, expected in base.EXPECTED_CANDIDATE_HASHES.items():
        if base.sha256(candidate / rel) != expected:
            post_errors.append(f"candidate source changed during cron compatibility smoke: {rel}")

    print(f"PRODUCTION_8642_HEALTH_AFTER={prod_health_after}")
    if prod_static_after == prod_static_before:
        print("PRODUCTION_STATIC_CONFIG_UNCHANGED=PASS")
    if prod_pid_after == prod_pid_before:
        print("PRODUCTION_GATEWAY_PID_IDENTITY_UNCHANGED=PASS")
    if base.candidate_status_paths(candidate) == expected_paths:
        print("CANDIDATE_GIT_STATUS_UNCHANGED=PASS")
    print(f"SCRATCH_ROOT={scratch_home}")

    if post_errors:
        for item in post_errors:
            print(f"POSTCONDITION_ERROR={item}")
        raise RuntimeError("\n".join(post_errors))

    print("P603_RUNTIME_EXACT_REPAIR_PRESERVATION=PASS")
    print("P604A_RUNTIME_DURABLE_ERROR_CLASS=PASS")
    print("ISOLATED_CRON_COMPAT_CONTRACT=PASS")
    print("PRODUCTION_HERMES_MUTATED=false")
    print("COMPANION_STATE_MUTATED=false")
    print("PRODUCTION_RUNTIME_RESTARTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
