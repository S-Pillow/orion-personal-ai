from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

HUD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUD_ROOT))

import orion_hud_bridge as bridge


class FakeHermesHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    calls: list[dict] = []

    def log_message(self, fmt, *args):
        return

    def _record(self, body=b""):
        self.__class__.calls.append(
            {
                "method": self.command,
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": body,
            }
        )

    def _send(self, status: int, payload: object):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        self._record()
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        elif self.path == "/health/detailed":
            self._send(200, {"status": "ready", "readiness": {"checks": []}})
        elif self.path == "/v1/capabilities":
            self._send(200, {"features": {"run_stop": True, "run_approval": True, "session_chat_stream": True}})
        elif self.path == "/api/sessions":
            self._send(200, {"sessions": [{"id": "session_1", "title": "orion-hud-main"}]})
        elif self.path == "/api/sessions/session_1/messages":
            self._send(200, {"messages": [{"role": "user", "content": "hello"}]})
        elif self.path == "/v1/runs/run_1":
            self._send(200, {"run_id": "run_1", "status": "running"})
        elif self.path in ("/v1/skills", "/v1/toolsets", "/api/jobs"):
            self._send(200, [])
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        self._record(raw)
        if self.path == "/api/sessions":
            self._send(201, {"id": "session_1", "title": "orion-hud-main"})
        elif self.path == "/v1/runs/run_1/stop":
            self._send(200, {"status": "stopping"})
        elif self.path == "/v1/runs/run_1/approval":
            self._send(200, {"status": "accepted"})
        elif self.path == "/api/sessions/session_1/chat/stream":
            frames = (
                'event: run.started\ndata: {"run_id":"run_1","session_id":"session_1","seq":1}\n\n'
                'event: assistant.delta\ndata: {"run_id":"run_1","delta":"hello","seq":2}\n\n'
                'event: run.completed\ndata: {"run_id":"run_1","status":"completed","seq":3}\n\n'
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(frames)))
            self.end_headers()
            self.wfile.write(frames)
        else:
            self._send(404, {"error": "not_found"})


class ServerFixture:
    def __init__(self):
        FakeHermesHandler.calls = []
        self.hermes = ThreadingHTTPServer(("127.0.0.1", 0), FakeHermesHandler)
        target = bridge.HermesTarget("127.0.0.1", self.hermes.server_port)
        static_root = HUD_ROOT / "static"
        state = bridge.BridgeState(target=target, api_key="test-secret", ui_cookie="test-cookie", static_root=static_root)
        self.orion = bridge.OrionHTTPServer(("127.0.0.1", 0), state)
        self.threads = [
            threading.Thread(target=self.hermes.serve_forever, daemon=True),
            threading.Thread(target=self.orion.serve_forever, daemon=True),
        ]
        for thread in self.threads:
            thread.start()

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.orion.server_port}"

    def close(self):
        self.orion.shutdown()
        self.hermes.shutdown()
        self.orion.server_close()
        self.hermes.server_close()
        for thread in self.threads:
            thread.join(timeout=2)


class BridgeUnitTests(unittest.TestCase):
    def test_hermes_target_rejects_non_loopback(self):
        with self.assertRaises(bridge.BridgeConfigError):
            bridge.parse_hermes_target("http://192.168.1.10:8642")
        with self.assertRaises(bridge.BridgeConfigError):
            bridge.parse_hermes_target("https://127.0.0.1:8642")
        target = bridge.parse_hermes_target("http://127.0.0.1:8642")
        self.assertEqual(target.host, "127.0.0.1")
        self.assertEqual(target.port, 8642)

    def test_key_loader_reads_only_api_server_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("OTHER_SECRET=do-not-use\nAPI_SERVER_KEY='expected'\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"ORION_HERMES_API_KEY": "", "ORION_HERMES_ENV": ""}, clear=False):
                self.assertEqual(bridge.load_hermes_api_key(env_file), "expected")

    def test_source_has_no_process_or_shell_execution(self):
        source = (HUD_ROOT / "orion_hud_bridge.py").read_text(encoding="utf-8")
        forbidden = (
            "import subprocess",
            "from subprocess",
            "os.system(",
            "os.popen(",
            "taskkill",
            "Start-Process",
            "Stop-Process",
            "hermes gateway",
            "ollama serve",
        )
        for token in forbidden:
            self.assertNotIn(token, source)


class BridgeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ServerFixture()
        self.conn = http.client.HTTPConnection("127.0.0.1", self.fixture.orion.server_port, timeout=5)
        self.cookie = "orion_ui=test-cookie"

    def tearDown(self):
        self.conn.close()
        self.fixture.close()

    def request(self, method, path, body=None, *, origin=True, cookie=True):
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {}
        if cookie:
            headers["Cookie"] = self.cookie
        if origin:
            headers["Origin"] = self.fixture.origin
        if payload is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(payload))
        self.conn.request(method, path, body=payload, headers=headers)
        response = self.conn.getresponse()
        data = response.read()
        return response.status, response.getheaders(), data

    def test_root_sets_http_only_strict_cookie_and_csp(self):
        status, headers, data = self.request("GET", "/", origin=False, cookie=False)
        self.assertEqual(status, 200)
        header_map = {k.lower(): v for k, v in headers}
        self.assertIn("HttpOnly", header_map["set-cookie"])
        self.assertIn("SameSite=Strict", header_map["set-cookie"])
        self.assertIn("default-src 'self'", header_map["content-security-policy"])
        self.assertIn(b"ORION", data)

    def test_api_requires_ui_cookie(self):
        status, _, data = self.request("GET", "/api/orion/status", origin=False, cookie=False)
        self.assertEqual(status, 403)
        self.assertIn(b"orion_ui_session_required", data)

    def test_mutation_requires_same_origin(self):
        status, _, data = self.request("POST", "/api/orion/sessions", {"title": "x"}, origin=False)
        self.assertEqual(status, 403)
        self.assertIn(b"same_origin_required", data)

    def test_status_probes_without_starting_any_runtime(self):
        status, _, data = self.request("GET", "/api/orion/status", origin=False)
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertTrue(payload["hermes"]["online"])
        self.assertFalse(payload["bridge"]["lifecycle_authority"])

    def test_authenticated_proxy_keeps_key_server_side(self):
        status, _, data = self.request("GET", "/api/orion/capabilities", origin=False)
        self.assertEqual(status, 200)
        self.assertNotIn(b"test-secret", data)
        call = next(c for c in FakeHermesHandler.calls if c["path"] == "/v1/capabilities")
        self.assertEqual(call["authorization"], "Bearer test-secret")

    def test_create_session_is_narrowed_to_title(self):
        status, _, _ = self.request("POST", "/api/orion/sessions", {"title": "orion-hud-main", "danger": "ignored"})
        self.assertEqual(status, 201)
        call = next(c for c in FakeHermesHandler.calls if c["method"] == "POST" and c["path"] == "/api/sessions")
        self.assertEqual(json.loads(call["body"]), {"title": "orion-hud-main"})

    def test_invalid_run_id_never_reaches_upstream(self):
        before = len(FakeHermesHandler.calls)
        status, _, _ = self.request("POST", "/api/orion/runs/%2e%2e/stop", {})
        self.assertIn(status, (400, 404))
        self.assertEqual(len(FakeHermesHandler.calls), before)

    def test_stop_proxies_only_known_run_target(self):
        status, _, data = self.request("POST", "/api/orion/runs/run_1/stop", {})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["status"], "stopping")
        call = next(c for c in FakeHermesHandler.calls if c["path"] == "/v1/runs/run_1/stop")
        self.assertEqual(call["authorization"], "Bearer test-secret")

    def test_approval_accepts_canonical_choices_only(self):
        status, _, _ = self.request("POST", "/api/orion/runs/run_1/approval", {"choice": "allow"})
        self.assertEqual(status, 400)
        status, _, _ = self.request("POST", "/api/orion/runs/run_1/approval", {"choice": "once"})
        self.assertEqual(status, 200)
        call = next(c for c in FakeHermesHandler.calls if c["path"] == "/v1/runs/run_1/approval")
        self.assertEqual(json.loads(call["body"]), {"choice": "once"})

    def test_session_stream_is_forwarded_as_sse(self):
        status, headers, data = self.request("POST", "/api/orion/sessions/session_1/chat/stream", {"input": "hello"})
        self.assertEqual(status, 200)
        header_map = {k.lower(): v for k, v in headers}
        self.assertIn("text/event-stream", header_map["content-type"])
        self.assertIn(b"event: run.started", data)
        self.assertIn(b"event: assistant.delta", data)
        self.assertIn(b"event: run.completed", data)

    def test_unknown_proxy_surface_is_blocked(self):
        before = len(FakeHermesHandler.calls)
        status, _, data = self.request("GET", "/api/orion/arbitrary", origin=False)
        self.assertEqual(status, 404)
        self.assertIn(b"operation_not_allowlisted", data)
        self.assertEqual(len(FakeHermesHandler.calls), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
