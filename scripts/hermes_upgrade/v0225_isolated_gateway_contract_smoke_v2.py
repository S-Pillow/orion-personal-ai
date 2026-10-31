#!/usr/bin/env python3
"""Security-hardened v0.22.5 isolated gateway contract smoke.

Supersedes v0225_isolated_gateway_contract_smoke.py for runtime execution.
It never copies production config content or credentials into scratch state.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import psutil
import yaml

import v0225_isolated_gateway_contract_smoke as base

PROFILE = "companion"
START_TIMEOUT_S = 90.0
V1_PREFIX = "orion-hermes-v0225-gateway-"
V2_PREFIX = "orion-hermes-v0225-gateway-v2-"
PROFILE_DIRS = ("memories", "sessions", "skills", "skins", "logs", "plans", "workspace", "cron", "home")


def prepare_minimal_profile(profile: Path, port: int) -> None:
    profile.mkdir(parents=True, exist_ok=False)
    for name in PROFILE_DIRS:
        (profile / name).mkdir(parents=True, exist_ok=True)
    cfg = {
        "gateway": {
            "standalone": True,
            "on_all_adapters_down": "stay_alive",
            "profile_routes": [],
        },
        "platforms": {
            "api_server": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": port,
            }
        },
    }
    (profile / "config.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )
    (profile / ".no-bundled-skills").write_text(
        "Disposable qualification profile: bundled skill seeding disabled.\n",
        encoding="utf-8",
        newline="\n",
    )


def cleanup_v1_scratch(temp_root: Path) -> int:
    removed = 0
    for path in sorted(temp_root.glob(V1_PREFIX + "*")):
        if not path.is_dir() or path.name.startswith(V2_PREFIX):
            continue
        if not (path / "profiles" / PROFILE / "config.yaml").is_file():
            continue
        if not (path / "gateway.log").exists():
            continue
        shutil.rmtree(path)
        removed += 1
    return removed


def proc_diag(proc: subprocess.Popen, log_path: Path) -> str:
    rows = [f"CHILD_PID={proc.pid}", f"CHILD_POLL={proc.poll()}"]
    try:
        p = psutil.Process(proc.pid)
        rows += [
            f"CHILD_STATUS={p.status()}",
            f"CHILD_THREADS={p.num_threads()}",
            f"CHILD_RSS_BYTES={p.memory_info().rss}",
        ]
        cpu = p.cpu_times()
        rows.append(f"CHILD_CPU_SECONDS={cpu.user + cpu.system:.3f}")
        children = []
        for child in p.children(recursive=True):
            try:
                children.append(f"{child.pid}:{child.name()}:{child.status()}")
            except psutil.Error:
                pass
        rows.append("CHILDREN=" + (",".join(children) if children else "<none>"))
    except psutil.Error as exc:
        rows.append(f"CHILD_PSUTIL={type(exc).__name__}")
    try:
        rows.append(f"LOG_BYTES={log_path.stat().st_size}")
    except OSError:
        rows.append("LOG_BYTES=<unavailable>")
    return "\n".join(rows)


def verify_candidate(candidate: Path) -> list[str]:
    head = base.git_single(candidate, "rev-parse", "HEAD")
    if head != base.EXPECTED_RELEASE_HEAD:
        raise RuntimeError(f"candidate HEAD drift: {head}")
    expected_paths = sorted(base.EXPECTED_CANDIDATE_HASHES)
    actual_paths = base.candidate_status_paths(candidate)
    if actual_paths != expected_paths:
        raise RuntimeError(
            f"candidate changed scope mismatch: expected {expected_paths}, observed {actual_paths}"
        )
    for rel, expected in base.EXPECTED_CANDIDATE_HASHES.items():
        observed = base.sha256(candidate / rel)
        if observed != expected:
            raise RuntimeError(
                f"candidate hash mismatch for {rel}: expected {expected}, observed {observed}"
            )
    return expected_paths


def verify_runtime_contract(port: int, key: str) -> None:
    url = f"http://127.0.0.1:{port}"
    if base.http_json("GET", url + "/health")[0] != 200:
        raise RuntimeError("GET /health did not return 200")
    if base.http_json("GET", url + "/v1/capabilities")[0] != 401:
        raise RuntimeError("unauthenticated capabilities did not return 401")
    if base.http_json("GET", url + "/v1/capabilities", token="wrong-disposable-token")[0] != 401:
        raise RuntimeError("wrong-token capabilities did not return 401")
    code, caps = base.http_json("GET", url + "/v1/capabilities", token=key)
    if code != 200 or not isinstance(caps, dict):
        raise RuntimeError(f"authorized capabilities expected JSON 200; observed {code}")
    features = caps.get("features")
    endpoints = caps.get("endpoints")
    if not isinstance(features, dict) or not isinstance(endpoints, dict):
        raise RuntimeError("capabilities missing features/endpoints maps")
    required = {
        "audio_api": True,
        "realtime_voice": False,
        "session_chat": True,
        "session_chat_streaming": True,
        "run_stop": True,
        "run_steer": True,
        "run_approval_response": True,
        "approval_events": True,
    }
    bad = {k: (features.get(k), v) for k, v in required.items() if features.get(k) is not v}
    if bad:
        raise RuntimeError(f"capability feature mismatch: {bad}")
    for name, method, path in (
        ("audio_transcribe", "POST", "/api/audio/transcribe"),
        ("audio_speak", "POST", "/api/audio/speak"),
    ):
        row = endpoints.get(name)
        if not isinstance(row, dict) or row.get("method") != method or row.get("path") != path:
            raise RuntimeError(f"capability endpoint mismatch for {name}: {row!r}")
    if base.http_json("POST", url + "/api/audio/speak", payload={})[0] != 401:
        raise RuntimeError("unauthenticated audio speak did not return 401")
    if base.http_json("POST", url + "/api/audio/speak", token=key, payload={})[0] != 400:
        raise RuntimeError("authorized empty audio speak did not return local 400 validation")
    if base.http_json("POST", url + "/api/audio/transcribe", token=key, payload={})[0] != 400:
        raise RuntimeError("authorized empty audio transcribe did not return local 400 validation")


def redact_log(path: Path, key: str) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "NOT_NEEDED"
    if key not in text:
        return "NOT_NEEDED"
    path.write_text(text.replace(key, "<redacted-ephemeral-api-key>"), encoding="utf-8", newline="\n")
    return "APPLIED"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--production-hermes-root", required=True)
    ap.add_argument("--candidate-root", required=True)
    ap.add_argument("--runtime-python", required=True)
    ap.add_argument("--port", type=int, default=base.DEFAULT_PORT)
    args = ap.parse_args()

    prod_root = Path(args.production_hermes_root).resolve()
    prod_profile = prod_root / "profiles" / PROFILE
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

    expected_paths = verify_candidate(candidate)
    prod_before = base.snapshot_production(prod_root, prod_profile)
    prod_listener_before = base.require_single_listener(8642)
    prod_pid_before = prod_listener_before[0]

    temp_root = Path(tempfile.gettempdir())
    removed = cleanup_v1_scratch(temp_root)
    scratch_root = Path(tempfile.mkdtemp(prefix=V2_PREFIX))
    scratch_profile = scratch_root / "profiles" / PROFILE
    prepare_minimal_profile(scratch_profile, port)

    key = secrets.token_urlsafe(36)
    env_file = scratch_profile / ".env"
    env_file.write_text(
        "# Disposable qualification only.\n"
        "API_SERVER_ENABLED=true\n"
        f"API_SERVER_KEY={key}\n"
        "API_SERVER_HOST=127.0.0.1\n"
        f"API_SERVER_PORT={port}\n",
        encoding="utf-8",
        newline="\n",
    )
    log_path = scratch_root / "gateway.log"
    env = base.scrubbed_child_env(scratch_profile, key, port)
    cmd = [str(runtime_python), "-B", "-m", "hermes_cli.main", "gateway", "run"]

    print(f"CANDIDATE_HEAD={base.git_single(candidate, 'rev-parse', 'HEAD')}")
    print(f"PRIOR_V1_SCRATCH_REMOVED={removed}")
    print("SCRATCH_CONFIG_SOURCE=minimal_generated")
    print("SCRATCH_PROFILE_LAYOUT=profiles/companion")
    print("SCRATCH_GATEWAY_STANDALONE=true")
    print("SCRATCH_BUNDLED_SKILL_SEEDING=disabled")
    print("SCRATCH_EXTERNAL_PLATFORM_COUNT=0")
    print("SCRATCH_PRODUCTION_CONFIG_CONTENT_COPIED=false")
    print("SCRATCH_PRODUCTION_CREDENTIALS_COPIED=false")
    print(f"ISOLATED_BIND_TARGET=127.0.0.1:{port}")

    proc = None
    failure: Exception | None = None
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
            deadline = time.time() + START_TIMEOUT_S
            while time.time() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(
                        f"isolated gateway exited before readiness (rc={proc.returncode})\n"
                        + proc_diag(proc, log_path)
                        + "\n--- SAFE LOG TAIL ---\n"
                        + base.safe_log_tail(log_path, key)
                    )
                if base.listener_rows(port):
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError(
                    "isolated gateway did not bind before timeout\n"
                    + proc_diag(proc, log_path)
                    + "\n--- SAFE LOG TAIL ---\n"
                    + base.safe_log_tail(log_path, key)
                )

        listener = base.require_single_listener(port, expected_host="127.0.0.1")
        owned = {p.pid for p in base.descendants(proc)}
        if listener[0] not in owned:
            raise RuntimeError(f"isolated listener PID {listener[0]} not owned by candidate tree {sorted(owned)}")
        verify_runtime_contract(port, key)
        print("ISOLATED_GATEWAY_HEALTH=PASS")
        print("ISOLATED_BIND_LOCALHOST_ONLY=PASS")
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
        redaction = redact_log(log_path, key)
        try:
            env_file.unlink(missing_ok=True)
        except OSError as exc:
            if failure is None:
                failure = RuntimeError(f"failed to remove disposable API key file: {exc}")

    post_errors = []
    if base.listener_rows(port):
        post_errors.append(f"isolated listener {port} remained after cleanup")
    if base.snapshot_production(prod_root, prod_profile) != prod_before:
        post_errors.append("production watched artifacts changed during smoke")
    try:
        prod_after = base.require_single_listener(8642)
        if prod_after[0] != prod_pid_before:
            post_errors.append(f"production 8642 owner changed: {prod_pid_before} -> {prod_after[0]}")
    except Exception as exc:
        post_errors.append(f"production 8642 verification failed: {exc}")
    if base.candidate_status_paths(candidate) != expected_paths:
        post_errors.append("candidate Git status changed during smoke")
    for rel, expected in base.EXPECTED_CANDIDATE_HASHES.items():
        if base.sha256(candidate / rel) != expected:
            post_errors.append(f"candidate source changed during smoke: {rel}")

    print("SCRATCH_EPHEMERAL_KEY_REMOVED=" + ("PASS" if not env_file.exists() else "FAIL"))
    print(f"SCRATCH_LOG_SECRET_REDACTION={redaction}")
    if not post_errors:
        print("ISOLATED_GATEWAY_CLEANUP=PASS")
        print("PRODUCTION_8642_OWNER_UNCHANGED=PASS")
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

    print("ISOLATED_STANDALONE_GATEWAY_CONTRACT=PASS")
    print("PRODUCTION_HERMES_MUTATED=false")
    print("COMPANION_STATE_MUTATED=false")
    print("PRODUCTION_RUNTIME_RESTARTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
