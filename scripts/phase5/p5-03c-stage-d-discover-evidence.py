#!/usr/bin/env python3
"""P5-03C Stage D read-only persisted-action evidence discovery.

Uses the installed COMPANION Hermes runtime through the real Orion bridge
projection. It enumerates persisted sessions and reports only bounded metadata
about projected completed action evidence. It never prints transcript bodies,
tool-result raw content, recovery paths, secrets, or provider configuration.
It performs GET requests only.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import secrets
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Any


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


class OrionClient:
    def __init__(self, origin: str):
        jar = http.cookiejar.CookieJar()
        self.origin = origin.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def establish(self) -> None:
        with self.opener.open(self.origin + "/", timeout=8) as response:
            if int(response.status) != 200:
                raise RuntimeError(f"orion_root_http_{response.status}")
            response.read(32)

    def get_json(self, path: str) -> Any:
        request = urllib.request.Request(
            self.origin + path,
            method="GET",
            headers={"Accept": "application/json"},
        )
        with self.opener.open(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    hud_root = repo / "hud"
    sys.path.insert(0, str(hud_root))
    import orion_hud_bridge as bridge

    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA_unavailable")
    dotenv = (
        Path(local)
        / "hermes"
        / "profiles"
        / "companion"
        / ".env"
    )
    api_key = bridge.load_hermes_api_key(dotenv)
    if not api_key:
        raise RuntimeError("companion_api_server_key_unavailable")

    state = bridge.BridgeState(
        target=bridge.HermesTarget("127.0.0.1", 8642),
        api_key=api_key,
        ui_cookie=secrets.token_urlsafe(32),
        static_root=hud_root / "static",
    )
    server = bridge.OrionHTTPServer(("127.0.0.1", 0), state)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.1},
        daemon=True,
    )
    thread.start()

    qualifying: list[dict[str, Any]] = []
    session_count = 0
    try:
        client = OrionClient(
            f"http://127.0.0.1:{server.server_port}"
        )
        client.establish()
        status = client.get_json("/api/orion/status")
        if status.get("hermes", {}).get("online") is not True:
            raise RuntimeError("hermes_not_online")

        sessions = rows(client.get_json("/api/orion/sessions"))
        session_count = len(sessions)
        for session in sessions:
            session_id = str(
                session.get("id")
                or session.get("session_id")
                or ""
            )
            if not session_id:
                continue
            evidence = client.get_json(
                f"/api/orion/sessions/{session_id}/action-evidence"
            )
            for item in rows(evidence):
                if item.get("durability") != "completed_record":
                    continue
                state_name = str(item.get("state") or "")
                if state_name not in {
                    "succeeded",
                    "failed",
                    "refused",
                    "stale_plan",
                    "unknown",
                }:
                    continue
                qualifying.append({
                    "session_id": session_id,
                    "state": state_name,
                    "source": str(item.get("source") or ""),
                    "action": str(item.get("action") or ""),
                    "has_run_id": bool(item.get("run_id")),
                    "has_recovery_id": bool(item.get("recovery_id")),
                    "recovery_state": str(
                        item.get("recovery_state") or ""
                    ),
                })
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    if thread.is_alive():
        raise RuntimeError("temporary_orion_bridge_did_not_stop")

    print(f"P5_03C_STAGE_D_SESSION_COUNT={session_count}")
    print(
        "P5_03C_STAGE_D_QUALIFYING_EVIDENCE_COUNT="
        f"{len(qualifying)}"
    )
    for index, item in enumerate(qualifying, start=1):
        print(
            f"P5_03C_STAGE_D_EVIDENCE_{index}="
            + json.dumps(item, sort_keys=True)
        )
    print("P5_03C_STAGE_D_TRANSCRIPT_BODIES_PRINTED=false")
    print("P5_03C_STAGE_D_RAW_TOOL_RESULTS_PRINTED=false")
    print("P5_03C_STAGE_D_VAULT_READ=false")
    print("P5_03C_STAGE_D_VAULT_MUTATION=false")
    print("P5_03C_STAGE_D_READONLY_DISCOVERY=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            "P5_03C_STAGE_D_READONLY_DISCOVERY=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
