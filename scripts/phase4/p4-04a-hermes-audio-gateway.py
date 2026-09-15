#!/usr/bin/env python3
"""P4-04A deterministic Hermes gateway audio compatibility patcher.

Target: Hermes v0.20.6 / v2026.8.27
Commit: 5fc308a70719a83cccdbba4c0e39c23f5a8239d5
File: gateway/platforms/api_server.py
Expected Git blob SHA-1: 980659c9343d2975040f304e05bf97fa95f6a046

The patch is fail-closed: exact source identity only, byte-for-byte backup,
compile-check before replacement, and exact rollback.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

EXPECTED_BLOB_SHA1 = "980659c9343d2975040f304e05bf97fa95f6a046"
ACCEPTED_HERMES_COMMIT = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
PATCH_ID = "ORION-P4-04A-HERMES-AUDIO-GATEWAY-v1"
HANDLERS = '''    # ORION-P4-04A-HERMES-AUDIO-GATEWAY-v1
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
        header_lower = header.lower()
        if ";base64" not in header_lower:
            return web.json_response(
                {"error": "invalid_audio_payload", "message": "Audio data URL must use base64 encoding."},
                status=400,
            )
        declared_mime = header[5:].split(";", 1)[0].strip().lower()
        requested_base_mime = requested_mime.split(";", 1)[0].strip() if requested_mime else declared_mime
        suffix_by_mime = {
            "audio/webm": ".webm",
            "video/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
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

        max_audio_bytes = 4 * 1024 * 1024
        if not audio_bytes:
            return web.json_response(
                {"error": "empty_audio", "message": "Audio recording is empty."},
                status=400,
            )
        if len(audio_bytes) > max_audio_bytes:
            return web.json_response(
                {"error": "audio_too_large", "message": "Audio recording exceeds the 4 MiB gateway limit."},
                status=413,
            )

        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                prefix="orion-p4-04a-",
                suffix=suffix_by_mime[declared_mime],
                delete=False,
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
                {
                    "error": "transcription_failed",
                    "message": _redact_api_error_text(exc, limit=300),
                },
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

        return web.json_response(
            {
                "ok": True,
                "transcript": str(result.get("transcript") or ""),
                "no_speech": bool(result.get("no_speech")),
            }
        )

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
                {"error": "tts_text_required", "message": "Text is required."},
                status=400,
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
            if isinstance(raw_result, str):
                result = json.loads(raw_result)
            elif isinstance(raw_result, dict):
                result = raw_result
            else:
                result = {}
        except Exception as exc:
            logger.exception("[%s] gateway TTS synthesis failed", self.name)
            return web.json_response(
                {"error": "tts_failed", "message": _redact_api_error_text(exc, limit=300)},
                status=502,
            )

        if not result.get("success"):
            return web.json_response(
                {
                    "error": "tts_failed",
                    "message": _redact_api_error_text(
                        result.get("error") or "Hermes TTS returned an unsuccessful result.",
                        limit=300,
                    ),
                },
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

        try:
            path = Path(safe_path)
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
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".opus": "audio/ogg",
            ".m4a": "audio/mp4",
            ".mp4": "audio/mp4",
        }
        mime_type = mime_by_suffix.get(path.suffix.lower())
        if not mime_type:
            return web.json_response(
                {"error": "tts_audio_type_unsupported", "message": "Hermes TTS returned an unsupported audio format."},
                status=502,
            )

        import base64
        encoded = base64.b64encode(audio_bytes).decode("ascii")
        return web.json_response(
            {
                "ok": True,
                "data_url": f"data:{mime_type};base64,{encoded}",
                "mime_type": mime_type,
            }
        )

'''

def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)

def patch_text(source: str) -> str:
    if PATCH_ID in source:
        return source
    source = _replace_once(
        source,
        '- GET  /v1/capabilities            — machine-readable API capabilities for external UIs\n'
        '- GET  /api/sessions               — list client-visible Hermes sessions\n',
        '- GET  /v1/capabilities            — machine-readable API capabilities for external UIs\n'
        '- POST /api/audio/transcribe       — authenticated Hermes STT relay\n'
        '- POST /api/audio/speak            — authenticated Hermes TTS relay\n'
        '- GET  /api/sessions               — list client-visible Hermes sessions\n',
        "module endpoint documentation",
    )
    source = _replace_once(
        source,
        '            ("GET", "/v1/capabilities", self._handle_capabilities),\n',
        '            ("GET", "/v1/capabilities", self._handle_capabilities),\n'
        '            ("POST", "/api/audio/transcribe", self._handle_audio_transcribe),\n'
        '            ("POST", "/api/audio/speak", self._handle_audio_speak),\n',
        "route table",
    )
    source = _replace_once(
        source,
        '                "audio_api": False,\n',
        '                "audio_api": True,\n',
        "audio capability",
    )
    source = _replace_once(
        source,
        '                "model_options": {"method": "GET", "path": "/api/model/options"},\n',
        '                "model_options": {"method": "GET", "path": "/api/model/options"},\n'
        '                "audio_transcribe": {"method": "POST", "path": "/api/audio/transcribe"},\n'
        '                "audio_speak": {"method": "POST", "path": "/api/audio/speak"},\n',
        "capability endpoint map",
    )
    source = _replace_once(
        source,
        '    # ------------------------------------------------------------------\n'
        '    # Browser-extension control (authenticated local/VPS API)\n'
        '    # ------------------------------------------------------------------\n',
        HANDLERS
        + '    # ------------------------------------------------------------------\n'
        '    # Browser-extension control (authenticated local/VPS API)\n'
        '    # ------------------------------------------------------------------\n',
        "handler insertion point",
    )
    compile(source, "api_server.py", "exec")
    return source

def verify_patched_text(text: str) -> list[str]:
    required = [
        PATCH_ID,
        '("POST", "/api/audio/transcribe", self._handle_audio_transcribe)',
        '("POST", "/api/audio/speak", self._handle_audio_speak)',
        '"audio_api": True',
        '"realtime_voice": False',
        '"audio_transcribe": {"method": "POST", "path": "/api/audio/transcribe"}',
        '"audio_speak": {"method": "POST", "path": "/api/audio/speak"}',
        "transcribe_recording(temp_path)",
        "text_to_speech_tool(text=text)",
    ]
    return [item for item in required if item not in text]

def _paths(target: Path) -> tuple[Path, Path]:
    return (
        target.with_name(target.name + ".orion-p4-04a.bak"),
        target.with_name(target.name + ".orion-p4-04a.json"),
    )

def apply_patch(target: Path) -> int:
    original = target.read_bytes()
    text = original.decode("utf-8")
    if not verify_patched_text(text):
        print(f"P4-04A VERIFY PASS already patched: {target}")
        return 0
    blob = git_blob_sha1(original)
    if blob != EXPECTED_BLOB_SHA1:
        raise RuntimeError(
            f"source identity mismatch: expected Git blob {EXPECTED_BLOB_SHA1}, got {blob}; refusing patch"
        )
    patched_text = patch_text(text)
    missing = verify_patched_text(patched_text)
    if missing:
        raise RuntimeError(f"patched source verification failed; missing: {missing}")
    patched = patched_text.encode("utf-8")
    backup, manifest = _paths(target)
    if backup.exists() or manifest.exists():
        raise RuntimeError("backup/manifest already exists; resolve before applying")
    backup.write_bytes(original)
    metadata = {
        "patch_id": PATCH_ID,
        "accepted_hermes_commit": ACCEPTED_HERMES_COMMIT,
        "target": str(target),
        "pre_git_blob_sha1": blob,
        "pre_sha256": sha256(original),
        "post_sha256": sha256(patched),
        "backup": str(backup),
    }
    manifest.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    temp_target = target.with_name(target.name + ".orion-p4-04a.tmp")
    try:
        temp_target.write_bytes(patched)
        compile(temp_target.read_text(encoding="utf-8"), str(target), "exec")
        os.replace(temp_target, target)
    finally:
        try:
            temp_target.unlink()
        except FileNotFoundError:
            pass
    print("P4-04A APPLY PASS")
    print(f"Target={target}")
    print(f"PreGitBlobSha1={blob}")
    print(f"PreSha256={sha256(original)}")
    print(f"PostSha256={sha256(patched)}")
    print(f"Backup={backup}")
    return 0

def verify_target(target: Path) -> int:
    data = target.read_bytes()
    text = data.decode("utf-8")
    missing = verify_patched_text(text)
    if missing:
        blob = git_blob_sha1(data)
        if blob == EXPECTED_BLOB_SHA1:
            print("P4-04A VERIFY: accepted source is unpatched")
            print(f"GitBlobSha1={blob}")
            return 3
        raise RuntimeError(f"patch verification failed; missing {missing}; Git blob={blob}")
    compile(text, str(target), "exec")
    print("P4-04A VERIFY PASS")
    print(f"Target={target}")
    print(f"Sha256={sha256(data)}")
    return 0

def rollback(target: Path) -> int:
    backup, manifest = _paths(target)
    if not backup.is_file() or not manifest.is_file():
        raise RuntimeError("rollback backup or manifest is missing")
    meta = json.loads(manifest.read_text(encoding="utf-8"))
    if meta.get("patch_id") != PATCH_ID:
        raise RuntimeError("rollback manifest patch id mismatch")
    original = backup.read_bytes()
    blob = git_blob_sha1(original)
    if blob != EXPECTED_BLOB_SHA1:
        raise RuntimeError(
            f"rollback backup identity mismatch: expected {EXPECTED_BLOB_SHA1}, got {blob}"
        )
    if PATCH_ID not in target.read_text(encoding="utf-8"):
        raise RuntimeError("target does not contain the P4-04A marker; refusing destructive rollback")
    temp_target = target.with_name(target.name + ".orion-p4-04a.rollback.tmp")
    try:
        temp_target.write_bytes(original)
        os.replace(temp_target, target)
    finally:
        try:
            temp_target.unlink()
        except FileNotFoundError:
            pass
    if git_blob_sha1(target.read_bytes()) != EXPECTED_BLOB_SHA1:
        raise RuntimeError("rollback write verification failed")
    backup.unlink()
    manifest.unlink()
    print("P4-04A ROLLBACK PASS")
    print(f"Target={target}")
    print(f"RestoredGitBlobSha1={EXPECTED_BLOB_SHA1}")
    return 0

def self_test() -> int:
    fixture = (
        '"""\n'
        '- GET  /v1/capabilities            — machine-readable API capabilities for external UIs\n'
        '- GET  /api/sessions               — list client-visible Hermes sessions\n'
        '"""\n'
        'import asyncio, json, os, re\n'
        'from pathlib import Path\n'
        'logger = type("L", (), {"exception": lambda *a, **k: None})()\n'
        'def _redact_api_error_text(x, limit=None): return str(x)\n'
        'def validate_media_delivery_path(x): return x\n'
        '_api_request_profile = type("C", (), {"get": lambda self: None})()\n'
        'class web:\n'
        '    class Request: pass\n'
        '    class Response: pass\n'
        '    @staticmethod\n'
        '    def json_response(*a, **k): return None\n'
        'class APIServerAdapter:\n'
        '    def _http_route_table(self):\n'
        '        routes = [\n'
        '            ("GET", "/v1/capabilities", self._handle_capabilities),\n'
        '        ]\n'
        '    async def _handle_capabilities(self, request):\n'
        '        value = {\n'
        '            "features": {\n'
        '                "audio_api": False,\n'
        '                "realtime_voice": False,\n'
        '            },\n'
        '            "endpoints": {\n'
        '                "model_options": {"method": "GET", "path": "/api/model/options"},\n'
        '            },\n'
        '        }\n'
        '    # ------------------------------------------------------------------\n'
        '    # Browser-extension control (authenticated local/VPS API)\n'
        '    # ------------------------------------------------------------------\n'
    )
    patched = patch_text(fixture)
    missing = verify_patched_text(patched)
    if missing:
        raise RuntimeError(f"self-test verification failed: {missing}")
    compile(patched, "synthetic_api_server.py", "exec")
    print("P4-04A SELF-TEST PASS")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--apply", action="store_true")
    action.add_argument("--verify", action="store_true")
    action.add_argument("--rollback", action="store_true")
    action.add_argument("--self-test", action="store_true")
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    try:
        if args.self_test:
            return self_test()
        if args.target is None:
            parser.error("--target is required for --apply, --verify, and --rollback")
        target = args.target.resolve()
        if not target.is_file():
            raise RuntimeError(f"target file not found: {target}")
        if args.apply:
            return apply_patch(target)
        if args.verify:
            return verify_target(target)
        return rollback(target)
    except Exception as exc:
        print(f"P4-04A FAIL: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
