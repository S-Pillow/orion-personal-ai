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
import orion_phase4_voice_bridge as voice


class FakeVoiceHermesHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    calls: list[dict] = []
    audio_api = True

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
        if self.path == "/v1/capabilities":
            self._send(200, {"features": {"audio_api": self.__class__.audio_api}})
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        self._record(raw)
        if self.path == "/api/audio/transcribe":
            self._send(200, {"ok": True, "transcript": "hello Orion", "provider": "local"})
        elif self.path == "/api/audio/speak":
            self._send(
                200,
                {
                    "ok": True,
                    "data_url": "data:audio/wav;base64,UklGRg==",
                    "mime_type": "audio/wav",
                    "provider": "edge",
                },
            )
        else:
            self._send(404, {"error": "not_found"})


class VoiceFixture:
    def __init__(self, *, audio_api=True):
        FakeVoiceHermesHandler.calls = []
        FakeVoiceHermesHandler.audio_api = audio_api
        self.hermes = ThreadingHTTPServer(("127.0.0.1", 0), FakeVoiceHermesHandler)
        target = bridge.HermesTarget("127.0.0.1", self.hermes.server_port)
        static_root = HUD_ROOT / "static"
        state = bridge.BridgeState(
            target=target,
            api_key="test-secret",
            ui_cookie="test-cookie",
            static_root=static_root,
        )
        original_handler = bridge.OrionHandler
        bridge.OrionHandler = voice.Phase4VoiceHandler
        try:
            self.orion = bridge.OrionHTTPServer(("127.0.0.1", 0), state)
        finally:
            bridge.OrionHandler = original_handler
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


class Phase4VoiceUnitTests(unittest.TestCase):
    def test_redaction_removes_nested_credentials(self):
        value = {
            "api_key": "secret",
            "stt": {"provider": "openai", "token": "secret-2"},
            "tts": [{"credential": "secret-3", "mode": "relay"}],
        }
        safe = voice._redact_voice_config(value)
        rendered = json.dumps(safe)
        self.assertNotIn("secret", rendered)
        self.assertEqual(safe["stt"]["provider"], "openai")
        self.assertEqual(safe["tts"][0]["mode"], "relay")

    def test_source_has_no_new_runtime_or_shell_authority(self):
        source = (HUD_ROOT / "orion_phase4_voice_bridge.py").read_text(encoding="utf-8")
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


class Phase4VoiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = VoiceFixture()
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

    def test_voice_status_uses_gateway_capability_only(self):
        status, _, data = self.request("GET", "/api/orion/voice/status", origin=False)
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertTrue(payload["voice"]["ready"])
        self.assertEqual(payload["voice"]["wake"], "disabled")
        self.assertNotIn(b"api_key", data)
        self.assertNotIn(b"provider", data)
        call = next(c for c in FakeVoiceHermesHandler.calls if c["path"] == "/v1/capabilities")
        self.assertEqual(call["authorization"], "Bearer test-secret")
        self.assertFalse(any(c["path"] == "/api/audio/voice-config" for c in FakeVoiceHermesHandler.calls))

    def test_transcription_is_allowlisted_and_server_authenticated(self):
        body = {
            "data_url": "data:audio/webm;base64,AAAA",
            "mime_type": "audio/webm",
        }
        status, _, data = self.request("POST", "/api/orion/voice/transcribe", body)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["transcript"], "hello Orion")
        call = next(c for c in FakeVoiceHermesHandler.calls if c["path"] == "/api/audio/transcribe")
        self.assertEqual(call["authorization"], "Bearer test-secret")
        self.assertEqual(json.loads(call["body"]), body)

    def test_transcription_rejects_non_audio_before_upstream(self):
        before = len(FakeVoiceHermesHandler.calls)
        status, _, data = self.request(
            "POST",
            "/api/orion/voice/transcribe",
            {"data_url": "data:text/plain;base64,AAAA", "mime_type": "text/plain"},
        )
        self.assertEqual(status, 400)
        self.assertIn(b"invalid_audio_payload", data)
        # Capability check occurs only after the same-origin/API guard but before
        # audio proxying; invalid payload must never reach the audio endpoint.
        self.assertFalse(any(c["path"] == "/api/audio/transcribe" for c in FakeVoiceHermesHandler.calls[before:]))

    def test_tts_is_allowlisted_and_server_authenticated(self):
        status, _, data = self.request("POST", "/api/orion/voice/speak", {"text": "Hello there."})
        self.assertEqual(status, 200)
        self.assertIn(b"data:audio/wav;base64", data)
        call = next(c for c in FakeVoiceHermesHandler.calls if c["path"] == "/api/audio/speak")
        self.assertEqual(call["authorization"], "Bearer test-secret")

    def test_voice_mutation_requires_same_origin(self):
        status, _, data = self.request(
            "POST",
            "/api/orion/voice/speak",
            {"text": "Hello"},
            origin=False,
        )
        self.assertEqual(status, 403)
        self.assertIn(b"same_origin_required", data)


class Phase4VoiceCapabilityGateTests(unittest.TestCase):
    def test_audio_api_false_fails_closed_and_preserves_typed_fallback(self):
        fixture = VoiceFixture(audio_api=False)
        conn = http.client.HTTPConnection("127.0.0.1", fixture.orion.server_port, timeout=5)
        try:
            headers = {"Cookie": "orion_ui=test-cookie"}
            conn.request("GET", "/api/orion/voice/status", headers=headers)
            response = conn.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertFalse(payload["voice"]["ready"])
            self.assertEqual(payload["voice"]["reason"], "hermes_gateway_audio_api_unavailable")
            self.assertTrue(payload["voice"]["typed_fallback"])

            body = json.dumps({"text": "Hello"}).encode("utf-8")
            conn.request(
                "POST",
                "/api/orion/voice/speak",
                body=body,
                headers={
                    "Cookie": "orion_ui=test-cookie",
                    "Origin": fixture.origin,
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                },
            )
            response = conn.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 503)
            self.assertEqual(payload["reason"], "hermes_gateway_audio_api_unavailable")
            self.assertTrue(payload["typed_fallback"])
            self.assertFalse(any(c["path"] == "/api/audio/speak" for c in FakeVoiceHermesHandler.calls))
        finally:
            conn.close()
            fixture.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
