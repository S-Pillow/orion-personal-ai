"""Deterministic P5-03C reconnect/hydration fixture.

This fixture serves the real Orion bridge and production HUD against a fake,
read-only Hermes authority. It never touches a live vault, resolves a real
approval, or performs mutation.
"""
from __future__ import annotations

import json
import secrets
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from test_bridge import HUD_ROOT, bridge


FIXTURE_SNIPPET = r'''
window.__orionReconnectFixture = {
  async reloadEvidence() {
    await loadMessages();
    await reconcileReconnectState();
    return this.snapshot();
  },
  async refreshEvidence() {
    await refreshActionEvidence();
    return this.snapshot();
  },
  snapshot() {
    return {
      sessionId: state.sessionId,
      activeRunId: state.activeRunId,
      reconnectInterlockRunId: state.reconnectInterlockRunId,
      streaming: state.streaming,
      sendDisabled: ui.sendButton.disabled,
      newSessionDisabled: ui.newSession.disabled,
      sessionSelectDisabled: ui.sessionSelect.disabled,
      stopDisabled: ui.stopButton.disabled,
      stopHidden: ui.stopButton.hidden,
      authorityState: ui.authorityStatus.dataset.authorityState,
      approvalVisible: !ui.approvalPanel.classList.contains("hidden"),
      actionVisible: !ui.actionEvidencePanel.classList.contains("hidden"),
      actionState: ui.actionEvidencePanel.dataset.actionState,
      execution: ui.actionExecution.textContent,
      recovery: ui.actionRecovery.textContent,
      coreState: ui.coreStage.dataset.coreState,
      coreDetail: ui.coreDetail.textContent,
      transcript: [...ui.transcript.querySelectorAll(".message-body")]
        .map((node) => node.textContent),
      locator: sessionStorage.getItem(RUN_LOCATOR_KEY),
    };
  },
};
'''


def completed_tool_message(
    *,
    session_id: str = "session_1",
    run_id: str = "run_completed",
) -> dict:
    return {
        "id": "tool-result-1",
        "session_id": session_id,
        "run_id": run_id,
        "role": "tool",
        "tool_name": "orion_vault_apply_plan",
        "tool_call_id": "call_1",
        "content": json.dumps({
            "success": True,
            "mutation_performed": True,
            "recovery_required": False,
            "recovery_id": "a" * 64,
            "action": "edit_note",
            "target_relative_path": "fixtures/reconnect-note.md",
            "recovery_dir": "C:/private/DO-NOT-LEAK",
            "api_key": "DO-NOT-LEAK",
        }),
    }


def ordinary_messages(session_id: str = "session_1") -> list[dict]:
    return [
        {
            "id": f"{session_id}-user",
            "session_id": session_id,
            "role": "user",
            "content": f"persisted user turn for {session_id}",
            "created_at": "2026-09-29T10:00:00Z",
        },
        {
            "id": f"{session_id}-assistant",
            "session_id": session_id,
            "role": "assistant",
            "content": f"persisted assistant reply for {session_id}",
            "created_at": "2026-09-29T10:00:01Z",
        },
    ]


class ReconnectHermesHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    @property
    def fixture(self):
        return self.server.fixture

    def _send(self, status: int, payload) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_invalid_json(self) -> None:
        raw = b"{invalid"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        scenario = self.fixture.scenario

        if path == "/health":
            self._send(200, {"status": "ok"})
            return
        if path == "/health/detailed":
            self._send(200, {"status": "ok"})
            return
        if path == "/v1/capabilities":
            self._send(200, {"features": {"sessions": True, "run_stop": True}})
            return
        if path == "/v1/skills":
            self._send(200, {"data": []})
            return
        if path == "/api/jobs":
            self._send(200, {"data": []})
            return
        if path == "/api/sessions":
            sessions = [
                {"id": "session_1", "title": "Reconnect fixture one"},
                {"id": "session_2", "title": "Reconnect fixture two"},
            ]
            if scenario == "session_disappeared":
                sessions = [sessions[1]]
            self._send(200, {"data": sessions})
            return

        if self.path.startswith("/api/sessions/session_1/messages?"):
            if scenario == "hydration_failure":
                self._send(500, {"error": "fixture_hydration_failure"})
                return
            if scenario == "hydration_malformed":
                self._send_invalid_json()
                return
            if scenario == "delayed_session_1":
                time.sleep(0.45)
            rows = ordinary_messages("session_1")
            if scenario in {"completed", "terminal_with_result"}:
                rows.append(completed_tool_message())
            self._send(200, {"data": rows})
            return

        if self.path.startswith("/api/sessions/session_2/messages?"):
            rows = ordinary_messages("session_2")
            self._send(200, {"data": rows})
            return

        if path in {
            "/api/sessions/session_1/messages",
            "/api/sessions/session_2/messages",
        }:
            session_id = path.split("/")[3]
            self._send(200, {"data": ordinary_messages(session_id)})
            return

        if path == "/v1/runs/run_active":
            self._send(200, {
                "object": "hermes.run",
                "run_id": "run_active",
                "session_id": "session_1",
                "status": "running",
                "last_event": "assistant.delta",
            })
            return
        if path == "/v1/runs/run_terminal":
            self._send(200, {
                "object": "hermes.run",
                "run_id": "run_terminal",
                "session_id": "session_1",
                "status": "completed",
                "last_event": "run.completed",
            })
            return
        if path == "/v1/runs/run_waiting":
            self._send(200, {
                "object": "hermes.run",
                "run_id": "run_waiting",
                "session_id": "session_1",
                "status": "waiting_for_approval",
                "last_event": "approval.request",
            })
            return
        if path == "/v1/runs/run_stopping":
            self._send(200, {
                "object": "hermes.run",
                "run_id": "run_stopping",
                "session_id": "session_1",
                "status": "stopping",
                "last_event": "run.stopping",
            })
            return
        if path == "/v1/runs/run_transient":
            self._send(502, {"error": "fixture_transient_run_status"})
            return
        if path == "/v1/runs/run_wrong_session":
            self._send(200, {
                "object": "hermes.run",
                "run_id": "run_wrong_session",
                "session_id": "session_2",
                "status": "running",
            })
            return
        if path.startswith("/v1/runs/"):
            self._send(404, {"error": "run_not_found"})
            return

        self._send(404, {"error": "not_found"})

    def do_POST(self):
        self._send(409, {"error": "fixture_is_read_only"})


class ReconnectFixture:
    def __init__(self):
        self.cookie = secrets.token_urlsafe(32)
        self.scenario = "ordinary"
        self._tmp = tempfile.TemporaryDirectory(prefix="orion-p5-03c-")
        self.static_root = Path(self._tmp.name) / "static"
        shutil.copytree(HUD_ROOT / "static", self.static_root)

        app_path = self.static_root / "app.js"
        app_path.write_text(
            app_path.read_text(encoding="utf-8")
            + "\n"
            + FIXTURE_SNIPPET
            + "\n",
            encoding="utf-8",
        )

        self.hermes = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            ReconnectHermesHandler,
        )
        self.hermes.fixture = self

        state = bridge.BridgeState(
            target=bridge.HermesTarget(
                "127.0.0.1",
                self.hermes.server_port,
            ),
            api_key="p5-03c-fixture-only",
            ui_cookie=self.cookie,
            static_root=self.static_root,
        )
        self.orion = bridge.OrionHTTPServer(("127.0.0.1", 0), state)
        self.threads = [
            threading.Thread(target=server.serve_forever, daemon=True)
            for server in (self.hermes, self.orion)
        ]
        for thread in self.threads:
            thread.start()

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.orion.server_port}"

    def set_scenario(self, name: str) -> None:
        self.scenario = name

    def close(self) -> None:
        for server in (self.orion, self.hermes):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(timeout=2)
        self._tmp.cleanup()


if __name__ == "__main__":
    fixture = ReconnectFixture()
    try:
        print(f"P5-03C HUD: {fixture.origin}", flush=True)
        print("Read-only deterministic reconnect fixture.", flush=True)
        print("Ctrl+C closes fixture servers.", flush=True)
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        fixture.close()
