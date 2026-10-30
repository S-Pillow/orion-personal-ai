#!/usr/bin/env python3
"""Stable entry point and shared safe helpers for the hardened v0.22.5 gateway smoke.

The retired first implementation copied production COMPANION config into scratch state.
That behavior is intentionally absent. Runtime execution delegates lazily to v2 after
all helper definitions are available, avoiding circular-import ambiguity.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

import psutil

EXPECTED_RELEASE_HEAD = "bf0203a794a07aac3ff764972ab9087baa4e4f4e"
EXPECTED_CANDIDATE_HASHES = {
    "agent/monitoring/cron_health.py": "d5fd17bb5fdefb3c9e197b3633da322c70fa2f3d84a775b6be69c4e7a7d30b08",
    "cron/error_classification.py": "86c4a839152e7188c2e71a290ed953d32b24c050b7bf96df8cbd59c9a8bafd39",
    "cron/executions.py": "639875c57c153df7cbd4782cef802bc93d2b79fdf14da7b9bd090f8877e86a91",
    "cron/jobs.py": "eb64e1f6ccdc7fb158f53f373a1b61f60ae6888be274f0557e1d90be0bc4fe3a",
    "gateway/platforms/api_server.py": "fc376aec9d0812260a279efa89978ff934da902db00c3cce4887e68fb10038d1",
}
DEFAULT_PORT = 18642
HTTP_TIMEOUT_S = 5.0


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stat_signature(path: Path) -> tuple[bool, int | None, int | None]:
    try:
        st = path.stat()
    except FileNotFoundError:
        return False, None, None
    return True, int(st.st_size), int(st.st_mtime_ns)


def git_single(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.rstrip()}"
        )
    lines = proc.stdout.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise RuntimeError(
            f"git {' '.join(args)} expected one non-empty line; observed {len(lines)}"
        )
    return lines[0].strip()


def candidate_status_paths(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode:
        raise RuntimeError(f"candidate git status failed ({proc.returncode})")
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            raise RuntimeError(f"malformed porcelain record: {line!r}")
        paths.append(line[3:])
    return sorted(paths)


def snapshot_production(root: Path, profile_home: Path) -> dict:
    hashed = [
        root / "config.yaml",
        root / ".env",
        root / "active_profile",
        profile_home / "config.yaml",
        profile_home / ".env",
    ]
    runtime = [
        root / "state.db",
        root / "gateway_state.json",
        root / "gateway.pid",
        profile_home / "state.db",
        profile_home / "gateway_state.json",
        profile_home / "gateway.pid",
    ]
    return {
        "hashes": {str(p): sha256(p) for p in hashed},
        "runtime": {str(p): stat_signature(p) for p in runtime},
    }


def listener_rows(port: int) -> list[tuple[int | None, str, int]]:
    rows: list[tuple[int | None, str, int]] = []
    for conn in psutil.net_connections(kind="tcp"):
        if conn.status == psutil.CONN_LISTEN and conn.laddr and int(conn.laddr.port) == port:
            rows.append((conn.pid, str(conn.laddr.ip), int(conn.laddr.port)))
    return sorted(rows, key=lambda row: ((row[0] or -1), row[1], row[2]))


def require_single_listener(port: int, expected_host: str | None = None):
    rows = listener_rows(port)
    if len(rows) != 1:
        raise RuntimeError(f"expected exactly one listener on {port}; observed {rows}")
    row = rows[0]
    if expected_host is not None and row[1] != expected_host:
        raise RuntimeError(
            f"listener on {port} bound to {row[1]!r}, expected {expected_host!r}"
        )
    return row


def tcp_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def http_json(method: str, url: str, token: str | None = None, payload=None):
    headers = {"Accept": "application/json"}
    body = None
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=body, headers=headers, method=method)
    try:
        with urlrequest.urlopen(req, timeout=HTTP_TIMEOUT_S) as response:
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


def safe_log_tail(path: Path, key: str, lines: int = 80) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "<log unavailable>"
    return "\n".join(text.splitlines()[-lines:]).replace(
        key, "<redacted-ephemeral-api-key>"
    )


def scrubbed_child_env(scratch_profile: Path, key: str, port: int) -> dict[str, str]:
    allow = (
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "PROGRAMDATA",
        "PROCESSOR_ARCHITECTURE",
        "PROCESSOR_ARCHITEW6432",
        "NUMBER_OF_PROCESSORS",
        "USERNAME",
    )
    env = {name: os.environ[name] for name in allow if name in os.environ}
    env.update(
        {
            "HERMES_HOME": str(scratch_profile),
            "API_SERVER_ENABLED": "true",
            "API_SERVER_KEY": key,
            "API_SERVER_HOST": "127.0.0.1",
            "API_SERVER_PORT": str(port),
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
            "NO_COLOR": "1",
        }
    )
    return env


def descendants(proc: subprocess.Popen) -> list[psutil.Process]:
    try:
        root = psutil.Process(proc.pid)
    except psutil.Error:
        return []
    try:
        return [root, *root.children(recursive=True)]
    except psutil.Error:
        return [root]


def terminate_owned_tree(proc: subprocess.Popen) -> None:
    owned = descendants(proc)
    identities: list[tuple[int, float]] = []
    for item in owned:
        try:
            identities.append((item.pid, item.create_time()))
        except psutil.Error:
            pass
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    for pid, created in reversed(identities):
        if pid == proc.pid:
            continue
        try:
            item = psutil.Process(pid)
            if abs(item.create_time() - created) <= 0.001:
                item.terminate()
        except psutil.Error:
            pass
    deadline = time.time() + 5
    alive: list[psutil.Process] = []
    while time.time() < deadline:
        alive = []
        for pid, created in identities:
            try:
                item = psutil.Process(pid)
                if abs(item.create_time() - created) <= 0.001 and item.is_running():
                    alive.append(item)
            except psutil.Error:
                pass
        if not alive:
            return
        time.sleep(0.1)
    for item in alive:
        try:
            item.kill()
        except psutil.Error:
            pass


def main() -> int:
    from v0225_isolated_gateway_contract_smoke_v2 import main as hardened_main

    return hardened_main()


if __name__ == "__main__":
    raise SystemExit(main())
