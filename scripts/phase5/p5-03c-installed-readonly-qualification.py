#!/usr/bin/env python3
"""P5-03C installed read-only reconnect/hydration qualification.

This verifier uses the installed COMPANION Hermes runtime and a temporary Orion
loopback HUD bridge. It performs GET/read-only requests only. It does not start
or stop Hermes, resolve approval, submit chat, invoke tools, read vault files,
or mutate runtime/source configuration.
"""
from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


EXPECTED_BRANCH = "feature/orion-phase5-p5-03c-reconnect-hydration"
QUALIFIED_IMPLEMENTATION_ANCESTOR = "e214d152460ede4790488343c01998ccc1b7d53d"
EXPECTED_HERMES_HEAD = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
EXPECTED_P5_03A2_POST_SHA256 = (
    "7a206396aac7abe7e50fd5d346733fea85bb57160cb0a5d8a2e7feda29167c84"
)
FORBIDDEN_MUTATION_ENV = (
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT",
)


def run_text(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"command_failed:{args[0]}:{proc.returncode}:"
            + (proc.stderr or proc.stdout).strip()[:400]
        )
    return proc.stdout.strip()


def git(repo: Path, *args: str) -> str:
    return run_text("git", "-C", str(repo), *args)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_port(port: int, expected: bool, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_listening(port) == expected:
            return True
        time.sleep(0.15)
    return port_listening(port) == expected


def dotenv_assignment_names(path: Path) -> set[str]:
    names: set[str] = set()
    if not path.is_file():
        raise RuntimeError("companion_dotenv_missing")
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name = line.split("=", 1)[0].strip()
        if name:
            names.add(name)
    return names


class OrionClient:
    def __init__(self, origin: str):
        self.origin = origin.rstrip("/")
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def get_json(self, path: str) -> Any:
        request = urllib.request.Request(
            self.origin + path,
            method="GET",
            headers={"Accept": "application/json"},
        )
        with self.opener.open(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))

    def establish_ui_session(self) -> None:
        request = urllib.request.Request(self.origin + "/", method="GET")
        with self.opener.open(request, timeout=8) as response:
            if int(response.status) != 200:
                raise RuntimeError(f"orion_root_http_{response.status}")
            response.read(32)


def rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "items", "sessions", "messages"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--session-id", default="")
    parser.add_argument("--orion-port", type=int, default=8765)
    args = parser.parse_args()

    repo = args.repo.resolve()
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA_unavailable")
    hermes_root = Path(local) / "hermes" / "hermes-agent"
    profile = Path(local) / "hermes" / "profiles" / "companion"
    dotenv = profile / ".env"
    api_source = hermes_root / "gateway" / "platforms" / "api_server.py"
    compat_manifest = api_source.with_name(
        api_source.name + ".orion-p5-03a2-approval-compat.json"
    )
    bridge = repo / "hud" / "orion_hud_bridge.py"

    if not bridge.is_file() or not api_source.is_file():
        raise RuntimeError("required_runtime_source_missing")

    branch = git(repo, "branch", "--show-current")
    head = git(repo, "rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"unexpected_orion_branch:{branch}")
    subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor",
         QUALIFIED_IMPLEMENTATION_ANCESTOR, "HEAD"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    repo_before = git(repo, "status", "--porcelain=v1")
    if repo_before:
        raise RuntimeError("orion_worktree_not_clean")

    hermes_head = git(hermes_root, "rev-parse", "HEAD")
    if hermes_head != EXPECTED_HERMES_HEAD:
        raise RuntimeError(f"hermes_head_drift:{hermes_head}")
    hermes_before = git(hermes_root, "status", "--porcelain=v1")
    api_sha_before = sha256(api_source)
    if api_sha_before != EXPECTED_P5_03A2_POST_SHA256:
        raise RuntimeError(f"p5_03a2_live_sha_drift:{api_sha_before}")
    if not compat_manifest.is_file():
        raise RuntimeError("p5_03a2_manifest_missing")
    compat = json.loads(compat_manifest.read_text(encoding="utf-8"))
    if str(compat.get("post_sha256", "")).lower() != api_sha_before:
        raise RuntimeError("p5_03a2_manifest_live_sha_mismatch")
    if str(compat.get("accepted_hermes_commit", "")) != EXPECTED_HERMES_HEAD:
        raise RuntimeError("p5_03a2_manifest_hermes_head_mismatch")

    for name in FORBIDDEN_MUTATION_ENV:
        if os.environ.get(name):
            raise RuntimeError(f"forbidden_process_env_present:{name}")
    dotenv_names = dotenv_assignment_names(dotenv)
    for name in FORBIDDEN_MUTATION_ENV:
        if name in dotenv_names:
            raise RuntimeError(f"forbidden_persisted_env_present:{name}")

    if not port_listening(8642):
        raise RuntimeError(
            "hermes_not_listening: start COMPANION Hermes manually before Stage C"
        )
    if port_listening(args.orion_port):
        raise RuntimeError(
            f"orion_port_{args.orion_port}_already_in_use:"
            "Stage C requires a verifier-owned temporary Orion bridge"
        )

    bridge_proc = subprocess.Popen(
        [
            sys.executable,
            str(bridge),
            "--host", "127.0.0.1",
            "--port", str(args.orion_port),
        ],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    observed: dict[str, Any] = {}
    try:
        if not wait_port(args.orion_port, True, 8):
            raise RuntimeError("temporary_orion_bridge_did_not_start")

        client = OrionClient(f"http://127.0.0.1:{args.orion_port}")
        client.establish_ui_session()

        status = client.get_json("/api/orion/status")
        if status.get("bridge", {}).get("status") != "ok":
            raise RuntimeError("orion_bridge_status_not_ok")
        if status.get("hermes", {}).get("online") is not True:
            raise RuntimeError("orion_does_not_observe_hermes_online")

        sessions = rows(client.get_json("/api/orion/sessions"))
        session_ids = [
            str(row.get("id") or row.get("session_id") or "")
            for row in sessions
        ]
        session_ids = [value for value in session_ids if value]

        selected = args.session_id.strip()
        if selected and selected not in session_ids:
            raise RuntimeError("requested_session_not_found")
        if not selected:
            if not session_ids:
                raise RuntimeError("no_persisted_session_available_for_stage_c")
            selected = session_ids[0]

        transcript = client.get_json(
            f"/api/orion/sessions/{selected}/messages"
        )
        evidence = client.get_json(
            f"/api/orion/sessions/{selected}/action-evidence"
        )
        transcript_rows = rows(transcript)
        evidence_rows = rows(evidence)

        serialized = json.dumps(
            {"transcript": transcript, "evidence": evidence},
            sort_keys=True,
        )
        for forbidden in (
            "API_SERVER_KEY",
            "ORION_HERMES_API_KEY",
            "recovery_dir",
            "pattern_key",
            "rule_key",
        ):
            if forbidden in serialized:
                raise RuntimeError(f"browser_projection_leak:{forbidden}")

        for item in evidence_rows:
            if item.get("recovery_id") and item.get("recovery_state") != "unavailable":
                raise RuntimeError(
                    "historical_recovery_id_implied_current_recovery_availability"
                )

        observed = {
            "orion_head": head,
            "orion_branch": branch,
            "hermes_head": hermes_head,
            "hermes_api_sha256": api_sha_before,
            "hermes_online": True,
            "session_count": len(session_ids),
            "selected_session": selected,
            "transcript_visible_rows": len(transcript_rows),
            "action_evidence_rows": len(evidence_rows),
            "current_recovery_visibility": evidence.get(
                "current_recovery_visibility"
            ) if isinstance(evidence, dict) else None,
            "mutation_mode_present": False,
            "approval_requested": False,
            "protected_action_executed": False,
            "vault_read": False,
            "vault_mutation": False,
        }
    finally:
        bridge_proc.terminate()
        try:
            bridge_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bridge_proc.kill()
            bridge_proc.wait(timeout=5)

    if port_listening(args.orion_port):
        raise RuntimeError("temporary_orion_bridge_still_listening_after_stop")
    if not port_listening(8642):
        raise RuntimeError("hermes_listener_changed_during_stage_c")

    repo_after = git(repo, "status", "--porcelain=v1")
    hermes_after = git(hermes_root, "status", "--porcelain=v1")
    api_sha_after = sha256(api_source)
    if repo_after != repo_before:
        raise RuntimeError("orion_worktree_changed_during_stage_c")
    if hermes_after != hermes_before:
        raise RuntimeError("hermes_worktree_changed_during_stage_c")
    if api_sha_after != api_sha_before:
        raise RuntimeError("hermes_source_changed_during_stage_c")

    for key, value in observed.items():
        print(f"P5_03C_{key.upper()}={json.dumps(value, ensure_ascii=False)}")
    print("P5_03C_ORION_WORKTREE_UNCHANGED=true")
    print("P5_03C_HERMES_WORKTREE_UNCHANGED=true")
    print("P5_03C_HERMES_SOURCE_UNCHANGED=true")
    print("P5_03C_STAGE_C_READONLY=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_03C_STAGE_C_READONLY=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
