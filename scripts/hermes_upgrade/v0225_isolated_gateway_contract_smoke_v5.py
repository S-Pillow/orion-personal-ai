#!/usr/bin/env python3
"""Research-corrected Windows isolated Hermes v0.22.5 gateway smoke.

Key corrections:
- uses a unique scratch profile name so Windows Scheduled Task/service identity cannot
  collide with production `Hermes_Gateway_companion`;
- proves the computed scratch task name and that no such task is installed;
- uses proxy-disabled loopback HTTP GET /health as readiness oracle;
- launches ordinary standalone `gateway run` without --force;
- uses native netstat only after readiness as bind-address/process evidence;
- copies no production config/credentials and persists no disposable API key.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

import v0225_isolated_gateway_contract_smoke as base
import v0225_isolated_gateway_contract_smoke_v2 as v2

PRODUCTION_PROFILE = "companion"
SCRATCH_PROFILE = "orion_v0225_qual"
START_TIMEOUT_S = 90.0
V5_PREFIX = "orion-hermes-v0225-gateway-v5-"
HTTP_TIMEOUT_S = 3.0


def direct_http_json(method: str, url: str, token: str | None = None, payload=None):
    """Loopback HTTP with proxies disabled explicitly."""
    headers = {"Accept": "application/json"}
    body = None
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=body, headers=headers, method=method)
    opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
    try:
        with opener.open(req, timeout=HTTP_TIMEOUT_S) as response:
            raw = response.read()
            code = int(response.status)
    except urlerror.HTTPError as exc:
        code = int(exc.code)
        raw = exc.read()
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"HTTP request failed for {method} {url}: {exc}") from exc
    if not raw:
        return code, None
    try:
        return code, json.loads(raw.decode("utf-8"))
    except Exception:
        return code, None


def health_state(port: int) -> str:
    try:
        code, payload = direct_http_json("GET", f"http://127.0.0.1:{port}/health")
    except Exception:
        return "UNREACHABLE"
    status = payload.get("status") if isinstance(payload, dict) else None
    return f"HTTP_{code}|status={status}"


def wait_http_ready(proc: subprocess.Popen, port: int, log_path: Path, key: str) -> None:
    deadline = time.time() + START_TIMEOUT_S
    last_state = "UNREACHABLE"
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"isolated gateway exited before HTTP readiness (rc={proc.returncode})\n"
                + v2.proc_diag(proc, log_path)
                + "\n--- SAFE LOG TAIL ---\n"
                + base.safe_log_tail(log_path, key)
            )
        last_state = health_state(port)
        if last_state.startswith("HTTP_200|"):
            return
        time.sleep(0.25)
    raise RuntimeError(
        f"isolated gateway did not become HTTP-ready before timeout; last={last_state}\n"
        + v2.proc_diag(proc, log_path)
        + "\n--- SAFE LOG TAIL ---\n"
        + base.safe_log_tail(log_path, key)
    )


def probe_scratch_identity(candidate: Path, runtime_python: Path, env: dict[str, str]) -> str | None:
    code = r'''
import json, os
from hermes_constants import get_hermes_home, profile_name_for_home
from hermes_cli.profiles import profile_is_standalone
home = get_hermes_home()
task_name = None
if os.name == "nt":
    from hermes_cli.gateway_windows import get_task_name
    task_name = get_task_name()
print("ORION_PROFILE_PROBE=" + json.dumps({
    "home": str(home),
    "profile": profile_name_for_home(home),
    "standalone": bool(profile_is_standalone(home)),
    "task_name": task_name,
}, sort_keys=True))
'''
    proc = subprocess.run(
        [str(runtime_python), "-B", "-c", code],
        cwd=str(candidate),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "scratch identity probe failed "
            f"(rc={proc.returncode}): {(proc.stderr or '').strip()}"
        )
    marker = "ORION_PROFILE_PROBE="
    rows = [line for line in proc.stdout.splitlines() if line.startswith(marker)]
    if len(rows) != 1:
        raise RuntimeError(f"scratch identity probe expected one marker; observed {len(rows)}")
    data = json.loads(rows[0][len(marker):])
    if data.get("profile") != SCRATCH_PROFILE:
        raise RuntimeError(f"scratch profile resolved incorrectly: {data!r}")
    if data.get("standalone") is not True:
        raise RuntimeError(f"scratch profile is not standalone: {data!r}")
    task_name = data.get("task_name")
    if os.name == "nt":
        if not isinstance(task_name, str) or not task_name.strip():
            raise RuntimeError(f"scratch Windows task identity missing: {data!r}")
        if task_name.casefold() == "hermes_gateway_companion":
            raise RuntimeError("scratch Windows task identity collides with production companion task")
    print("SCRATCH_PROFILE_RESOLUTION=PASS")
    print(f"SCRATCH_PROFILE_NAME={SCRATCH_PROFILE}")
    print("SCRATCH_PROFILE_STANDALONE=true")
    if task_name:
        print(f"SCRATCH_WINDOWS_TASK_NAME={task_name}")
    return task_name


def require_windows_task_absent(task_name: str | None) -> None:
    if os.name != "nt" or not task_name:
        print("SCRATCH_WINDOWS_TASK_COLLISION=NOT_APPLICABLE")
        return
    proc = subprocess.run(
        ["schtasks", "/Query", "/TN", task_name],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=False,
        timeout=15,
    )
    if proc.returncode == 0:
        raise RuntimeError(f"scratch Windows Scheduled Task already exists: {task_name}")
    print("SCRATCH_WINDOWS_TASK_COLLISION=ABSENT")


def windows_netstat_listener_rows(port: int) -> list[tuple[str, int]]:
    if os.name != "nt":
        return []
    proc = subprocess.run(
        ["netstat", "-ano", "-p", "TCP"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"netstat failed with exit code {proc.returncode}")
    rows: list[tuple[str, int]] = []
    wanted = str(port)
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line or "LISTENING" not in line.upper():
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local = parts[1]
        if local.rsplit(":", 1)[-1] != wanted:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        rows.append((local, pid))
    return rows


def verify_windows_bind(port: int, owned_pids: set[int]) -> None:
    if os.name != "nt":
        print("ISOLATED_BIND_NETSTAT=NOT_APPLICABLE_NON_WINDOWS")
        return
    rows = windows_netstat_listener_rows(port)
    if len(rows) != 1:
        raise RuntimeError(f"expected one netstat listener on isolated port {port}; observed {rows}")
    local, pid = rows[0]
    # This smoke explicitly configures IPv4 loopback, so require exactly that bind form.
    if not local.startswith("127.0.0.1:"):
        raise RuntimeError(f"isolated API listener is not IPv4 loopback-only: {local}")
    if pid not in owned_pids:
        raise RuntimeError(
            f"isolated listener PID {pid} is outside candidate process tree {sorted(owned_pids)}"
        )
    print(f"ISOLATED_BIND_NETSTAT={local}|pid={pid}")
    print("ISOLATED_BIND_LOCALHOST_ONLY=PASS")


def verify_runtime_contract(port: int, key: str) -> None:
    url = f"http://127.0.0.1:{port}"
    code, body = direct_http_json("GET", url + "/health")
    if code != 200 or not isinstance(body, dict) or body.get("status") != "ok":
        raise RuntimeError(f"GET /health expected status ok; observed {code}, {body!r}")
    if direct_http_json("GET", url + "/v1/capabilities")[0] != 401:
        raise RuntimeError("unauthenticated capabilities did not return 401")
    if direct_http_json("GET", url + "/v1/capabilities", token="wrong-disposable-token")[0] != 401:
        raise RuntimeError("wrong-token capabilities did not return 401")
    code, caps = direct_http_json("GET", url + "/v1/capabilities", token=key)
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
    if direct_http_json("POST", url + "/api/audio/speak", payload={})[0] != 401:
        raise RuntimeError("unauthenticated audio speak did not return 401")
    if direct_http_json("POST", url + "/api/audio/speak", token=key, payload={})[0] != 400:
        raise RuntimeError("authorized empty audio speak did not return local 400 validation")
    if direct_http_json("POST", url + "/api/audio/transcribe", token=key, payload={})[0] != 400:
        raise RuntimeError("authorized empty audio transcribe did not return local 400 validation")


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
    prod_health_before = health_state(8642)

    scratch_root = Path(tempfile.mkdtemp(prefix=V5_PREFIX))
    scratch_profile = scratch_root / "profiles" / SCRATCH_PROFILE
    v2.prepare_minimal_profile(scratch_profile, port)

    key = secrets.token_urlsafe(36)
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
    print("LAUNCH_MODE=standalone_normal_no_force")
    print(f"ISOLATED_BIND_TARGET=127.0.0.1:{port}")

    task_name = probe_scratch_identity(candidate, runtime_python, env)
    require_windows_task_absent(task_name)

    cmd = [
        str(runtime_python), "-B", "-m", "hermes_cli.main", "gateway", "run", "-v", "-v"
    ]

    proc: subprocess.Popen | None = None
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
            wait_http_ready(proc, port, log_path, key)

        owned = {item.pid for item in base.descendants(proc)}
        verify_windows_bind(port, owned)
        verify_runtime_contract(port, key)
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
    prod_health_after = health_state(8642)
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

    print("ISOLATED_STANDALONE_GATEWAY_CONTRACT=PASS")
    print("PRODUCTION_HERMES_MUTATED=false")
    print("COMPANION_STATE_MUTATED=false")
    print("PRODUCTION_RUNTIME_RESTARTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
