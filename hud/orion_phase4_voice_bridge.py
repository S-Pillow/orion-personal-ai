#!/usr/bin/env python3
"""Orion Phase 4 voice wrapper around the accepted loopback HUD bridge.

This module adds a narrow, reversible voice surface without changing Hermes
voice ownership. Browser microphone audio is forwarded only to Hermes'
authenticated gateway when that gateway explicitly advertises audio API
support. TTS requests follow the same rule. The Hermes API credential remains
server-side in orion_hud_bridge.

Wake listening is intentionally not enabled here. The accepted P4-03 custom
`Hey Orion` models were rejected, so this slice is push-to-talk only.
"""

from __future__ import annotations

import http.client
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import orion_hud_bridge as base

VOICE_WRAPPER_VERSION = "p4-04-0.2"
MAX_VOICE_REQUEST_BYTES = 6 * 1024 * 1024
MAX_TTS_TEXT_CHARS = 4000
DATA_URL_RE = re.compile(r"^data:(audio/[^;,]+|video/webm)(?:;[^,]*)?;base64,", re.IGNORECASE)


def _redact_voice_config(value: Any) -> Any:
    """Defensive helper retained for tests/future metadata; never expose secrets."""
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"api_key", "key", "token", "authorization", "credential"}:
                continue
            safe[str(key)] = _redact_voice_config(item)
        return safe
    if isinstance(value, list):
        return [_redact_voice_config(item) for item in value]
    return value


class Phase4VoiceHandler(base.OrionHandler):
    """Add only the Phase 4 voice endpoints to the existing allowlist."""

    server_version = "OrionHUD/P4"

    def _read_voice_json(self) -> dict[str, Any] | None:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError:
            self._send_json(411, {"error": "content_length_required"})
            return None
        if length < 0 or length > MAX_VOICE_REQUEST_BYTES:
            self._send_json(413, {"error": "voice_request_too_large"})
            return None
        try:
            raw = self.rfile.read(length)
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return None
        if not isinstance(body, dict):
            self._send_json(400, {"error": "json_object_required"})
            return None
        return body

    def _audio_capability(self) -> tuple[bool, str]:
        """Return whether the accepted Hermes gateway advertises audio_api."""
        try:
            status, content_type, data = self.hermes.request(
                "GET", "/v1/capabilities", timeout=5.0
            )
        except base.BridgeConfigError:
            return False, "hermes_credentials_unavailable"
        except (OSError, http.client.HTTPException, RuntimeError):
            return False, "hermes_unavailable"

        if not (200 <= status < 300) or "json" not in content_type.lower():
            return False, f"capabilities_http_{status}"
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return False, "invalid_capabilities"
        if not isinstance(payload, dict):
            return False, "invalid_capabilities"

        features = payload.get("features")
        if not isinstance(features, dict) or features.get("audio_api") is not True:
            return False, "hermes_gateway_audio_api_unavailable"
        return True, "ready"

    def _require_audio_capability(self) -> bool:
        ready, reason = self._audio_capability()
        if ready:
            return True
        self._send_json(
            503,
            {
                "error": "voice_unavailable",
                "reason": reason,
                "typed_fallback": True,
                "wake": "disabled",
            },
        )
        return False

    def _send_voice_status(self) -> None:
        ready, reason = self._audio_capability()
        self._send_json(
            200,
            {
                "voice": {
                    "activation": "push_to_talk",
                    "wake": "disabled",
                    "ready": ready,
                    "reason": None if ready else reason,
                    "transport": "hermes_gateway_audio_api" if ready else None,
                    "follow_up": "manual_push_to_talk",
                    "barge_in": "push_to_talk_interrupt",
                    "typed_fallback": True,
                },
                "wrapper_version": VOICE_WRAPPER_VERSION,
            },
        )

    def _handle_transcribe(self, body: dict[str, Any]) -> None:
        if not self._require_audio_capability():
            return
        data_url = str(body.get("data_url") or "").strip()
        mime_type = str(body.get("mime_type") or "").strip()
        if not data_url or not DATA_URL_RE.match(data_url):
            self._send_json(400, {"error": "invalid_audio_payload"})
            return
        if mime_type and not (mime_type.lower().startswith("audio/") or mime_type.lower() == "video/webm"):
            self._send_json(400, {"error": "invalid_audio_mime_type"})
            return
        self._proxy_json(
            "POST",
            "/api/audio/transcribe",
            body={"data_url": data_url, "mime_type": mime_type or None},
        )

    def _handle_speak(self, body: dict[str, Any]) -> None:
        if not self._require_audio_capability():
            return
        text = str(body.get("text") or "").strip()
        if not text:
            self._send_json(400, {"error": "tts_text_required"})
            return
        if len(text) > MAX_TTS_TEXT_CHARS:
            self._send_json(413, {"error": "tts_text_too_large"})
            return
        self._proxy_json("POST", "/api/audio/speak", body={"text": text})

    def do_GET(self) -> None:  # noqa: N802
        if not self._request_host_guard():
            return
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            file_path = self.state.static_root / "index.html"
            try:
                html = file_path.read_text(encoding="utf-8", errors="strict")
            except (OSError, UnicodeError):
                self._send_json(500, {"error": "static_asset_missing"})
                return
            marker = "</body>"
            injection = '\n  <script type="module" src="/phase4-voice.js"></script>\n'
            if marker not in html:
                self._send_json(500, {"error": "voice_injection_anchor_missing"})
                return
            html = html.replace(marker, injection + marker, 1)
            self._send_bytes(
                200,
                html.encode("utf-8"),
                "text/html; charset=utf-8",
                set_cookie=True,
            )
            return

        if path == "/api/orion/voice/status":
            if not self._api_guard():
                return
            self._send_voice_status()
            return

        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/api/orion/voice/transcribe", "/api/orion/voice/speak"}:
            super().do_POST()
            return

        self.close_connection = True
        if not self._request_host_guard():
            return
        if not self._api_guard(mutation=True):
            return
        body = self._read_voice_json()
        if body is None:
            return

        if path == "/api/orion/voice/transcribe":
            self._handle_transcribe(body)
        else:
            self._handle_speak(body)


def main(argv: list[str] | None = None) -> int:
    static_root = Path(__file__).resolve().parent / "static"
    base.STATIC_FILES["/phase4-voice.js"] = ("phase4-voice.js", "text/javascript; charset=utf-8")
    base.STATIC_FILES["/phase4-voice.css"] = ("phase4-voice.css", "text/css; charset=utf-8")
    base.OrionHandler = Phase4VoiceHandler

    if not static_root.is_dir():
        print("[orion-voice] static asset directory missing", file=sys.stderr)
        return 2
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
