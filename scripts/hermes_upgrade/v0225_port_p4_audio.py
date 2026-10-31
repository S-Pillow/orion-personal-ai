#!/usr/bin/env python3
"""Port Orion P4-04A bounded gateway audio relay to exact Hermes v0.22.5.

The v0.22.5 dashboard/web server has native audio routes, but the authenticated
API-server gateway on port 8642 still advertises audio_api=false and exposes no
/api/audio/transcribe or /api/audio/speak routes. Orion intentionally uses the
single 8642 gateway, so this exact-commit port preserves the accepted P4-04A
architecture without adding a second Hermes server.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXPECTED_HERMES_COMMIT = "bf0203a794a07aac3ff764972ab9087baa4e4f4e"
EXPECTED_API_SERVER_BLOB = "f8160def3de65aa3a26d61196ca1e080e0d1c4f8"
TARGET = "gateway/platforms/api_server.py"
MARKER = "ORION-HERMES-V0225-P4-04A-AUDIO-GATEWAY-v1"

HANDLERS = r'''    # ORION-HERMES-V0225-P4-04A-AUDIO-GATEWAY-v1
    async def _handle_audio_transcribe(self, request: "web.Request") -> "web.Response":
        """Authenticated bounded STT relay using Hermes' existing voice pipeline."""
        auth_err = self._check_auth(request)
        if auth_err:
            return auth_err

        body, err = await self._read_json_body(request)
        if err:
            return err

        data_url = str(body.get("data_url") or "").strip()
        requested_mime = str(body.get("mime_type") or "").strip().lower()
        if not data_url.startswith("data:") or "," not in data_url:
            return web.json_response(
                {"error": "invalid_audio_payload", "message": "Expected a base64 audio data URL."},
                status=400,
            )

        header, encoded = data_url.split(",", 1)
        if ";base64" not in header.lower():
            return web.json_response(
                {"error": "invalid_audio_payload", "message": "Audio data URL must use base64 encoding."},
                status=400,
            )
        declared_mime = header[5:].split(";", 1)[0].strip().lower()
        requested_base_mime = requested_mime.split(";", 1)[0].strip() if requested_mime else declared_mime
        suffix_by_mime = {
            "audio/webm": ".webm", "video/webm": ".webm", "audio/ogg": ".ogg",
            "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
        }
        if (
            declared_mime not in suffix_by_mime
            or requested_base_mime not in suffix_by_mime
            or requested_base_mime != declared_mime
        ):
            return web.json_response(
                {"error": "unsupported_audio_type", "message": "Unsupported or mismatched audio MIME type."},
                status=415,
            )

        try:
            import base64
            import binascii
            import tempfile
            audio_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            return web.json_response(
                {"error": "invalid_audio_payload", "message": "Audio payload is not valid base64."},
                status=400,
            )

        if not audio_bytes:
            return web.json_response(
                {"error": "empty_audio", "message": "Audio recording is empty."}, status=400,
            )
        if len(audio_bytes) > 4 * 1024 * 1024:
            return web.json_response(
                {"error": "audio_too_large", "message": "Audio recording exceeds the 4 MiB gateway limit."},
                status=413,
            )

        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                prefix="orion-p4-04a-v0225-", suffix=suffix_by_mime[declared_mime], delete=False,
            ) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_path = temp_audio.name

            request_profile = _api_request_profile.get()

            def _transcribe():
                with self._profile_scope(request_profile):
                    from tools.voice_mode import transcribe_recording
                    return transcribe_recording(temp_path)

            result = await asyncio.to_thread(_transcribe)
        except Exception as exc:
            logger.exception("[%s] gateway audio transcription failed", self.name)
            return web.json_response(
                {"error": "transcription_failed", "message": _redact_api_error_text(exc, limit=300)},
                status=502,
            )
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

        if not isinstance(result, dict) or not result.get("success"):
            message = (
                _redact_api_error_text(result.get("error"), limit=300)
                if isinstance(result, dict)
                else "Hermes transcription returned an invalid result."
            )
            return web.json_response(
                {"error": "transcription_failed", "message": message or "Transcription failed."},
                status=502,
            )

        return web.json_response({
            "ok": True,
            "transcript": str(result.get("transcript") or ""),
            "no_speech": bool(result.get("no_speech")),
        })

    async def _handle_audio_speak(self, request: "web.Request") -> "web.Response":
        """Authenticated bounded TTS relay using Hermes' existing TTS provider."""
        auth_err = self._check_auth(request)
        if auth_err:
            return auth_err

        body, err = await self._read_json_body(request)
        if err:
            return err

        text = str(body.get("text") or "").strip()
        if not text:
            return web.json_response(
                {"error": "tts_text_required", "message": "Text is required."}, status=400,
            )
        if len(text) > 4000:
            return web.json_response(
                {"error": "tts_text_too_large", "message": "Text exceeds the 4,000-character gateway limit."},
                status=413,
            )

        request_profile = _api_request_profile.get()

        def _synthesize():
            with self._profile_scope(request_profile):
                from tools.tts_tool import text_to_speech_tool
                return text_to_speech_tool(text=text)

        try:
            raw_result = await asyncio.to_thread(_synthesize)
            result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
            if not isinstance(result, dict):
                result = {}
        except Exception as exc:
            logger.exception("[%s] gateway TTS synthesis failed", self.name)
            return web.json_response(
                {"error": "tts_failed", "message": _redact_api_error_text(exc, limit=300)}, status=502,
            )

        if not result.get("success"):
            return web.json_response(
                {"error": "tts_failed", "message": _redact_api_error_text(
                    result.get("error") or "Hermes TTS returned an unsuccessful result.", limit=300,
                )},
                status=502,
            )

        audio_path = result.get("file_path")
        if not audio_path:
            paths = result.get("file_paths")
            if isinstance(paths, list) and paths:
                audio_path = paths[0]
        safe_path = validate_media_delivery_path(str(audio_path or ""))
        if not safe_path:
            return web.json_response(
                {"error": "tts_audio_unavailable", "message": "Hermes TTS returned no safe audio file."},
                status=502,
            )

        path = Path(safe_path)
        try:
            size = path.stat().st_size
            if size <= 0:
                raise OSError("empty TTS audio file")
            if size > 16 * 1024 * 1024:
                return web.json_response(
                    {"error": "tts_audio_too_large", "message": "Synthesized audio exceeds 16 MiB."},
                    status=502,
                )
            audio_bytes = await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            return web.json_response(
                {"error": "tts_audio_unavailable", "message": _redact_api_error_text(exc, limit=300)},
                status=502,
            )

        mime_by_suffix = {
            ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
            ".opus": "audio/ogg", ".m4a": "audio/mp4", ".mp4": "audio/mp4",
        }
        mime_type = mime_by_suffix.get(path.suffix.lower())
        if not mime_type:
            return web.json_response(
                {"error": "tts_audio_type_unsupported", "message": "Hermes TTS returned an unsupported audio format."},
                status=502,
            )

        import base64
        encoded = base64.b64encode(audio_bytes).decode("ascii")
        return web.json_response({
            "ok": True,
            "data_url": f"data:{mime_type};base64,{encoded}",
            "mime_type": mime_type,
        })

'''


def _run(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args], check=False, text=True, capture_output=True
    )
    if proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout.strip()


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    args = parser.parse_args()
    root = Path(args.source_root).resolve()
    target = root / TARGET

    head = _run(root, "rev-parse", "HEAD")
    if head != EXPECTED_HERMES_COMMIT:
        raise RuntimeError(f"Hermes source identity mismatch: {head}")
    base_blob = _run(root, "rev-parse", f"HEAD:{TARGET}")
    if base_blob != EXPECTED_API_SERVER_BLOB:
        raise RuntimeError(f"API-server base blob mismatch: {base_blob}")
    live_blob = _run(root, "hash-object", "--no-filters", TARGET)
    if live_blob != EXPECTED_API_SERVER_BLOB:
        raise RuntimeError(f"API-server source was already modified before audio port: {live_blob}")

    text = target.read_text(encoding="utf-8")
    if MARKER in text:
        raise RuntimeError("audio port marker already present before transform")
    if '"skills_api": True, "audio_api": False, "realtime_voice": False,' not in text:
        raise RuntimeError("expected stock v0.22.5 audio capability state not found")
    if '/api/audio/transcribe' in text or '/api/audio/speak' in text:
        raise RuntimeError("stock API-server unexpectedly already exposes audio route markers")

    text = _replace_once(
        text,
        '    "skills_api": True, "audio_api": False, "realtime_voice": False,\n',
        '    "skills_api": True, "audio_api": True, "realtime_voice": False,\n',
        "audio feature flag",
    )
    text = _replace_once(
        text,
        '    ("toolsets", ("GET", "/v1/toolsets")), ("sessions", ("GET", "/api/sessions")),\n',
        '    ("toolsets", ("GET", "/v1/toolsets")),\n'
        '    ("audio_transcribe", ("POST", "/api/audio/transcribe", "audio_api")),\n'
        '    ("audio_speak", ("POST", "/api/audio/speak", "audio_api")),\n'
        '    ("sessions", ("GET", "/api/sessions")),\n',
        "capability endpoint table",
    )
    text = _replace_once(
        text,
        '            ("GET", "/v1/capabilities", self._handle_capabilities),\n'
        '            # Browser-control (gated on browser.extension_control.enabled + API key): POST\n',
        '            ("GET", "/v1/capabilities", self._handle_capabilities),\n'
        '            ("POST", "/api/audio/transcribe", self._handle_audio_transcribe),\n'
        '            ("POST", "/api/audio/speak", self._handle_audio_speak),\n'
        '            # Browser-control (gated on browser.extension_control.enabled + API key): POST\n',
        "gateway route table",
    )
    text = _replace_once(
        text,
        '    @_require_auth\n'
        '    async def _handle_capabilities(self, request: web.Request) -> web.Response:\n',
        HANDLERS
        + '    @_require_auth\n'
        '    async def _handle_capabilities(self, request: web.Request) -> web.Response:\n',
        "audio handler insertion point",
    )

    compile(text, str(target), "exec")
    target.write_text(text, encoding="utf-8", newline="\n")

    verify = target.read_text(encoding="utf-8")
    required = (
        MARKER,
        '"audio_api": True',
        '("audio_transcribe", ("POST", "/api/audio/transcribe", "audio_api"))',
        '("audio_speak", ("POST", "/api/audio/speak", "audio_api"))',
        '("POST", "/api/audio/transcribe", self._handle_audio_transcribe)',
        '("POST", "/api/audio/speak", self._handle_audio_speak)',
        'transcribe_recording(temp_path)',
        'text_to_speech_tool(text=text)',
        'validate_media_delivery_path(str(audio_path or ""))',
        '"realtime_voice": False',
    )
    missing = [item for item in required if item not in verify]
    if missing:
        raise RuntimeError(f"audio port verification failed; missing: {missing}")

    _run(root, "diff", "--check", "--", TARGET)
    print("PORT_P404A_AUDIO_GATEWAY=PASS")
    print(f"AUDIO_GATEWAY_TARGET={TARGET}")
    print("AUDIO_API=true")
    print("REALTIME_VOICE=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
