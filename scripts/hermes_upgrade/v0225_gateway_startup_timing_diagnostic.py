#!/usr/bin/env python3
"""Bounded startup-timing diagnostic for the qualified Hermes v0.22.5 candidate.

This is a diagnostic breakpoint, not a session/chat qualification. It intentionally performs
no Hermes cold-import identity probe before launch, no session CRUD, and no model/memory/STT/TTS
request. It measures whether the isolated standalone gateway becomes HTTP-ready, exits, or remains
alive without readiness, while separating immutable production configuration from volatile live
runtime metadata.
"""
from __future__ import annotations

import argparse
import os
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import psutil

import v0225_isolated_gateway_contract_smoke as base
import v0225_isolated_gateway_contract_smoke_v2 as v2
import v0225_isolated_gateway_contract_smoke_v5 as v5
import v0225_isolated_gateway_contract_smoke_v6 as v6

PRODUCTION_PROFILE = v5.PRODUCTION_PROFILE
SCRATCH_PROFILE = v5.SCRATCH_PROFILE
PREFIX = "orion-hermes-v0225-startup-diag-"
DIAGNOSTIC_TIMEOUT_S = 180.0
SAMPLE_INTERVAL_S = 10.0


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


def _volatile_snapshot(root: Path, profile_home: Path) -> dict[str, tuple]:
    paths = [
        root / "state.db",
        root / "gateway_state.json",
        profile_home / "state.db",
        profile_home / "gateway_state.json",
    ]
    return {str(path): base.stat_signature(path) for path in paths}


def _changed_paths(before: dict, after: dict) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _sample(proc: subprocess.Popen, log_path: Path, started: float, port: int) -> None:
    owned = base.descendants(proc)
    rss = 0
    threads = 0
    cpu = 0.0
    alive = 0
    pids: list[int] = []
    for item in owned:
        try:
            if not item.is_running():
                continue
            alive += 1
            pids.append(item.pid)
            rss += int(item.memory_info().rss)
            threads += int(item.num_threads())
            times = item.cpu_times()
            cpu += float(times.user) + float(times.system)
        except psutil.Error:
            continue
    try:
        log_bytes = int(log_path.stat().st_size)
    except OSError:
        log_bytes = -1
    elapsed = time.monotonic() - started
    print(
        "STARTUP_SAMPLE="
        f"elapsed_s={elapsed:.1f}|health={v5.health_state(port)}|"
        f"root_poll={proc.poll()}|alive_processes={alive}|pids={','.join(map(str, sorted(pids)))}|"
        f"threads={threads}|rss_bytes={rss}|cpu_seconds={cpu:.3f}|log_bytes={log_bytes}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--production-hermes-root", required=True)
    ap.add_argument("--candidate-root", required=True)
    ap.add_argument("--runtime-python", required=True)
    ap.add_argument("--port", type=int, default=base.DEFAULT_PORT)
    args = ap.parse_args()

    prod_root = Path(args.production_hermes_root).resolve()
    prod_profile = prod_root / "profiles" / PRODUCTION_PROFILE
    candidate = Path(args.candidate_root).resolve()
    runtime_python = Path(args.runtime_python).resolve()
    port = int(args.port)

    if not prod_root.is_dir() or not prod_profile.is_dir():
        raise RuntimeError("production Hermes root or COMPANION profile is missing")
    if not candidate.is_dir() or not (candidate / ".git").exists():
        raise RuntimeError("candidate root is not a Git checkout")
    if not runtime_python.is_file():
        raise RuntimeError("isolated runtime Python is missing")
    if not base.tcp_port_free("127.0.0.1", port):
        raise RuntimeError(f"isolated port {port} is not free")

    expected_paths = v2.verify_candidate(candidate)
    prod_static_before = _static_snapshot(prod_root, prod_profile)
    prod_pid_before = _pid_snapshot(prod_root, prod_profile)
    prod_volatile_before = _volatile_snapshot(prod_root, prod_profile)
    prod_health_before = v5.health_state(8642)

    scratch_root = Path(tempfile.mkdtemp(prefix=PREFIX))
    scratch_profile = scratch_root / "profiles" / SCRATCH_PROFILE
    v2.prepare_minimal_profile(scratch_profile, port)
    v6.verify_scratch_bind_config(scratch_profile, port)

    task_name = f"Hermes_Gateway_{SCRATCH_PROFILE}" if os.name == "nt" else None
    v5.require_windows_task_absent(task_name)

    key = secrets.token_urlsafe(36)
    env = base.scrubbed_child_env(scratch_profile, key, port)
    log_path = scratch_root / "gateway.log"

    print(f"CANDIDATE_HEAD={base.git_single(candidate, 'rev-parse', 'HEAD')}")
    print(f"PRODUCTION_8642_HEALTH_BASELINE={prod_health_before}")
    print("DIAGNOSTIC_SCOPE=startup_timing_only")
    print("PRELAUNCH_HERMES_IMPORT_PROBE=false")
    print("SCRATCH_CONFIG_SOURCE=minimal_generated")
    print(f"SCRATCH_PROFILE_LAYOUT=profiles/{SCRATCH_PROFILE}")
    print("SCRATCH_GATEWAY_STANDALONE=true")
    if task_name:
        print(f"SCRATCH_WINDOWS_TASK_NAME={task_name}")
    print("CHAT_TURN_SUBMITTED=false")
    print("SESSION_RESOURCE_MUTATION=false")
    print("MODEL_PROVIDER_CALLS=0")
    print("MEMORY_CALLS=0")
    print("STT_PROVIDER_CALLS=0")
    print("TTS_PROVIDER_CALLS=0")
    print(f"STARTUP_DIAGNOSTIC_DEADLINE_S={DIAGNOSTIC_TIMEOUT_S:.0f}")

    cmd = [
        str(runtime_python), "-B", "-m", "hermes_cli.main", "gateway", "run", "-v", "-v"
    ]
    proc: subprocess.Popen | None = None
    ready_elapsed: float | None = None
    failure: str | None = None
    started = time.monotonic()
    next_sample = started

    try:
        with log_path.open("wb") as log:
            proc = subprocess.Popen(
                cmd,
                cwd=str(candidate),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            deadline = started + DIAGNOSTIC_TIMEOUT_S
            while time.monotonic() < deadline:
                rc = proc.poll()
                if rc is not None:
                    classification = "WATCHDOG_EXIT_75" if rc == 75 else f"PROCESS_EXIT_{rc}"
                    failure = f"candidate exited before HTTP readiness: {classification}"
                    print(f"COLD_START_CLASSIFICATION={classification}")
                    break
                state = v5.health_state(port)
                now = time.monotonic()
                if state == "HTTP_200|status=ok":
                    ready_elapsed = now - started
                    print(f"COLD_START_HTTP_READY=PASS|elapsed_s={ready_elapsed:.3f}")
                    print(
                        "COLD_START_CLASSIFICATION="
                        + ("READY_WITHIN_LEGACY_90S" if ready_elapsed <= 90.0 else "READY_AFTER_LEGACY_90S")
                    )
                    v6.verify_post_ready_stability(proc, port, log_path, key)
                    break
                if now >= next_sample:
                    _sample(proc, log_path, started, port)
                    next_sample = now + SAMPLE_INTERVAL_S
                time.sleep(0.25)
            else:
                failure = (
                    f"candidate remained alive without HTTP readiness for {DIAGNOSTIC_TIMEOUT_S:.0f}s"
                )
                print("COLD_START_HTTP_READY=FAIL_TIMEOUT")
                print("COLD_START_CLASSIFICATION=ALIVE_NO_HTTP_BY_DIAGNOSTIC_DEADLINE")
                _sample(proc, log_path, started, port)

            if ready_elapsed is None:
                print("--- SAFE LOG TAIL ---")
                print(base.safe_log_tail(log_path, key, lines=120))
    finally:
        if proc is not None:
            base.terminate_owned_tree(proc)
        redaction = v2.redact_log(log_path, key)
        key = "<discarded>"

    prod_static_after = _static_snapshot(prod_root, prod_profile)
    prod_pid_after = _pid_snapshot(prod_root, prod_profile)
    prod_volatile_after = _volatile_snapshot(prod_root, prod_profile)
    prod_health_after = v5.health_state(8642)

    post_errors: list[str] = []
    static_changed = _changed_paths(prod_static_before, prod_static_after)
    pid_changed = _changed_paths(prod_pid_before, prod_pid_after)
    volatile_changed = _changed_paths(prod_volatile_before, prod_volatile_after)

    if static_changed:
        post_errors.append("production static config changed: " + ", ".join(static_changed))
    if pid_changed:
        post_errors.append("production gateway PID identity file changed: " + ", ".join(pid_changed))
    if prod_health_after != prod_health_before:
        post_errors.append(
            "production health baseline changed: "
            f"{prod_health_before} -> {prod_health_after}"
        )
    if base.candidate_status_paths(candidate) != expected_paths:
        post_errors.append("candidate Git status changed during startup diagnostic")
    for rel, expected in base.EXPECTED_CANDIDATE_HASHES.items():
        if base.sha256(candidate / rel) != expected:
            post_errors.append(f"candidate source changed during startup diagnostic: {rel}")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            post_errors.append(f"isolated port {port} still accepted TCP after cleanup")
    except OSError:
        pass

    print(f"SCRATCH_LOG_SECRET_REDACTION={redaction}")
    print(f"PRODUCTION_8642_HEALTH_AFTER={prod_health_after}")
    print(
        "PRODUCTION_VOLATILE_RUNTIME_CHANGED="
        + ("NONE" if not volatile_changed else ";".join(volatile_changed))
    )
    print("PRODUCTION_VOLATILE_RUNTIME_CHANGE_IS_MUTATION_ORACLE=false")
    if not static_changed:
        print("PRODUCTION_STATIC_CONFIG_UNCHANGED=PASS")
    if not pid_changed:
        print("PRODUCTION_GATEWAY_PID_IDENTITY_UNCHANGED=PASS")
    if base.candidate_status_paths(candidate) == expected_paths:
        print("CANDIDATE_GIT_STATUS_UNCHANGED=PASS")
    print(f"SCRATCH_ROOT={scratch_root}")
    print(f"SCRATCH_LOG={log_path}")

    if failure is not None or post_errors:
        parts = [failure] if failure is not None else []
        parts.extend(post_errors)
        raise RuntimeError("\n".join(parts))

    print("STARTUP_TIMING_DIAGNOSTIC=PASS")
    print("PRODUCTION_HERMES_MUTATED=false")
    print("COMPANION_STATIC_CONFIG_MUTATED=false")
    print("PRODUCTION_RUNTIME_RESTARTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
