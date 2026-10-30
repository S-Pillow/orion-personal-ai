from __future__ import annotations

import http.client
import json
import sys
import threading
import unittest
from unittest import mock
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

    def test_phase4_voice_controls_match_current_composer_contract(self):
        index = (HUD_ROOT / "static" / "index.html").read_text(encoding="utf-8")
        source = (HUD_ROOT / "static" / "phase4-voice.js").read_text(encoding="utf-8")
        css = (HUD_ROOT / "static" / "phase4-voice.css").read_text(encoding="utf-8")

        self.assertIn('class="composer-actions"', index)
        self.assertIn('sendButton?.closest(".composer-actions")', source)
        self.assertIn("composerActions.insertBefore(voiceButton, sendButton)", source)
        self.assertIn("composerActions.insertBefore(speakButton, sendButton)", source)
        self.assertNotIn("composer.insertBefore(voiceButton, sendButton)", source)
        self.assertIn(".composer-actions.phase4-voice-actions", css)
        self.assertIn(".foreground-workspace:has(> .phase4-voice-status)", css)
        self.assertIn("grid-template-rows: minmax(0, 1fr) 78px auto", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", css)
        self.assertNotIn("minmax(9.5rem, auto)", css)
        self.assertNotIn("minmax(11.25rem, auto)", css)

    def test_interruption_clears_voice_turn_and_aborts_inflight_tts(self):
        source = (HUD_ROOT / "static" / "phase4-voice.js").read_text(encoding="utf-8")
        self.assertIn("activeSpeechController.abort()", source)
        self.assertIn('error?.name === "AbortError"', source)
        self.assertIn("function interruptSpeechAndRun() {\n    voiceTurn = null;", source)
        self.assertIn("if (!stopButton.disabled) stopButton.click()", source)

    def test_recording_is_session_bound_and_microphone_acquisition_is_single_flight(self):
        source = (HUD_ROOT / "static" / "phase4-voice.js").read_text(encoding="utf-8")
        self.assertIn("let recordingSessionId = null", source)
        self.assertIn("let microphonePending = false", source)
        self.assertIn("if (microphonePending || transcriptionPending || pendingVoiceSubmission) return", source)
        self.assertIn("microphonePending = true", source)
        self.assertIn("voiceButton.disabled = !recorderIsActive()", source)
        self.assertIn("recordingSessionId = sessionId", source)
        self.assertIn("sessionStillSelected(boundSessionId)", source)
        self.assertIn('queueTranscriptSubmission(payload.transcript || "", sessionId)', source)
        self.assertIn("SESSION CHANGED · TRANSCRIPT NOT SENT", source)
        self.assertIn("SESSION CHANGED · RECORDING DISCARDED", source)

    def test_barge_in_retains_transcript_until_current_run_releases_controls(self):
        source = (HUD_ROOT / "static" / "phase4-voice.js").read_text(encoding="utf-8")
        self.assertIn("let pendingVoiceSubmission = null", source)
        self.assertIn("function trySubmitPendingVoice()", source)
        self.assertIn("if (sendButton.disabled || sessionSelect.disabled)", source)
        self.assertIn("WAITING FOR PRIOR RUN TO STOP", source)
        self.assertIn('composer.dispatchEvent(new Event("submit"', source)
        self.assertIn("if (!sendButton.disabled)", source)
        self.assertIn("TRANSCRIPT READY · WAITING TO SUBMIT", source)
        self.assertIn("pendingVoiceSubmission = null", source)
        self.assertIn("voiceTurn = speakReplies", source)
        self.assertIn("if (pendingVoiceSubmission && !sendButton.disabled)", source)

    def test_sentence_chunking_consumes_only_a_contiguous_prefix(self):
        source = (HUD_ROOT / "static" / "phase4-voice.js").read_text(encoding="utf-8")
        self.assertIn("function extractCompletedSpeechPrefix(text)", source)
        self.assertIn("remaining.match(/^([\\s\\S]*?", source)
        self.assertIn("remaining = remaining.slice(advance)", source)
        self.assertIn("consumed += advance", source)
        self.assertNotIn("remainder.matchAll(sentencePattern)", source)

    def test_voice_source_observes_exact_chat_stream_before_app_rendering(self):
        source = (HUD_ROOT / "static" / "phase4-voice.js").read_text(encoding="utf-8")
        self.assertIn("const CHAT_STREAM_PATH_RE", source)
        self.assertIn("function requestTargetsChatStream(input, options = {})", source)
        self.assertIn('method !== "POST"', source)
        self.assertIn("url.origin === window.location.origin", source)
        self.assertIn("CHAT_STREAM_PATH_RE.test(url.pathname)", source)
        self.assertIn("function wrapChatStreamResponse(response)", source)
        self.assertIn("new TransformStream", source)
        self.assertIn("controller.enqueue(chunk)", source)
        self.assertIn("observeAssistantStreamFrame(frame)", source)
        self.assertIn('parsed.event === "assistant.delta"', source)
        self.assertIn("voiceTurn.sourceText += delta", source)
        self.assertIn('parsed.event === "assistant.completed"', source)
        self.assertIn("response.body.pipeThrough(observer)", source)
        self.assertIn("window.fetch = nativeFetch", source)
        self.assertNotIn("updateVoiceSourceText", source)
        self.assertNotIn("transcriptObserver", source)

    def test_client_tts_chunks_match_server_text_limit(self):
        source = (HUD_ROOT / "static" / "phase4-voice.js").read_text(encoding="utf-8")
        self.assertEqual(voice.MAX_TTS_TEXT_CHARS, 4000)
        self.assertIn("const MAX_TTS_TEXT_CHARS = 4000", source)
        self.assertIn("function splitSpeechForTts(text)", source)
        self.assertIn('lastIndexOf(" ", MAX_TTS_TEXT_CHARS)', source)
        self.assertIn("cut = MAX_TTS_TEXT_CHARS", source)
        self.assertIn("while (remaining.length > MAX_TTS_TEXT_CHARS)", source)
        self.assertIn("for (const clean of parts)", source)

    def test_voice_audio_response_limit_is_separate_from_base_proxy_limit(self):
        source = (HUD_ROOT / "orion_phase4_voice_bridge.py").read_text(encoding="utf-8")
        self.assertEqual(bridge.MAX_PROXY_BYTES, 2 * 1024 * 1024)
        self.assertEqual(voice.MAX_VOICE_RESPONSE_BYTES, 24 * 1024 * 1024)
        self.assertGreater(voice.MAX_VOICE_RESPONSE_BYTES, bridge.MAX_PROXY_BYTES)
        self.assertIn("response.read(MAX_VOICE_RESPONSE_BYTES + 1)", source)
        self.assertIn("Hermes audio response exceeded voice proxy limit", source)
        self.assertIn('"GET", "/v1/capabilities", timeout=5.0', source)

    def test_voice_audio_request_accepts_response_larger_than_base_proxy_limit(self):
        data = b"x" * (bridge.MAX_PROXY_BYTES + 1024)
        response = mock.Mock()
        response.status = 200
        response.getheader.return_value = "application/json"
        response.read.return_value = data

        conn = mock.Mock()
        conn.getresponse.return_value = response

        handler = mock.Mock()
        handler.state = bridge.BridgeState(
            target=bridge.HermesTarget("127.0.0.1", 8642),
            api_key="test-secret",
            ui_cookie="test-cookie",
            static_root=HUD_ROOT / "static",
        )

        with mock.patch.object(voice.http.client, "HTTPConnection", return_value=conn):
            status, content_type, returned = voice.Phase4VoiceHandler._request_voice_json(
                handler,
                "/api/audio/speak",
                body={"text": "hello"},
                timeout=voice.VOICE_TTS_TIMEOUT_SECONDS,
            )

        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(returned, data)
        response.read.assert_called_once_with(voice.MAX_VOICE_RESPONSE_BYTES + 1)
        conn.close.assert_called_once()

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

    def test_voice_wrapper_preserves_accepted_hud_server_identity(self):
        self.assertEqual(voice.Phase4VoiceHandler.server_version, bridge.OrionHandler.server_version)
        self.assertEqual(voice.Phase4VoiceHandler.server_version, "OrionHUD/2A")


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

    def test_phase4_csp_allows_returned_tts_data_audio(self):
        status, headers, data = self.request("GET", "/", origin=False, cookie=False)
        self.assertEqual(status, 200)
        header_map = dict(headers)
        csp = header_map.get("Content-Security-Policy", "")
        self.assertIn("media-src 'self' data:", csp)
        self.assertIn(b'/phase4-voice.js', data)
        self.assertTrue(header_map.get("Server", "").startswith("OrionHUD/2A"))

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
        self.assertFalse(
            any(c["path"] == "/api/audio/transcribe" for c in FakeVoiceHermesHandler.calls[before:])
        )

    def test_tts_is_allowlisted_and_server_authenticated(self):
        status, _, data = self.request("POST", "/api/orion/voice/speak", {"text": "Hello there."})
        self.assertEqual(status, 200)
        self.assertIn(b"data:audio/wav;base64", data)
        call = next(c for c in FakeVoiceHermesHandler.calls if c["path"] == "/api/audio/speak")
        self.assertEqual(call["authorization"], "Bearer test-secret")

    def test_tts_rejects_text_above_bounded_server_limit(self):
        status, _, data = self.request(
            "POST",
            "/api/orion/voice/speak",
            {"text": "x" * (voice.MAX_TTS_TEXT_CHARS + 1)},
        )
        self.assertEqual(status, 413)
        self.assertIn(b"tts_text_too_large", data)
        self.assertFalse(any(c["path"] == "/api/audio/speak" for c in FakeVoiceHermesHandler.calls))

    def test_voice_routes_use_bounded_extended_timeouts(self):
        seen: dict[str, float | None] = {}
        original = voice.Phase4VoiceHandler._request_voice_json

        def wrapped(handler, path, *, body, timeout):
            seen[path] = timeout
            return original(handler, path, body=body, timeout=timeout)

        with mock.patch.object(
            voice.Phase4VoiceHandler,
            "_request_voice_json",
            new=wrapped,
        ):
            status, _, _ = self.request(
                "POST",
                "/api/orion/voice/transcribe",
                {
                    "data_url": "data:audio/webm;base64,AAAA",
                    "mime_type": "audio/webm",
                },
            )
            self.assertEqual(status, 200)
            status, _, _ = self.request(
                "POST",
                "/api/orion/voice/speak",
                {"text": "Hello there."},
            )
            self.assertEqual(status, 200)

        self.assertEqual(seen["/api/audio/transcribe"], voice.VOICE_STT_TIMEOUT_SECONDS)
        self.assertEqual(seen["/api/audio/speak"], voice.VOICE_TTS_TIMEOUT_SECONDS)
        self.assertGreater(voice.VOICE_STT_TIMEOUT_SECONDS, 15.0)
        self.assertGreater(voice.VOICE_TTS_TIMEOUT_SECONDS, 15.0)

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
