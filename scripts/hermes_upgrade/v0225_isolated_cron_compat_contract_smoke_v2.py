#!/usr/bin/env python3
"""Observer-hardened isolated runtime contract for Orion's Hermes v0.22.5 cron ports.

Separates P6-03 and P6-04A into independent bounded child processes with flushed phase markers so
a timeout identifies the last completed phase. Production/candidate postconditions are evaluated
even when one or both contract children fail.

No gateway is launched and no production cron job, model, memory, STT, or TTS provider call is made.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import time
from pathlib import Path

import v0225_isolated_cron_compat_contract_smoke as v1
import v0225_isolated_gateway_contract_smoke as base
import v0225_isolated_gateway_contract_smoke_v2 as gateway_v2
import v0225_isolated_gateway_contract_smoke_v5 as v5

PRODUCTION_PROFILE = v5.PRODUCTION_PROFILE
PREFIX = "orion-hermes-v0225-cron-compat-v2-"
PHASE_TIMEOUT_S = 45.0

P603_CODE = r'''
from __future__ import annotations
import hashlib, os
from pathlib import Path
print("ORION_PHASE=P603_SETUP_BEGIN", flush=True)
home = Path(os.environ["HERMES_HOME"]).resolve(); cron_dir = home / "cron"; cron_dir.mkdir(parents=True, exist_ok=True)
original = b"\xef\xbb\xbf[\r\n]\r\n"; jobs_file = cron_dir / "jobs.json"; jobs_file.write_bytes(original)
original_sha = hashlib.sha256(original).hexdigest(); print("ORION_PHASE=P603_SETUP_END", flush=True)
print("ORION_PHASE=P603_IMPORT_JOBS_BEGIN", flush=True)
from cron import jobs as jobs_mod
print("ORION_PHASE=P603_IMPORT_JOBS_END", flush=True)
print("ORION_PHASE=P603_LOAD_JOBS_BEGIN", flush=True)
loaded = jobs_mod.load_jobs(); print("ORION_PHASE=P603_LOAD_JOBS_END", flush=True)
if loaded != []: raise RuntimeError(f"P6-03 repair returned unexpected jobs: {loaded!r}")
print("ORION_PHASE=P603_VERIFY_RECOVERY_BEGIN", flush=True)
recovery_dir = cron_dir / "recovery"; recovery = sorted(recovery_dir.glob("jobs.json.*.original")) if recovery_dir.is_dir() else []
if len(recovery) != 1: raise RuntimeError(f"P6-03 expected one recovery pre-image; observed {len(recovery)}")
preserved = recovery[0].read_bytes()
if preserved != original: raise RuntimeError(f"P6-03 recovery bytes differ: expected_sha={original_sha} observed_sha={hashlib.sha256(preserved).hexdigest()}")
if original_sha not in recovery[0].name: raise RuntimeError("P6-03 recovery filename does not carry source SHA-256")
if jobs_file.read_bytes() == original: raise RuntimeError("P6-03 repair did not rewrite source jobs.json")
print("ORION_PHASE=P603_VERIFY_RECOVERY_END", flush=True)
print("ORION_P603_TRIGGER=bare_list_wrapped_as_dict", flush=True)
print("ORION_P603_SOURCE_SHA256=" + original_sha, flush=True)
print("ORION_P603_RECOVERY_FILE=" + recovery[0].name, flush=True)
print("ORION_P603_EXACT_PRE_REPAIR_BYTES=PASS", flush=True)
print("ORION_P603_REPAIR_REWRITE=PASS", flush=True)
'''

P604A_CODE = r'''
from __future__ import annotations
import os, sqlite3
from pathlib import Path
print("ORION_PHASE=P604A_SETUP_BEGIN", flush=True)
home = Path(os.environ["HERMES_HOME"]).resolve(); cron_dir = home / "cron"; cron_dir.mkdir(parents=True, exist_ok=True); exec_db = cron_dir / "executions.db"
print("ORION_PHASE=P604A_SETUP_END", flush=True)
print("ORION_PHASE=P604A_IMPORT_EXECUTIONS_BEGIN", flush=True)
from cron import executions as exec_mod
print("ORION_PHASE=P604A_IMPORT_EXECUTIONS_END", flush=True); exec_mod.EXECUTIONS_FILE = exec_db
print("ORION_PHASE=P604A_FAILED_EXECUTION_BEGIN", flush=True)
failed = exec_mod.create_execution("orion-p604a-failed", source="orion_qualification"); failed_id = failed["id"]
if exec_mod.mark_execution_running(failed_id) is None: raise RuntimeError("P6-04A could not transition failed execution to running")
failed_final = exec_mod.finish_execution(failed_id, success=False, error="HTTP 429 quota exceeded", delivery_outcome="qualification_local_only")
if not isinstance(failed_final, dict) or failed_final.get("status") != "failed" or failed_final.get("error_class") != "rate_limited": raise RuntimeError(f"P6-04A failed terminal mismatch: {failed_final!r}")
print("ORION_PHASE=P604A_FAILED_EXECUTION_END", flush=True)
print("ORION_PHASE=P604A_SUCCESS_EXECUTION_BEGIN", flush=True)
succeeded = exec_mod.create_execution("orion-p604a-success", source="orion_qualification"); success_id = succeeded["id"]
if exec_mod.mark_execution_running(success_id) is None: raise RuntimeError("P6-04A could not transition success execution to running")
success_final = exec_mod.finish_execution(success_id, success=True, delivery_outcome="qualification_local_only")
if not isinstance(success_final, dict) or success_final.get("status") != "completed" or success_final.get("error_class") is not None: raise RuntimeError(f"P6-04A success terminal mismatch: {success_final!r}")
print("ORION_PHASE=P604A_SUCCESS_EXECUTION_END", flush=True)
print("ORION_PHASE=P604A_SQLITE_VERIFY_BEGIN", flush=True)
con = sqlite3.connect(f"file:{exec_db.as_posix()}?mode=ro", uri=True, timeout=5.0)
try:
    columns = {row[1] for row in con.execute("PRAGMA table_info(executions)").fetchall()}
    if "error_class" not in columns: raise RuntimeError("P6-04A executions schema missing error_class")
    failed_row = con.execute("SELECT status,error,error_class FROM executions WHERE id=?", (failed_id,)).fetchone()
    success_row = con.execute("SELECT status,error,error_class FROM executions WHERE id=?", (success_id,)).fetchone()
finally:
    con.close()
if failed_row != ("failed", "HTTP 429 quota exceeded", "rate_limited"): raise RuntimeError(f"P6-04A durable failed row mismatch: {failed_row!r}")
if success_row != ("completed", None, None): raise RuntimeError(f"P6-04A durable success row mismatch: {success_row!r}")
print("ORION_PHASE=P604A_SQLITE_VERIFY_END", flush=True)
print("ORION_P604A_SCHEMA_ERROR_CLASS=PASS", flush=True)
print("ORION_P604A_FAILED_CLASSIFICATION=rate_limited", flush=True)
print("ORION_P604A_DURABLE_FAILED_ROW=PASS", flush=True)
print("ORION_P604A_SUCCESS_NULL_CLASS=PASS", flush=True)
print("ORION_CRON_PROVIDER_CALLS=0", flush=True)
print("ORION_CRON_EXTERNAL_JOB_EXECUTION=false", flush=True)
'''


def _last_phase(text: str) -> str:
    phases = [line.split("=", 1)[1] for line in text.splitlines() if line.startswith("ORION_PHASE=")]
    return phases[-1] if phases else "NO_PHASE_MARKER"


def _emit_child_output(label: str, stdout: str, stderr: str) -> None:
    for line in stdout.splitlines():
        if line.startswith("ORION_"):
            print(line)
    if stderr.strip():
        print(f"{label}_STDERR_BEGIN"); print(stderr.rstrip()); print(f"{label}_STDERR_END")


def _run_child(label: str, candidate: Path, runtime_python: Path, scratch_home: Path, code: str) -> str | None:
    proc = subprocess.Popen([str(runtime_python), "-B", "-c", code], cwd=str(candidate), env=v1._child_env(scratch_home), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    started = time.monotonic()
    try:
        stdout, stderr = proc.communicate(timeout=PHASE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill(); stdout, stderr = proc.communicate(); elapsed = time.monotonic() - started
        _emit_child_output(label, stdout or "", stderr or ""); last = _last_phase(stdout or "")
        print(f"{label}_TIMEOUT=YES|elapsed_s={elapsed:.3f}|last_phase={last}")
        return f"{label} timed out after {PHASE_TIMEOUT_S:.0f}s; last_phase={last}"
    elapsed = time.monotonic() - started; _emit_child_output(label, stdout or "", stderr or "")
    if proc.returncode != 0:
        last = _last_phase(stdout or ""); print(f"{label}_EXIT=FAIL|rc={proc.returncode}|elapsed_s={elapsed:.3f}|last_phase={last}")
        return f"{label} failed rc={proc.returncode}; last_phase={last}"
    print(f"{label}_EXIT=PASS|elapsed_s={elapsed:.3f}|last_phase={_last_phase(stdout or '')}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--production-hermes-root", required=True); ap.add_argument("--candidate-root", required=True); ap.add_argument("--runtime-python", required=True); args = ap.parse_args()
    prod_root = Path(args.production_hermes_root).resolve(); prod_profile = prod_root / "profiles" / PRODUCTION_PROFILE; candidate = Path(args.candidate_root).resolve(); runtime_python = Path(args.runtime_python).resolve()
    if not prod_root.is_dir() or not prod_profile.is_dir(): raise RuntimeError("production Hermes root or COMPANION profile is missing")
    if not candidate.is_dir() or not (candidate / ".git").exists(): raise RuntimeError("candidate root is not a Git checkout")
    if not runtime_python.is_file(): raise RuntimeError("isolated runtime Python is missing")
    expected_paths = gateway_v2.verify_candidate(candidate); prod_static_before = v1._static_snapshot(prod_root, prod_profile); prod_pid_before = v1._pid_snapshot(prod_root, prod_profile); prod_health_before = v5.health_state(8642)
    scratch_root = Path(tempfile.mkdtemp(prefix=PREFIX)).resolve(); p603_home = scratch_root / "p603-home"; p604a_home = scratch_root / "p604a-home"; p603_home.mkdir(parents=True); p604a_home.mkdir(parents=True)
    print(f"CANDIDATE_HEAD={base.git_single(candidate, 'rev-parse', 'HEAD')}"); print(f"PRODUCTION_8642_HEALTH_BASELINE={prod_health_before}"); print("QUALIFICATION_SCOPE=p603_p604a_runtime_local_only_v2"); print(f"SCRATCH_ROOT={scratch_root}"); print(f"P603_SCRATCH_HERMES_HOME={p603_home}"); print(f"P604A_SCRATCH_HERMES_HOME={p604a_home}"); print(f"PHASE_TIMEOUT_S={PHASE_TIMEOUT_S:.0f}"); print("GATEWAY_LAUNCHED=false"); print("PRODUCTION_CRON_JOB_EXECUTED=false"); print("MODEL_PROVIDER_CALLS=0"); print("MEMORY_CALLS=0"); print("STT_PROVIDER_CALLS=0"); print("TTS_PROVIDER_CALLS=0")
    failures: list[str] = []
    p603_error = _run_child("P603_CHILD", candidate, runtime_python, p603_home, P603_CODE)
    if p603_error: failures.append(p603_error)
    p604a_error = _run_child("P604A_CHILD", candidate, runtime_python, p604a_home, P604A_CODE)
    if p604a_error: failures.append(p604a_error)
    prod_static_after = v1._static_snapshot(prod_root, prod_profile); prod_pid_after = v1._pid_snapshot(prod_root, prod_profile); prod_health_after = v5.health_state(8642)
    if prod_static_after != prod_static_before: failures.append("production static config changed during cron compatibility smoke v2")
    if prod_pid_after != prod_pid_before: failures.append("production gateway PID identity changed during cron compatibility smoke v2")
    if prod_health_after != prod_health_before: failures.append(f"production health baseline changed: {prod_health_before} -> {prod_health_after}")
    if base.candidate_status_paths(candidate) != expected_paths: failures.append("candidate Git status changed during cron compatibility smoke v2")
    for rel, expected in base.EXPECTED_CANDIDATE_HASHES.items():
        if base.sha256(candidate / rel) != expected: failures.append(f"candidate source changed during cron compatibility smoke v2: {rel}")
    print(f"PRODUCTION_8642_HEALTH_AFTER={prod_health_after}")
    if prod_static_after == prod_static_before: print("PRODUCTION_STATIC_CONFIG_UNCHANGED=PASS")
    if prod_pid_after == prod_pid_before: print("PRODUCTION_GATEWAY_PID_IDENTITY_UNCHANGED=PASS")
    if base.candidate_status_paths(candidate) == expected_paths: print("CANDIDATE_GIT_STATUS_UNCHANGED=PASS")
    print("PRODUCTION_CRON_STORE_TOUCH_OBSERVER=scratch_home_enforced_plus_static_pid_health_postconditions")
    if p603_error is None: print("P603_RUNTIME_EXACT_REPAIR_PRESERVATION=PASS")
    if p604a_error is None: print("P604A_RUNTIME_DURABLE_ERROR_CLASS=PASS")
    if failures:
        for item in failures: print(f"CONTRACT_ERROR={item}")
        print("ISOLATED_CRON_COMPAT_CONTRACT=FAIL_UNRESOLVED_OR_FUNCTIONAL"); raise RuntimeError("\n".join(failures))
    print("ISOLATED_CRON_COMPAT_CONTRACT=PASS"); print("PRODUCTION_HERMES_MUTATED=false"); print("COMPANION_STATE_MUTATED=false"); print("PRODUCTION_RUNTIME_RESTARTED=false"); return 0

if __name__ == "__main__": raise SystemExit(main())
