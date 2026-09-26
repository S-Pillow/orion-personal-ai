from __future__ import annotations

import http.client
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HUD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUD_ROOT))

import orion_hud_bridge as bridge


class ProjectionHermesHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requested_paths = []

    def log_message(self, fmt, *args):
        return

    def _send(self, status, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        type(self).requested_paths.append(self.path)
        if self.path.startswith("/api/sessions/session_1/messages"):
            self._send(200, {
                "object": "list",
                "data": [
                    {
                        "id": "1",
                        "session_id": "session_1",
                        "role": "user",
                        "content": "hello",
                    },
                    {
                        "id": "2",
                        "session_id": "session_1",
                        "role": "assistant",
                        "content": "reply",
                    },
                    {
                        "id": "3",
                        "session_id": "session_1",
                        "role": "tool",
                        "tool_name": "orion_vault_apply_plan",
                        "tool_call_id": "call_1",
                        "content": json.dumps({
                            "success": True,
                            "mutation_performed": True,
                            "recovery_required": False,
                            "recovery_id": "c" * 64,
                            "action": "edit_note",
                            "target_relative_path": "note.md",
                            "recovery_dir": "C:/private/recovery",
                            "api_key": "DO-NOT-LEAK",
                        }),
                    },
                ],
            })
        elif self.path == "/v1/runs/run_1":
            self._send(200, {
                "object": "hermes.run",
                "run_id": "run_1",
                "session_id": "session_1",
                "status": "failed",
                "last_event": "run.failed",
                "error": "stack bearer DO-NOT-LEAK",
            })
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if self.path == "/v1/runs/run_1/approval":
            choice = json.loads(raw).get("choice")
            self._send(200, {
                "object": "hermes.run.approval_response",
                "run_id": "run_1",
                "choice": choice,
                "resolved": 1,
                "secret": "DO-NOT-LEAK",
            })
            return
        if self.path == "/api/sessions/session_1/chat/stream":
            frames = [
                (
                    "approval.request",
                    {
                        "event": "approval.request",
                        "session_id": "session_1",
                        "run_id": "run_1",
                        "command": "orion_vault_apply_plan",
                        "description": (
                            "Target: C:/vault/note.md\n--- old\n+++ new"
                        ),
                        "choices": ["once", "deny"],
                        "pattern_key": "plugin_rule:DO-NOT-LEAK",
                        "args": {"new_content": "DO-NOT-LEAK"},
                    },
                ),
                (
                    "run.completed",
                    {
                        "event": "run.completed",
                        "session_id": "session_1",
                        "run_id": "run_1",
                        "messages": [{
                            "role": "tool",
                            "tool_name": "orion_vault_apply_plan",
                            "tool_call_id": "call_1",
                            "content": json.dumps({
                                "success": True,
                                "mutation_performed": True,
                                "recovery_required": False,
                                "recovery_id": "d" * 64,
                                "action": "edit_note",
                                "target_relative_path": "note.md",
                                "recovery_dir": (
                                    "C:/private/DO-NOT-LEAK"
                                ),
                            }),
                        }],
                    },
                ),
            ]
            body = b"".join(
                (
                    f"event: {name}\n"
                    f"data: {json.dumps(data)}\n\n"
                ).encode("utf-8")
                for name, data in frames
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send(404, {"error": "not_found"})


class ProjectionBridgeTests(unittest.TestCase):
    def setUp(self):
        ProjectionHermesHandler.requested_paths = []
        self.hermes = ThreadingHTTPServer(
            ("127.0.0.1", 0), ProjectionHermesHandler
        )
        state = bridge.BridgeState(
            target=bridge.HermesTarget(
                "127.0.0.1", self.hermes.server_port
            ),
            api_key="synthetic-key",
            ui_cookie="synthetic-cookie",
            static_root=HUD_ROOT / "static",
        )
        self.orion = bridge.OrionHTTPServer(
            ("127.0.0.1", 0), state
        )
        self.threads = [
            threading.Thread(
                target=self.hermes.serve_forever, daemon=True
            ),
            threading.Thread(
                target=self.orion.serve_forever, daemon=True
            ),
        ]
        for thread in self.threads:
            thread.start()

    def tearDown(self):
        self.orion.shutdown()
        self.hermes.shutdown()
        self.orion.server_close()
        self.hermes.server_close()
        for thread in self.threads:
            thread.join(timeout=2)

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.orion.server_port}"

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.orion.server_port, timeout=5
        )
        raw = (
            None
            if body is None
            else json.dumps(body).encode("utf-8")
        )
        headers = {
            "Cookie": "orion_ui=synthetic-cookie",
            "Origin": self.origin,
        }
        if raw is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(raw))
        try:
            conn.request(method, path, body=raw, headers=headers)
            response = conn.getresponse()
            data = response.read()
            return response.status, response.getheaders(), data
        finally:
            conn.close()

    def test_transcript_and_action_hydration_are_separate_allowlists(self):
        status, _, raw = self.request(
            "GET", "/api/orion/sessions/session_1/messages"
        )
        self.assertEqual(status, 200)
        transcript = json.loads(raw)
        self.assertEqual(
            [m["role"] for m in transcript["data"]],
            ["user", "assistant"],
        )
        self.assertNotIn("DO-NOT-LEAK", raw.decode())

        status, _, raw = self.request(
            "GET",
            "/api/orion/sessions/session_1/action-evidence",
        )
        self.assertEqual(status, 200)
        evidence = json.loads(raw)
        self.assertIn(
            "/api/sessions/session_1/messages?order=latest&limit=500",
            ProjectionHermesHandler.requested_paths,
        )
        self.assertEqual(evidence["items"][0]["state"], "succeeded")
        self.assertEqual(
            evidence["current_recovery_visibility"], "unavailable"
        )
        self.assertNotIn("recovery_dir", raw.decode())
        self.assertNotIn("DO-NOT-LEAK", raw.decode())

    def test_approval_response_proves_decision_only(self):
        status, _, raw = self.request(
            "POST",
            "/api/orion/runs/run_1/approval",
            {"choice": "once"},
        )
        self.assertEqual(status, 200)
        payload = json.loads(raw)
        self.assertEqual(
            payload["projection"]["state"], "approval_accepted"
        )
        self.assertFalse(payload["execution_proven"])
        self.assertNotIn("DO-NOT-LEAK", raw.decode())

    def test_run_status_is_allowlisted(self):
        status, _, raw = self.request(
            "GET", "/api/orion/runs/run_1"
        )
        self.assertEqual(status, 200)
        payload = json.loads(raw)
        self.assertEqual(payload["status"], "failed")
        self.assertTrue(payload["run_error_observed"])
        self.assertNotIn("DO-NOT-LEAK", raw.decode())

    def test_stream_projection_strips_private_fields_and_raw_transcript(self):
        status, headers, raw = self.request(
            "POST",
            "/api/orion/sessions/session_1/chat/stream",
            {"input": "probe"},
        )
        self.assertEqual(status, 200)
        header_map = {k.lower(): v for k, v in headers}
        self.assertIn(
            "text/event-stream", header_map["content-type"]
        )
        text = raw.decode("utf-8")
        self.assertIn("event: approval.request", text)
        self.assertIn('"state":"approval_requested"', text)
        self.assertIn("event: run.completed", text)
        self.assertIn('"state":"succeeded"', text)
        self.assertNotIn("pattern_key", text)
        self.assertNotIn("new_content", text)
        self.assertNotIn("recovery_dir", text)
        self.assertNotIn("DO-NOT-LEAK", text)
        self.assertNotIn('"messages":', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
