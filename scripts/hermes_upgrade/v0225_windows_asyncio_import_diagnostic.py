#!/usr/bin/env python3
"""Read-only Windows import diagnostic for Hermes v0.22.5 qualification.

Discriminates interpreter/environment failures from Hermes cron import-order behavior.
No gateway, cron job, provider, model, memory, STT, or TTS call is made.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

import v0225_isolated_cron_compat_contract_smoke as v1
import v0225_isolated_gateway_contract_smoke as base
import v0225_isolated_gateway_contract_smoke_v2 as gateway_v2
import v0225_isolated_gateway_contract_smoke_v5 as v5

PRODUCTION_PROFILE = v5.PRODUCTION_PROFILE
PREFIX = "orion-hermes-v0225-asyncio-import-diag-"
PROBE_TIMEOUT_S = 30.0

_SENSITIVE_NAME = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API.?KEY|CREDENTIAL|COOKIE|"
    r"OPENAI|ANTHROPIC|NOUS|DISCORD|GITHUB|^GH_|^AWS_|^AZURE|"
    r"GOOGLE|GEMINI|MISTRAL|GROQ|OPENROUTER|HUGGINGFACE|^HF_)",
    re.IGNORECASE,
)

PROBE_CODE = r'''
from __future__ import annotations
import inspect
import os
import sys

label = os.environ["ORION_DIAG_LABEL"]
target = os.environ["ORION_DIAG_TARGET"]
preimport = os.environ.get("ORION_DIAG_PREIMPORT_ASYNCIO") == "1"

print(f"ORION_DIAG_BEGIN={label}", flush=True)
print(f"ORION_DIAG_SYS_VERSION={sys.version.split()[0]}", flush=True)
print(f"ORION_DIAG_SYS_EXECUTABLE={sys.executable}", flush=True)
print(f"ORION_DIAG_SYS_PREFIX={sys.prefix}", flush=True)
print(f"ORION_DIAG_SYS_BASE_PREFIX={sys.base_prefix}", flush=True)
for name in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", "PYTHONSAFEPATH", "PYTHONNOUSERSITE"):
    print(f"ORION_DIAG_ENV_PRESENT_{name}={'true' if name in os.environ else 'false'}", flush=True)
print(f"ORION_DIAG_STARTUP_MODULE_sitecustomize={'true' if 'sitecustomize' in sys.modules else 'false'}", flush=True)
print(f"ORION_DIAG_STARTUP_MODULE_usercustomize={'true' if 'usercustomize' in sys.modules else 'false'}", flush=True)
print(f"ORION_DIAG_STARTUP_MODULE_hermes_bootstrap={'true' if 'hermes_bootstrap' in sys.modules else 'false'}", flush=True)

import subprocess
print(
    "ORION_DIAG_SUBPROCESS_POPEN="
    f"isclass:{str(inspect.isclass(subprocess.Popen)).lower()}|"
    f"type:{type(subprocess.Popen).__name__}|"
    f"module:{getattr(subprocess.Popen, '__module__', '')}|"
    f"qualname:{getattr(subprocess.Popen, '__qualname__', '')}",
    flush=True,
)

if preimport:
    print("ORION_DIAG_PREIMPORT_ASYNCIO_BEGIN", flush=True)
    import asyncio
    print(f"ORION_DIAG_PREIMPORT_ASYNCIO_PASS={asyncio.__file__}", flush=True)

if target == "asyncio":
    print("ORION_DIAG_TARGET_ASYNCIO_BEGIN", flush=True)
    import asyncio
    print(f"ORION_DIAG_TARGET_ASYNCIO_PASS={asyncio.__file__}", flush=True)
elif target == "cron_jobs":
    print("ORION_DIAG_TARGET_CRON_JOBS_BEGIN", flush=True)
    from cron import jobs as jobs_mod
    print(f"ORION_DIAG_TARGET_CRON_JOBS_PASS={jobs_mod.__file__}", flush=True)
else:
    raise RuntimeError(f"unknown diagnostic target: {target}")

print(f"ORION_DIAG_RESULT={label}|PASS", flush=True)
'''


def _sanitized_inherited_env(scratch_home: Path) -> dict[str, str]:
    env = {
        name: value
        for name, value in os.environ.items()
        if not _SENSITIVE_NAME.search(name)
    }
    env.update(
        {
            "HERMES_HOME": str(scratch_home),
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
            "NO_COLOR": "1",
        }
    )
    return env


def _probe_env(kind: str, scratch_home: Path) -> dict[str, str]:
    if kind == "scrubbed":
        return v1._child_env(scratch_home)
    if kind == "sanitized_inherited":
        return _sanitized_inherited_env(scratch_home)
    raise ValueError(kind)


def _run_probe(
    *,
    label: str,
    env_kind: str,
    target: str,
    preimport_asyncio: bool,
    candidate: Path,
    runtime_python: Path,
    scratch_home: Path,
) -> tuple[bool, str]:
    env = _probe_env(env_kind, scratch_home)
    env.update(
        {
            "ORION_DIAG_LABEL": label,
            "ORION_DIAG_TARGET": target,
            "ORION_DIAG_PREIMPORT_ASYNCIO": "1" if preimport_asyncio else "0",
        }
    )
    started = time.monotonic()
    proc = subprocess.Popen(
        [str(runtime_python), "-B", "-c", PROBE_CODE],
        cwd=str(candidate),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        stdout, stderr = proc.communicate(timeout=PROBE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        elapsed = time.monotonic() - started
        for line in (stdout or "").splitlines():
            if line.startswith("ORION_DIAG_"):
                print(line)
        if stderr and stderr.strip():
            print(f"ORION_DIAG_STDERR_BEGIN={label}")
            print(stderr.rstrip())
            print(f"ORION_DIAG_STDERR_END={label}")
        print(f"ORION_DIAG_PROBE={label}|TIMEOUT|elapsed_s={elapsed:.3f}")
        return False, "timeout"

    elapsed = time.monotonic() - started
    for line in (stdout or "").splitlines():
        if line.startswith("ORION_DIAG_"):
            print(line)
    if stderr and stderr.strip():
        print(f"ORION_DIAG_STDERR_BEGIN={label}")
        print(stderr.rstrip())
        print(f"ORION_DIAG_STDERR_END={label}")
    if proc.returncode == 0:
        print(f"ORION_DIAG_PROBE={label}|PASS|elapsed_s={elapsed:.3f}")
        return True, "pass"
    print(f"ORION_DIAG_PROBE={label}|FAIL|rc={proc.returncode}|elapsed_s={elapsed:.3f}")
    return False, "failure"


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

    expected_paths = gateway_v2.verify_candidate(candidate)
    prod_static_before = v1._static_snapshot(prod_root, prod_profile)
    prod_pid_before = v1._pid_snapshot(prod_root, prod_profile)
    prod_health_before = v5.health_state(8642)
    scratch_root = Path(tempfile.mkdtemp(prefix=PREFIX)).resolve()

    print(f"CANDIDATE_HEAD={base.git_single(candidate, 'rev-parse', 'HEAD')}")
    print(f"PRODUCTION_8642_HEALTH_BASELINE={prod_health_before}")
    print("DIAGNOSTIC_SCOPE=windows_asyncio_cron_import_boundary")
    print(f"SCRATCH_ROOT={scratch_root}")
    print(f"PROBE_TIMEOUT_S={PROBE_TIMEOUT_S:.0f}")
    print("GATEWAY_LAUNCHED=false")
    print("PRODUCTION_CRON_JOB_EXECUTED=false")
    print("MODEL_PROVIDER_CALLS=0")
    print("MEMORY_CALLS=0")
    print("STT_PROVIDER_CALLS=0")
    print("TTS_PROVIDER_CALLS=0")
    print("ENVIRONMENT_SECRET_VALUES_PRINTED=false")

    specs = [
        ("ASYNCIO_SCRUBBED", "scrubbed", "asyncio", False),
        ("ASYNCIO_SANITIZED_INHERITED", "sanitized_inherited", "asyncio", False),
        ("CRON_JOBS_SCRUBBED", "scrubbed", "cron_jobs", False),
        ("CRON_JOBS_SANITIZED_INHERITED", "sanitized_inherited", "cron_jobs", False),
        ("CRON_JOBS_PREIMPORT_ASYNCIO_SCRUBBED", "scrubbed", "cron_jobs", True),
        ("CRON_JOBS_PREIMPORT_ASYNCIO_SANITIZED_INHERITED", "sanitized_inherited", "cron_jobs", True),
    ]

    outcomes: dict[str, bool] = {}
    prod_static_after = prod_static_before
    prod_pid_after = prod_pid_before
    prod_health_after = prod_health_before
    candidate_paths_after = expected_paths
    hash_unchanged = True
    try:
        for label, env_kind, target, preimport in specs:
            home = scratch_root / label.lower()
            home.mkdir(parents=True, exist_ok=True)
            ok, _ = _run_probe(
                label=label,
                env_kind=env_kind,
                target=target,
                preimport_asyncio=preimport,
                candidate=candidate,
                runtime_python=runtime_python,
                scratch_home=home,
            )
            outcomes[label] = ok
    finally:
        prod_static_after = v1._static_snapshot(prod_root, prod_profile)
        prod_pid_after = v1._pid_snapshot(prod_root, prod_profile)
        prod_health_after = v5.health_state(8642)
        candidate_paths_after = base.candidate_status_paths(candidate)

        print(f"PRODUCTION_8642_HEALTH_AFTER={prod_health_after}")
        print(f"PRODUCTION_STATIC_CONFIG_UNCHANGED={'PASS' if prod_static_after == prod_static_before else 'FAIL'}")
        print(f"PRODUCTION_GATEWAY_PID_IDENTITY_UNCHANGED={'PASS' if prod_pid_after == prod_pid_before else 'FAIL'}")
        print(f"CANDIDATE_GIT_STATUS_UNCHANGED={'PASS' if candidate_paths_after == expected_paths else 'FAIL'}")
        hash_unchanged = all(
            base.sha256(candidate / rel) == expected
            for rel, expected in base.EXPECTED_CANDIDATE_HASHES.items()
        )
        print(f"CANDIDATE_EXPECTED_HASHES_UNCHANGED={'PASS' if hash_unchanged else 'FAIL'}")

    post_ok = (
        prod_static_after == prod_static_before
        and prod_pid_after == prod_pid_before
        and prod_health_after == prod_health_before
        and candidate_paths_after == expected_paths
        and hash_unchanged
    )
    if not post_ok:
        print("WINDOWS_IMPORT_DIAGNOSTIC=FAIL_POSTCONDITION")
        return 2

    direct_scrub = outcomes.get("ASYNCIO_SCRUBBED", False)
    direct_inherited = outcomes.get("ASYNCIO_SANITIZED_INHERITED", False)
    cron_scrub = outcomes.get("CRON_JOBS_SCRUBBED", False)
    cron_inherited = outcomes.get("CRON_JOBS_SANITIZED_INHERITED", False)
    pre_scrub = outcomes.get("CRON_JOBS_PREIMPORT_ASYNCIO_SCRUBBED", False)
    pre_inherited = outcomes.get("CRON_JOBS_PREIMPORT_ASYNCIO_SANITIZED_INHERITED", False)

    if direct_inherited and not direct_scrub:
        classification = "SCRUBBED_ENVIRONMENT_BREAKS_DIRECT_ASYNCIO"
    elif not direct_inherited and not direct_scrub:
        classification = "RUNTIME_DIRECT_ASYNCIO_FAILURE_ACROSS_ENVIRONMENTS"
    elif direct_scrub and direct_inherited and (not cron_scrub or not cron_inherited) and (pre_scrub or pre_inherited):
        classification = "CRON_IMPORT_ORDER_INTERACTION_ASYNCIO_PREIMPORT_MITIGATES"
    elif direct_scrub and direct_inherited and not cron_scrub and not cron_inherited:
        classification = "CRON_IMPORT_PATH_FAILURE_NOT_DIRECT_ASYNCIO"
    elif direct_scrub and direct_inherited and cron_inherited and not cron_scrub:
        classification = "SCRUBBED_ENVIRONMENT_BREAKS_CRON_IMPORT"
    elif all(outcomes.values()):
        classification = "IMPORT_MATRIX_ALL_PASS_INTERMITTENT_PRIOR_FAILURE"
    else:
        classification = "MIXED_IMPORT_RESULT_REQUIRES_REVIEW"

    print(f"WINDOWS_IMPORT_DIAGNOSTIC_CLASSIFICATION={classification}")
    print("PRODUCTION_HERMES_MUTATED=false")
    print("COMPANION_STATE_MUTATED=false")
    print("PRODUCTION_RUNTIME_RESTARTED=false")
    print("WINDOWS_IMPORT_DIAGNOSTIC=PASS_OBSERVATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
