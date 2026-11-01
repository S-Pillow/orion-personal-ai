#!/usr/bin/env python3
"""Isolated Hermes v0.22.5 session/profile persistence contract smoke.

This gate intentionally does not submit a chat turn or invoke model, memory, STT, or TTS
providers. It exercises only authenticated session-resource operations against a unique
standalone scratch profile, proves durable session state is written under that profile,
and re-verifies that watched production Hermes/COMPANION state is unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import tempfile
from pathlib import Path

import v0225_isolated_gateway_contract_smoke as base
import v0225_isolated_gateway_contract_smoke_v2 as v2
import v0225_isolated_gateway_contract_smoke_v5 as v5
import v0225_isolated_gateway_contract_smoke_v6 as v6

PRODUCTION_PROFILE = v5.PRODUCTION_PROFILE
SCRATCH_PROFILE = v5.SCRATCH_PROFILE
PREFIX = "orion-hermes-v0225-session-profile-"
PERSIST_ID = "orion-v0225-qual-persist"
DELETE_ID = "orion-v0225-qual-delete"
INITIAL_TITLE = "Orion v0.22.5 isolation persistence"
UPDATED_TITLE = "Orion v0.22.5 isolation persistence updated"


def _session(body, expected_id: str) -> dict:
    if not isinstance(body, dict):
        raise RuntimeError(f"session response was not a JSON object: {body!r}")
    row = body.get("session")
    if not isinstance(row, dict) or row.get("id") != expected_id:
        raise RuntimeError(f"session response mismatch for {expected_id}: {body!r}")
    return row


def verify_session_resource_contract(port: int, key: str) -> None:
    url = f"http://127.0.0.1:{port}"

    if v5.direct_http_json("GET", url + "/api/sessions")[0] != 401:
        raise RuntimeError("unauthenticated session list did not return 401")
    if v5.direct_http_json(
        "GET", url + "/api/sessions", token="wrong-disposable-token"
    )[0] != 401:
        raise RuntimeError("wrong-token session list did not return 401")
    if v5.direct_http_json(
        "POST",
        url + "/api/sessions",
        payload={"id": "must-not-create", "title": "unauthenticated"},
    )[0] != 401:
        raise RuntimeError("unauthenticated session create did not return 401")

    code, body = v5.direct_http_json(
        "POST",
        url + "/api/sessions",
        token=key,
        payload={"id": PERSIST_ID, "title": INITIAL_TITLE, "source": "api_server"},
    )
    if code != 201:
        raise RuntimeError(f"session create expected 201; observed {code}, {body!r}")
    created = _session(body, PERSIST_ID)
    if created.get("title") != INITIAL_TITLE:
        raise RuntimeError(f"created session title mismatch: {created!r}")

    code, body = v5.direct_http_json(
        "GET", url + f"/api/sessions/{PERSIST_ID}", token=key
    )
    if code != 200:
        raise RuntimeError(f"session get expected 200; observed {code}, {body!r}")
    _session(body, PERSIST_ID)

    code, body = v5.direct_http_json(
        "PATCH",
        url + f"/api/sessions/{PERSIST_ID}",
        token=key,
        payload={"title": UPDATED_TITLE, "pinned": True},
    )
    if code != 200:
        raise RuntimeError(f"session patch expected 200; observed {code}, {body!r}")
    patched = _session(body, PERSIST_ID)
    if patched.get("title") != UPDATED_TITLE or patched.get("pinned") is not True:
        raise RuntimeError(f"patched session metadata mismatch: {patched!r}")

    code, body = v5.direct_http_json("GET", url + "/api/sessions", token=key)
    if code != 200 or not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise RuntimeError(f"session list expected JSON 200; observed {code}, {body!r}")
    rows = [row for row in body["data"] if isinstance(row, dict)]
    matches = [row for row in rows if row.get("id") == PERSIST_ID]
    if len(matches) != 1 or matches[0].get("title") != UPDATED_TITLE:
        raise RuntimeError(f"updated session absent or duplicated in session list: {matches!r}")

    code, body = v5.direct_http_json(
        "POST",
        url + "/api/sessions",
        token=key,
        payload={"id": DELETE_ID, "title": "Orion v0.22.5 delete contract", "source": "api_server"},
    )
    if code != 201:
        raise RuntimeError(f"delete-contract session create expected 201; observed {code}, {body!r}")
    _session(body, DELETE_ID)

    code, body = v5.direct_http_json(
        "DELETE", url + f"/api/sessions/{DELETE_ID}", token=key
    )
    if code not in (200, 204):
        raise RuntimeError(f"session delete expected 200/204; observed {code}, {body!r}")

    code, _body = v5.direct_http_json(
        "GET", url + f"/api/sessions/{DELETE_ID}", token=key
    )
    if code != 404:
        raise RuntimeError(f"deleted session remained addressable; GET returned {code}")

    print("SESSION_RESOURCE_AUTH=PASS")
    print("SESSION_CREATE=PASS")
    print("SESSION_GET=PASS")
    print("SESSION_PATCH=PASS")
    print("SESSION_LIST=PASS")
    print("SESSION_DELETE=PASS")


def verify_persisted_scratch_session(
    candidate: Path,
    runtime_python: Path,
    scratch_profile: Path,
) -> None:
    state_db = scratch_profile / "state.db"
    if not state_db.is_file():
        raise RuntimeError(f"scratch session database missing: {state_db}")

    inspect_env = {
        name: value
        for name, value in os.environ.items()
        if name in {
            "SystemRoot", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP",
            "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PROGRAMDATA",
            "PROCESSOR_ARCHITECTURE", "PROCESSOR_ARCHITEW6432", "NUMBER_OF_PROCESSORS",
            "USERNAME",
        }
    }
    inspect_env.update(
        {
            "HERMES_HOME": str(scratch_profile),
            "ORION_QUAL_STATE_DB": str(state_db),
            "ORION_QUAL_SESSION_ID": PERSIST_ID,
            "PYTHONUTF8": "1",
            "NO_COLOR": "1",
        }
    )
    code = r'''
import json, os
from pathlib import Path
from hermes_state import SessionDB
path = Path(os.environ["ORION_QUAL_STATE_DB"])
session_id = os.environ["ORION_QUAL_SESSION_ID"]
db = SessionDB(path)
try:
    row = db.get_session(session_id)
    if not isinstance(row, dict):
        raise RuntimeError("persisted session not found")
    safe = {
        "id": row.get("id"),
        "title": row.get("title"),
        "source": row.get("source"),
        "pinned": bool(row.get("pinned")),
    }
    print("ORION_SESSION_PERSISTENCE=" + json.dumps(safe, sort_keys=True))
finally:
    close = getattr(db, "close", None)
    if callable(close):
        close()
'''
    proc = subprocess.run(
        [str(runtime_python), "-B", "-c", code],
        cwd=str(candidate),
        env=inspect_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "scratch persistence probe failed "
            f"(rc={proc.returncode}): {(proc.stderr or '').strip()}"
        )
    marker = "ORION_SESSION_PERSISTENCE="
    rows = [line for line in proc.stdout.splitlines() if line.startswith(marker)]
    if len(rows) != 1:
        raise RuntimeError(f"scratch persistence probe expected one marker; observed {len(rows)}")
    row = json.loads(rows[0][len(marker):])
    if row.get("id") != PERSIST_ID:
        raise RuntimeError(f"persisted scratch session id mismatch: {row!r}")
    if row.get("title") != UPDATED_TITLE or row.get("pinned") is not True:
        raise RuntimeError(f"persisted scratch session metadata mismatch: {row!r}")
    print(f"SCRATCH_STATE_DB={state_db}")
    print("SCRATCH_SESSION_PERSISTENCE=PASS")
    print("SCRATCH_SESSION_PROFILE_ISOLATION=PASS")


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
    prod_before = base.snapshot_production(prod_root, prod_profile)
    prod_health_before = v5.health_state(8642)

    scratch_root = Path(tempfile.mkdtemp(prefix=PREFIX))
    scratch_profile = scratch_root / "profiles" / SCRATCH_PROFILE
    v2.prepare_minimal_profile(scratch_profile, port)
    v6.verify_scratch_bind_config(scratch_profile, port)

    key = secrets.token_urlsafe(36)
    env = base.scrubbed_child_env(scratch_profile, key, port)
    log_path = scratch_root / "gateway.log"

    print(f"CANDIDATE_HEAD={base.git_single(candidate, 'rev-parse', 'HEAD')}")
    print(f"PRODUCTION_8642_HEALTH_BASELINE={prod_health_before}")
    print("QUALIFICATION_SCOPE=session_resource_profile_isolation")
    print("SCRATCH_CONFIG_SOURCE=minimal_generated")
    print(f"SCRATCH_PROFILE_LAYOUT=profiles/{SCRATCH_PROFILE}")
    print("SCRATCH_GATEWAY_STANDALONE=true")
    print("SCRATCH_PRODUCTION_CONFIG_CONTENT_COPIED=false")
    print("SCRATCH_PRODUCTION_CREDENTIALS_COPIED=false")
    print("SCRATCH_API_KEY_PERSISTED=false")
    print("READINESS_ORACLE=http_health_no_proxy")
    print("BIND_ENUMERATION_RECHECK=SKIPPED_REUSE_V6_ACCEPTED_LIMITATION")
    print("CHAT_TURN_SUBMITTED=false")
    print("MODEL_PROVIDER_CALLS=0")
    print("MEMORY_CALLS=0")
    print("STT_PROVIDER_CALLS=0")
    print("TTS_PROVIDER_CALLS=0")

    task_name = v5.probe_scratch_identity(candidate, runtime_python, env)
    v5.require_windows_task_absent(task_name)

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
            v5.wait_http_ready(proc, port, log_path, key)
            v6.verify_post_ready_stability(proc, port, log_path, key)
            verify_session_resource_contract(port, key)
            v6._fail_if_exited(proc, log_path, key, "after session resource contract")
    except Exception as exc:
        failure = exc
    finally:
        if proc is not None:
            base.terminate_owned_tree(proc)
        redaction = v2.redact_log(log_path, key)
        key = "<discarded>"

    if failure is None:
        try:
            verify_persisted_scratch_session(candidate, runtime_python, scratch_profile)
        except Exception as exc:
            failure = exc

    post_errors: list[str] = []
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            post_errors.append(f"isolated port {port} still accepted TCP after cleanup")
    except OSError:
        pass
    if base.snapshot_production(prod_root, prod_profile) != prod_before:
        post_errors.append("production watched artifacts changed during session/profile smoke")
    prod_health_after = v5.health_state(8642)
    if prod_health_after != prod_health_before:
        post_errors.append(
            "production 8642 health baseline changed: "
            f"{prod_health_before} -> {prod_health_after}"
        )
    if base.candidate_status_paths(candidate) != expected_paths:
        post_errors.append("candidate Git status changed during session/profile smoke")
    for rel, expected in base.EXPECTED_CANDIDATE_HASHES.items():
        if base.sha256(candidate / rel) != expected:
            post_errors.append(f"candidate source changed during session/profile smoke: {rel}")

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

    print("ISOLATED_SESSION_PROFILE_CONTRACT=PASS")
    print("PRODUCTION_HERMES_MUTATED=false")
    print("COMPANION_STATE_MUTATED=false")
    print("PRODUCTION_RUNTIME_RESTARTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
