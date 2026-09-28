"""Serve the real HUD against a disposable, in-memory fake Hermes API.

No Hermes imports, credentials, profile, model calls, or vault access. This checks
HUD presentation/transport only; a fake decision is not a Hermes approval.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from http.server import ThreadingHTTPServer

from test_bridge import FakeHermesHandler, HUD_ROOT, bridge


DESCRIPTION = (
    "SIMULATED APPROVAL DISPLAY CHECK - no file action\n"
    "Action: edit Markdown note\n"
    "Canonical target (fictional): C:\\Orion-Disposable-Fixture\\vault\\note.md\n"
    "Exact diff fixture:\n--- vault/note.md\n+++ vault/note.md\n@@ -1,100 +1,100 @@\n"
    + "".join(f"-old line {n:03d}\r\n+new line {n:03d} | caf\u00e9 | <b>literal markup</b>\r\n" for n in range(1, 101))
    + "+END-OF-DIFF-100\n\\ No newline at end of file\n"
)


def approval_event(run_id):
    # Same command/description/choices shape as pinned Hermes api_server.py.
    return {
        "event": "approval.request", "run_id": run_id,
        "command": "orion_vault_apply_plan", "description": DESCRIPTION,
        "action_title": "Review proposed Orion note update",
        "target": "C:\\Orion-Disposable-Fixture\\vault\\note.md",
        "effect": "Apply the displayed Markdown diff after an explicit operator decision.",
        "operation": "edit_note",
        "pattern_key": "plugin_rule:orion_disposable_display_fixture",
        "allow_session": True, "allow_permanent": True,
        "choices": ["once", "session", "always", "deny"],
    }


class ApprovalFixtureHandler(FakeHermesHandler):
    def _record(self, body=b""):
        pass  # Do not retain browser messages or request headers.

    def do_GET(self):
        if self.path == "/health/detailed":
            self._send(200, {"status": "ok"})
        elif self.path.startswith("/api/sessions/session_1/messages"):
            self._send(200, {"messages": [
                {
                    "role": "user",
                    "created_at": "2026-09-27T05:38:00-04:00",
                    "content": "Review the latest progress on the Orion interface and tell me what is working, what still needs attention, and what you would prioritize next.",
                },
                {
                    "role": "assistant",
                    "created_at": "2026-09-27T05:39:00-04:00",
                    "content": "The strongest progress is in the authority model and the new companion-first layout. Approval, evidence, memory authority, and session state remain explicit while the interface is moving toward the cinematic Orion workspace.\n\nWhat still needs attention is visual balance: the hero scene, conversation depth, and operational rails need to feel like one coherent place rather than separate dashboard regions.\n\nI would prioritize composition and readability first, then finish state motion and reconnect qualification.",
                },
                {
                    "role": "user",
                    "created_at": "2026-09-27T05:40:00-04:00",
                    "content": "Keep the interface calm and readable. I want it to feel like a thinking partner, not a telemetry console.",
                },
                {
                    "role": "assistant",
                    "created_at": "2026-09-27T05:41:00-04:00",
                    "content": "Agreed. The visual direction should use atmosphere for identity, while conversation and approvals stay readable and operationally truthful. Decorative depth should never compete with the work surface.",
                },
                {
                    "role": "tool",
                    "session_id": "session_1",
                    "tool_name": "orion_vault_apply_plan",
                    "content": json.dumps({
                        "success": True,
                        "mutation_performed": True,
                        "recovery_required": False,
                        "recovery_id": "f" * 64,
                        "action": "edit_note",
                        "target_relative_path": "fixtures/review-note.md",
                    }),
                },
            ]})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/sessions/session_1/chat/stream":
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            fixture = self.server.fixture
            with fixture.lock:
                if fixture.pending is not None:
                    self._send(409, {"error": "fixture_already_waiting"})
                    return
                pending = {"run_id": "fixture_" + secrets.token_hex(8),
                           "done": threading.Event(), "choice": None}
                fixture.pending = pending
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            def send(event, data):
                frame = f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")
                self.wfile.write(frame)
                self.wfile.flush()

            try:
                run_id = pending["run_id"]
                send("run.started", {"run_id": run_id, "session_id": "session_1"})
                send("approval.request", approval_event(run_id))
                pending["done"].wait(120)
                with fixture.lock:
                    choice = pending["choice"] or "timeout"
                    fixture.pending = None
                print(f"SIMULATED result: {choice}; mutation_performed=false", flush=True)
                send("run.completed", {"run_id": run_id, "status": "completed"})
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with fixture.lock:
                    if fixture.pending is pending:
                        fixture.pending = None
            return

        if self.path.startswith("/v1/runs/fixture_") and self.path.endswith(("/approval", "/stop")):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            try:
                choice = "deny" if self.path.endswith("/stop") else json.loads(raw).get("choice")
            except (ValueError, AttributeError):
                self._send(400, {"error": "invalid_json"})
                return
            fixture = self.server.fixture
            with fixture.lock:
                pending = fixture.pending
                if not pending or self.path.split("/")[3] != pending["run_id"] or pending["done"].is_set():
                    self._send(409, {"error": "no_pending_fixture"})
                    return
                if choice not in bridge.APPROVAL_CHOICES:
                    self._send(400, {"error": "invalid_choice"})
                    return
                pending["choice"] = choice
                self._send(200, {
                    "object": "hermes.run.approval_response",
                    "run_id": pending["run_id"],
                    "choice": choice,
                    "resolved": 1,
                    "mutation_performed": False,
                })
                pending["done"].set()
            return
        super().do_POST()


class ApprovalSurfaceFixture:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = None
        self.cookie = secrets.token_urlsafe(32)
        self.hermes = ThreadingHTTPServer(("127.0.0.1", 0), ApprovalFixtureHandler)
        self.hermes.fixture = self
        state = bridge.BridgeState(
            target=bridge.HermesTarget("127.0.0.1", self.hermes.server_port),
            api_key="disposable-fixture-only", ui_cookie=self.cookie,
            static_root=HUD_ROOT / "static",
        )
        self.orion = bridge.OrionHTTPServer(("127.0.0.1", 0), state)
        self.threads = [threading.Thread(target=s.serve_forever, daemon=True)
                        for s in (self.hermes, self.orion)]
        for thread in self.threads:
            thread.start()

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.orion.server_port}"

    def close(self):
        with self.lock:
            if self.pending:
                self.pending["done"].set()
        for server in (self.orion, self.hermes):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(timeout=2)


def serve_until_interrupted(fixture, sleeper=time.sleep):
    """Keep the disposable fixture alive until Ctrl+C, then always close it."""
    try:
        while True:
            sleeper(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        fixture.close()


if __name__ == "__main__":
    fixture = ApprovalSurfaceFixture()
    print(f"ISOLATED HUD FIXTURE: {fixture.origin}", flush=True)
    print("Open that URL. Select orion-hud-main under SESSION before using Send.", flush=True)
    print("Send 'probe'. Check the complete diff, then choose DENY.", flush=True)
    print("Send 'probe' again and choose ALLOW ONCE. Both decisions are simulated.", flush=True)
    print("No live Hermes/profile/vault access. Ctrl+C closes the fixture.", flush=True)
    serve_until_interrupted(fixture)
