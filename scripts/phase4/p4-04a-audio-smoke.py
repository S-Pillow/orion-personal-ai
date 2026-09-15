#!/usr/bin/env python3
"""P4-04A authenticated Hermes gateway compatibility smoke.

Default mode is read-only and checks only /health + /v1/capabilities.
Pass --exercise-audio to make one TTS call and feed its returned audio into one
STT call. The API key is loaded using the same COMPANION precedence as Orion's
HUD bridge and is never printed.
"""
from __future__ import annotations

import argparse
import base64
import http.client
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_HERMES_URL = "http://127.0.0.1:8642"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def default_companion_env() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "hermes" / "profiles" / "companion" / ".env" if local else None


def load_api_key() -> str:
    direct = os.environ.get("ORION_HERMES_API_KEY")
    if direct:
        return direct.strip()
    override = os.environ.get("ORION_HERMES_ENV")
    env_path = Path(override).expanduser() if override else default_companion_env()
    if env_path is None or not env_path.is_file():
        return ""
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="strict").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "API_SERVER_KEY":
                return _unquote(value)
    except (OSError, UnicodeError):
        return ""
    return ""


def parse_target(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Hermes smoke target must be an explicit loopback http origin")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise RuntimeError("Hermes smoke target must be a bare loopback origin")
    return parsed.hostname, parsed.port or 80


def request_json(host: str, port: int, api_key: str, method: str, path: str, body=None, timeout=30.0):
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(payload))
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise RuntimeError(f"response too large from {path}")
        try:
            parsed = json.loads(data.decode("utf-8")) if data else {}
        except (UnicodeError, json.JSONDecodeError):
            raise RuntimeError(f"non-JSON response from {path} (HTTP {response.status})") from None
        if not (200 <= response.status < 300):
            message = parsed.get("message") or parsed.get("error") or f"HTTP {response.status}"
            if isinstance(message, dict):
                message = message.get("message") or message.get("code") or "gateway error"
            raise RuntimeError(f"{path} failed: {message}")
        return parsed
    finally:
        conn.close()


def run_capabilities(host: str, port: int, api_key: str) -> None:
    health = request_json(host, port, api_key, "GET", "/health", timeout=5.0)
    if health.get("status") != "ok":
        raise RuntimeError("Hermes /health did not return status=ok")
    capabilities = request_json(host, port, api_key, "GET", "/v1/capabilities", timeout=5.0)
    features = capabilities.get("features") if isinstance(capabilities, dict) else None
    if not isinstance(features, dict):
        raise RuntimeError("capabilities response has no features object")
    if features.get("audio_api") is not True:
        raise RuntimeError("capabilities does not advertise audio_api=true")
    if features.get("realtime_voice") is not False:
        raise RuntimeError("capabilities must keep realtime_voice=false for P4-04A")
    endpoints = capabilities.get("endpoints")
    if not isinstance(endpoints, dict):
        raise RuntimeError("capabilities response has no endpoints object")
    if endpoints.get("audio_transcribe") != {"method": "POST", "path": "/api/audio/transcribe"}:
        raise RuntimeError("audio_transcribe capability endpoint mismatch")
    if endpoints.get("audio_speak") != {"method": "POST", "path": "/api/audio/speak"}:
        raise RuntimeError("audio_speak capability endpoint mismatch")
    print("P4-04A CAPABILITIES PASS audio_api=true realtime_voice=false")


def run_audio_round_trip(host: str, port: int, api_key: str) -> None:
    phrase = "Orion gateway audio compatibility check."
    tts = request_json(
        host,
        port,
        api_key,
        "POST",
        "/api/audio/speak",
        {"text": phrase},
        timeout=60.0,
    )
    data_url = str(tts.get("data_url") or "")
    mime_type = str(tts.get("mime_type") or "")
    match = re.fullmatch(r"data:([^;,]+);base64,(.+)", data_url, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise RuntimeError("TTS response did not contain a valid base64 audio data URL")
    if not mime_type or match.group(1).lower() != mime_type.lower():
        raise RuntimeError("TTS MIME metadata does not match the data URL")
    try:
        decoded = base64.b64decode(match.group(2), validate=True)
    except Exception:
        raise RuntimeError("TTS data URL base64 validation failed") from None
    if not decoded:
        raise RuntimeError("TTS returned empty audio")
    print(f"P4-04A TTS PASS mime={mime_type} bytes={len(decoded)}")

    stt = request_json(
        host,
        port,
        api_key,
        "POST",
        "/api/audio/transcribe",
        {"data_url": data_url, "mime_type": mime_type},
        timeout=90.0,
    )
    transcript = str(stt.get("transcript") or "").strip()
    if not transcript:
        raise RuntimeError("STT returned an empty transcript for synthesized speech")
    print(f"P4-04A STT PASS transcript={transcript!r}")
    print("P4-04A AUDIO ROUND-TRIP PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-url", default=os.environ.get("ORION_HERMES_URL", DEFAULT_HERMES_URL))
    parser.add_argument("--exercise-audio", action="store_true")
    args = parser.parse_args()
    try:
        host, port = parse_target(args.hermes_url)
        api_key = load_api_key()
        if not api_key:
            raise RuntimeError("COMPANION API_SERVER_KEY is unavailable")
        run_capabilities(host, port, api_key)
        if args.exercise_audio:
            run_audio_round_trip(host, port, api_key)
        else:
            print("P4-04A READ-ONLY SMOKE PASS (audio calls not requested)")
        return 0
    except Exception as exc:
        print(f"P4-04A SMOKE FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
