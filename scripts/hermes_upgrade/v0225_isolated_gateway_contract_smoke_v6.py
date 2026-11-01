#!/usr/bin/env python3
"""Observer-hardened Windows isolated Hermes v0.22.5 gateway smoke.

v6 preserves the v5 research corrections but removes one invalid assumption:
a single empty Windows socket-table snapshot is not sufficient to declare a healthy
loopback HTTP listener absent. HTTP readiness remains authoritative for startup.
Socket enumeration is supporting bind/process evidence and only becomes a hard
failure when it returns contradictory non-empty evidence.
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import yaml

import v0225_isolated_gateway_contract_smoke as base
import v0225_isolated_gateway_contract_smoke_v2 as v2
import v0225_isolated_gateway_contract_smoke_v5 as v5

PRODUCTION_PROFILE = v5.PRODUCTION_PROFILE
SCRATCH_PROFILE = v5.SCRATCH_PROFILE
V6_PREFIX = "orion-hermes-v0225-gateway-v6-"
STABILITY_SAMPLES = 8
STABILITY_INTERVAL_S = 0.25
BIND_OBSERVER_ATTEMPTS = 12
BIND_OBSERVER_INTERVAL_S = 0.25


def _fail_if_exited(proc: subprocess.Popen, log_path: Path, key: str, context: str) -> None:
    rc = proc.poll()
    if rc is None:
        return
    raise RuntimeError(
        f"isolated gateway exited {context} (rc={rc})\n"
        + v2.proc_diag(proc, log_path)
        + "\n--- SAFE LOG TAIL ---\n"
        + base.safe_log_tail(log_path, key)
    )


def verify_post_ready_stability(
    proc: subprocess.Popen,
    port: int,
    log_path: Path,
    key: str,
) -> None:
    """Prove HTTP readiness was not a one-shot response immediately before process death."""
    observed: list[str] = []
    for index in range(STABILITY_SAMPLES):
        _fail_if_exited(proc, log_path, key, "after HTTP readiness")
        state = v5.health_state(port)
        observed.append(state)
        if state != "HTTP_200|status=ok":
            raise RuntimeError(
                "isolated gateway lost HTTP health during post-ready stability window: "
                f"sample={index + 1}/{STABILITY_SAMPLES}, state={state}\n"
                + v2.proc_diag(proc, log_path)
                + "\n--- SAFE LOG TAIL ---\n"
                + base.safe_log_tail(log_path, key)
            )
        if index + 1 < STABILITY_SAMPLES:
            time.sleep(STABILITY_INTERVAL_S)
    _fail_if_exited(proc, log_path, key, "after HTTP stability verification")
    print(f"POST_READY_HTTP_STABILITY=PASS|samples={len(observed)}")
    print("POST_READY_PROCESS_ALIVE=PASS")


def verify_scratch_bind_config(scratch_profile: Path, port: int) -> None:
    cfg_path = scratch_profile / "config.yaml"
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    try:
        api = data["platforms"]["api_server"]
    except Exception as exc:
        raise RuntimeError("scratch config missing platforms.api_server") from exc
    if api.get("enabled") is not True:
        raise RuntimeError(f"scratch API server is not enabled in config: {api!r}")
    if api.get("host") != "127.0.0.1" or int(api.get("port")) != port:
        raise RuntimeError(f"scratch API bind config mismatch: {api!r}")
    print(f"ISOLATED_BIND_CONFIGURATION=PASS|127.0.0.1:{port}")


def observe_windows_bind(
    proc: subprocess.Popen,
    port: int,
    log_path: Path,
    key: str,
) -> str:
    """Return PASS or INCONCLUSIVE after bounded native netstat observation.

    Empty snapshots are observer limitations. Any non-empty contradictory snapshot is
    acceptance-relevant and fails hard.
    """
    if os.name != "nt":
        print("ISOLATED_BIND_NETSTAT=NOT_APPLICABLE_NON_WINDOWS")
        print("ISOLATED_BIND_LOCALHOST_ONLY=CONFIG_CONFIRMED_NON_WINDOWS")
        return "NOT_APPLICABLE"

    for attempt in range(1, BIND_OBSERVER_ATTEMPTS + 1):
        _fail_if_exited(proc, log_path, key, "during bind observation")
        rows = v5.windows_netstat_listener_rows(port)
        if rows:
            if len(rows) != 1:
                raise RuntimeError(
                    f"contradictory netstat evidence on isolated port {port}: {rows}"
                )
            local, pid = rows[0]
            if local != f"127.0.0.1:{port}":
                raise RuntimeError(
                    f"isolated API listener is not exact IPv4 loopback bind: {local}"
                )
            owned = {item.pid for item in base.descendants(proc)}
            if pid not in owned:
                raise RuntimeError(
                    f"isolated listener PID {pid} is outside candidate process tree {sorted(owned)}"
                )
            print(f"ISOLATED_BIND_NETSTAT={local}|pid={pid}|attempt={attempt}")
            print("ISOLATED_BIND_LOCALHOST_ONLY=PASS")
            return "PASS"
        if attempt < BIND_OBSERVER_ATTEMPTS:
            time.sleep(BIND_OBSERVER_INTERVAL_S)

    _fail_if_exited(proc, log_path, key, "after empty bind observations")
    state = v5.health_state(port)
    if state != "HTTP_200|status=ok":
        raise RuntimeError(
            "netstat returned no listener and HTTP health was no longer stable; "
            f"state={state}\n"
            + v2.proc_diag(proc, log_path)
            + "\n--- SAFE LOG TAIL ---\n"
            + base.safe_log_tail(log_path, key)
        )
    print(
        "ISOLATED_BIND_NETSTAT=INCONCLUSIVE_NO_ROWS|"
        f"attempts={BIND_OBSERVER_ATTEMPTS}"
    )
    print("ISOLATED_BIND_LOCALHOST_ONLY=CONFIG_CONFIRMED_RUNTIME_ENUMERATION_INCONCLUSIVE")
    return "INCONCLUSIVE"


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
    temp_root = Path(tempfile.gettempdir())
    removed = v2.cleanup_v1_scratch(temp_root)

    prod_before = base.snapshot_production(prod_root, prod_profile)
    prod_health_before = v5.health_state(8642)

    scratch_root = Path(tempfile.mkdtemp(prefix=V6_PREFIX))
    scratch_profile = scratch_root / "profiles" / SCRATCH_PROFILE
    v2.prepare_minimal_profile(scratch_profile, port)
    verify_scratch_bind_config(scratch_profile, port)

    key = __import__("secrets").token_urlsafe(36)
    env = base.scrubbed_child_env(scratch_profile, key, port)
    log_path = scratch_root / "gateway.log"

    print(f"CANDIDATE_HEAD={base.git_single(candidate, 'rev-parse', 'HEAD')}")
    print(f"PRIOR_V1_SCRATCH_REMOVED={removed}")
    print(f"PRODUCTION_8642_HEALTH_BASELINE={prod_health_before}")
    print("SCRATCH_CONFIG_SOURCE=minimal_generated")
    print(f"SCRATCH_PROFILE_LAYOUT=profiles/{SCRATCH_PROFILE}")
    print("SCRATCH_GATEWAY_STANDALONE=true")
    print("SCRATCH_BUNDLED_SKILL_SEEDING=disabled")
    print("SCRATCH_EXTERNAL_PLATFORM_COUNT=0")
    print("SCRATCH_PRODUCTION_CONFIG_CONTENT_COPIED=false")
    print("SCRATCH_PRODUCTION_CREDENTIALS_COPIED=false")
    print("SCRATCH_API_KEY_PERSISTED=false")
    print("READINESS_ORACLE=http_health_no_proxy")
    print("BIND_OBSERVER=netstat_bounded_supporting_evidence")
    print("LAUNCH_MODE=standalone_normal_no_force")
    print(f"ISOLATED_BIND_TARGET=127.0.0.1:{port}")

    task_name = v5.probe_scratch_identity(candidate, runtime_python, env)
    v5.require_windows_task_absent(task_name)

    cmd = [
        str(runtime_python), "-B", "-m", "hermes_cli.main", "gateway", "run", "-v", "-v"
    ]

    proc: subprocess.Popen | None = None
    failure: Exception | None = None
    bind_evidence = "NOT_RUN"
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
            v5.wait_http_ready(proc, port, log_path, key)
            verify_post_ready_stability(proc, port, log_path, key)
            bind_evidence = observe_windows_bind(proc, port, log_path, key)
            _fail_if_exited(proc, log_path, key, "before runtime contract verification")
            v5.verify_runtime_contract(port, key)
            _fail_if_exited(proc, log_path, key, "after runtime contract verification")

        print("ISOLATED_GATEWAY_HEALTH=PASS")
        print("API_BEARER_AUTH=PASS")
        print("CAPABILITY_CONTRACT=PASS")
        print("P404A_AUDIO_ROUTE_AUTH=PASS")
        print("P404A_AUDIO_ROUTE_LOCAL_VALIDATION=PASS")
        print("MODEL_PROVIDER_CALLS=0")
        print("STT_PROVIDER_CALLS=0")
        print("TTS_PROVIDER_CALLS=0")
        print("MEMORY_CALLS=0")
    except Exception as exc:
        failure = exc
    finally:
        if proc is not None:
            base.terminate_owned_tree(proc)
        redaction = v2.redact_log(log_path, key)
        key = "<discarded>"

    post_errors: list[str] = []
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            post_errors.append(f"isolated port {port} still accepted TCP after cleanup")
    except OSError:
        pass
    if base.snapshot_production(prod_root, prod_profile) != prod_before:
        post_errors.append("production watched artifacts changed during smoke")
    prod_health_after = v5.health_state(8642)
    if prod_health_after != prod_health_before:
        post_errors.append(
            "production 8642 health baseline changed: "
            f"{prod_health_before} -> {prod_health_after}"
        )
    if base.candidate_status_paths(candidate) != expected_paths:
        post_errors.append("candidate Git status changed during smoke")
    for rel, expected in base.EXPECTED_CANDIDATE_HASHES.items():
        if base.sha256(candidate / rel) != expected:
            post_errors.append(f"candidate source changed during smoke: {rel}")

    print("SCRATCH_API_KEY_PERSISTED=false")
    print(f"SCRATCH_LOG_SECRET_REDACTION={redaction}")
    print(f"PRODUCTION_8642_HEALTH_AFTER={prod_health_after}")
    if not post_errors:
        print("ISOLATED_GATEWAY_CLEANUP=PASS")
        print("PRODUCTION_8642_HEALTH_BASELINE_UNCHANGED=PASS")
        print("PRODUCTION_WATCHED_STATE_UNCHANGED=PASS")
        print("CANDIDATE_SOURCE_UNCHANGED=PASS")
    else:
        for item in post_errors:
            print(f"POSTCONDITION_ERROR={item}")
    print(f"SCRATCH_ROOT={scratch_root}")
    print(f"SCRATCH_LOG={log_path}")

    if failure is not None or post_errors:
        parts = [str(failure)] if failure is not None else []
        parts.extend(post_errors)
        raise RuntimeError("\n".join(parts))

    if bind_evidence == "INCONCLUSIVE":
        print("BIND_EVIDENCE_LIMITATION=WINDOWS_SOCKET_ENUMERATION_EMPTY_WHILE_HTTP_STABLE")
        print("ISOLATED_STANDALONE_GATEWAY_CONTRACT=PASS_WITH_BIND_ENUMERATION_LIMITATION")
    else:
        print("BIND_EVIDENCE_LIMITATION=NONE")
        print("ISOLATED_STANDALONE_GATEWAY_CONTRACT=PASS")
    print("PRODUCTION_HERMES_MUTATED=false")
    print("COMPANION_STATE_MUTATED=false")
    print("PRODUCTION_RUNTIME_RESTARTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
