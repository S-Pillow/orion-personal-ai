"""Serve the real HUD against a disposable, in-memory fake Hermes API.

No Hermes imports, credentials, profile, model calls, or vault access. This checks
HUD presentation/transport only; a fake decision is not a Hermes approval.
"""
from __future__ import annotations

import json
import secrets
import threading
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
        elif self.path == "/api/sessions/session_1/messages":
            self._send(200, {"messages": [{
                "role": "assistant",
                "content": "ISOLATED DISPLAY FIXTURE. Send 'probe' to show a simulated approval. "
                           "Check the target, line 100, END-OF-DIFF-100 and literal <b> tags. "
                           "Choose DENY first, then send 'probe' again and choose ALLOW ONCE. "
                           "All choices are simulated; no files change.",
            }]})
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
                self._send(200, {"status": "simulated", "mutation_performed": False})
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


if __name__ == "__main__":
    fixture = ApprovalSurfaceFixture()
    print(f"ISOLATED HUD FIXTURE: {fixture.origin}", flush=True)
    print("Open that URL and send 'probe'. Check the complete diff, then choose DENY.", flush=True)
    print("Send 'probe' again and choose ALLOW ONCE. Both decisions are simulated.", flush=True)
    print("No live Hermes/profile/vault access. Ctrl+C closes the fixture.", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        fixture.close()
