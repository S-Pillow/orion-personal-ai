#!/usr/bin/env python3
"""Orion Phase 2A loopback HUD bridge.

This process is intentionally a presentation/control client for the accepted
Hermes API server. It does not start, stop, supervise, install, update, or kill
Hermes, Ollama, iai, or any Windows task/service.

Standard-library only so Phase 2A adds no runtime dependency.
"""

from __future__ import annotations

import argparse
import http.client
import http.cookies
import ipaddress
import json
import os
import re
import secrets
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BRIDGE_VERSION = "2a-0.2"
DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_BIND_PORT = 8765
DEFAULT_HERMES_URL = "http://127.0.0.1:8642"
MAX_REQUEST_BYTES = 128 * 1024
MAX_PROXY_BYTES = 2 * 1024 * 1024
ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
APPROVAL_CHOICES = frozenset({"once", "session", "always", "deny"})
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/core-state.js": ("core-state.js", "text/javascript; charset=utf-8"),
    "/workspace-state.js": ("workspace-state.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class BridgeConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class HermesTarget:
    host: str
    port: int


@dataclass
class BridgeState:
    target: HermesTarget
    api_key: str
    ui_cookie: str
    static_root: Path


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def parse_hermes_target(url: str) -> HermesTarget:
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise BridgeConfigError("Hermes URL must use http on loopback")
    if not parsed.hostname or not _is_loopback_host(parsed.hostname):
        raise BridgeConfigError("Hermes URL must resolve to an explicit loopback host")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise BridgeConfigError("Hermes URL must be a bare loopback origin")
    return HermesTarget(parsed.hostname, parsed.port or 80)


def _unquote_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _default_companion_env() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / "hermes" / "profiles" / "companion" / ".env"


def load_hermes_api_key(env_path: Path | None = None) -> str:
    """Read API_SERVER_KEY without logging or returning any other secret."""
    direct = os.environ.get("ORION_HERMES_API_KEY")
    if direct:
        return direct.strip()

    path_value = os.environ.get("ORION_HERMES_ENV")
    path = Path(path_value).expanduser() if path_value else (env_path or _default_companion_env())
    if path is None or not path.is_file():
        return ""

    try:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError):
        return ""

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "API_SERVER_KEY":
            return _unquote_env_value(value)
    return ""


class HermesClient:
    def __init__(self, state: BridgeState):
        self.state = state

    def _connection(self, timeout: float = 10.0) -> http.client.HTTPConnection:
        return http.client.HTTPConnection(self.state.target.host, self.state.target.port, timeout=timeout)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        authenticated: bool = True,
        accept: str = "application/json",
        timeout: float = 15.0,
    ) -> tuple[int, str, bytes]:
        if authenticated and not self.state.api_key:
            raise BridgeConfigError("Hermes API key is unavailable")

        payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers = {"Accept": accept}
        if payload is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(payload))
        if authenticated:
            headers["Authorization"] = f"Bearer {self.state.api_key}"

        conn = self._connection(timeout)
        try:
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            content_type = response.getheader("Content-Type", "application/octet-stream")
            data = response.read(MAX_PROXY_BYTES + 1)
            if len(data) > MAX_PROXY_BYTES:
                raise RuntimeError("Hermes response exceeded Phase 2A proxy limit")
            return response.status, content_type, data
        finally:
            conn.close()

    def open_stream(
        self,
        path: str,
        *,
        body: dict[str, Any],
        timeout: float = 600.0,
    ) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
        if not self.state.api_key:
            raise BridgeConfigError("Hermes API key is unavailable")
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        conn = self._connection(timeout)
        headers = {
            "Authorization": f"Bearer {self.state.api_key}",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
        }
        try:
            conn.request("POST", path, body=payload, headers=headers)
            return conn, conn.getresponse()
        except Exception:
            conn.close()
            raise


class OrionHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, server_address: tuple[str, int], state: BridgeState):
        super().__init__(server_address, OrionHandler)
        self.state = state


class OrionHandler(BaseHTTPRequestHandler):
    server_version = "OrionHUD/2A"
    protocol_version = "HTTP/1.1"

    @property
    def state(self) -> BridgeState:
        return self.server.state  # type: ignore[attr-defined]

    @property
    def hermes(self) -> HermesClient:
        return HermesClient(self.state)

    @property
    def expected_host(self) -> str:
        return f"{DEFAULT_BIND_HOST}:{self.server.server_port}"  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        # Paths/status only. Request/response bodies and authorization are never logged.
        sys.stderr.write("[orion-hud] " + (fmt % args) + "\n")

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "style-src 'self'; script-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'",
        )

    def _set_ui_cookie(self) -> None:
        self.send_header(
            "Set-Cookie",
            f"orion_ui={self.state.ui_cookie}; Path=/; HttpOnly; SameSite=Strict",
        )

    def _has_ui_cookie(self) -> bool:
        raw = self.headers.get("Cookie", "")
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(raw)
        except http.cookies.CookieError:
            return False
        morsel = cookie.get("orion_ui")
        return bool(morsel and secrets.compare_digest(morsel.value, self.state.ui_cookie))

    def _host_ok(self) -> bool:
        return secrets.compare_digest(self.headers.get("Host", ""), self.expected_host)

    def _origin_ok(self) -> bool:
        expected = f"http://{self.expected_host}"
        return secrets.compare_digest(self.headers.get("Origin", ""), expected)

    def _send_bytes(
        self,
        status: int,
        data: bytes,
        content_type: str,
        *,
        set_cookie: bool = False,
    ) -> None:
        self.send_response(status)
        self._security_headers()
        if set_cookie:
            self._set_ui_cookie()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status: int, obj: Any) -> None:
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send_bytes(status, data, "application/json; charset=utf-8")

    def _request_host_guard(self) -> bool:
        if self._host_ok():
            return True
        self._send_json(421, {"error": "loopback_host_required"})
        return False

    def _api_guard(self, *, mutation: bool = False) -> bool:
        if not self._has_ui_cookie():
            self._send_json(403, {"error": "orion_ui_session_required"})
            return False
        if mutation and not self._origin_ok():
            self._send_json(403, {"error": "same_origin_required"})
            return False
        return True

    def _read_json(self) -> dict[str, Any] | None:
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError:
            self._send_json(411, {"error": "content_length_required"})
            return None
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "request_too_large"})
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

    @staticmethod
    def _valid_id(value: str) -> bool:
        return bool(ID_RE.fullmatch(value))

    def _proxy_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> None:
        try:
            status, content_type, data = self.hermes.request(
                method,
                path,
                body=body,
                authenticated=authenticated,
            )
        except BridgeConfigError as exc:
            self._send_json(503, {"error": "hermes_credentials_unavailable", "message": str(exc)})
            return
        except (OSError, http.client.HTTPException, RuntimeError) as exc:
            self._send_json(502, {"error": "hermes_unavailable", "message": type(exc).__name__})
            return
        self._send_bytes(status, data, content_type)

    def do_GET(self) -> None:  # noqa: N802
        if not self._request_host_guard():
            return
        path = urlparse(self.path).path

        if path in STATIC_FILES:
            name, content_type = STATIC_FILES[path]
            file_path = self.state.static_root / name
            try:
                data = file_path.read_bytes()
            except OSError:
                self._send_json(500, {"error": "static_asset_missing"})
                return
            self._send_bytes(200, data, content_type, set_cookie=True)
            return

        if not path.startswith("/api/orion/"):
            self._send_json(404, {"error": "not_found"})
            return
        if not self._api_guard():
            return

        if path == "/api/orion/status":
            self._handle_status()
            return

        fixed = {
            "/api/orion/capabilities": "/v1/capabilities",
            "/api/orion/skills": "/v1/skills",
            "/api/orion/toolsets": "/v1/toolsets",
            "/api/orion/jobs": "/api/jobs",
            "/api/orion/sessions": "/api/sessions",
        }
        upstream = fixed.get(path)
        if upstream:
            self._proxy_json("GET", upstream)
            return

        match = re.fullmatch(r"/api/orion/sessions/([^/]+)(/messages)?", path)
        if match and self._valid_id(match.group(1)):
            suffix = "/messages" if match.group(2) else ""
            self._proxy_json("GET", f"/api/sessions/{match.group(1)}{suffix}")
            return

        match = re.fullmatch(r"/api/orion/runs/([^/]+)", path)
        if match and self._valid_id(match.group(1)):
            self._proxy_json("GET", f"/v1/runs/{match.group(1)}")
            return

        self._send_json(404, {"error": "operation_not_allowlisted"})

    def _handle_status(self) -> None:
        hermes_online = False
        health_status = None
        try:
            status, _, data = self.hermes.request(
                "GET", "/health", authenticated=False, timeout=2.0
            )
            health_status = status
            hermes_online = 200 <= status < 300
            del data
        except (OSError, http.client.HTTPException, RuntimeError):
            pass

        detailed: Any = None
        if hermes_online and self.state.api_key:
            try:
                status, content_type, data = self.hermes.request(
                    "GET", "/health/detailed", timeout=3.0
                )
                if 200 <= status < 300 and "json" in content_type.lower():
                    detailed = json.loads(data.decode("utf-8"))
            except (
                OSError,
                http.client.HTTPException,
                RuntimeError,
                UnicodeError,
                json.JSONDecodeError,
            ):
                detailed = None

        self._send_json(
            200,
            {
                "bridge": {
                    "status": "ok",
                    "version": BRIDGE_VERSION,
                    "lifecycle_authority": False,
                    "bind": self.expected_host,
                },
                "hermes": {
                    "online": hermes_online,
                    "health_http_status": health_status,
                    "credentials_available": bool(self.state.api_key),
                    "detailed": detailed,
                },
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        # POST requests are deliberately one-request connections. This prevents
        # unread rejected request bodies from being interpreted as a follow-on
        # HTTP request by BaseHTTPRequestHandler.
        self.close_connection = True

        if not self._request_host_guard():
            return
        path = urlparse(self.path).path
        if not path.startswith("/api/orion/"):
            self._send_json(404, {"error": "not_found"})
            return
        if not self._api_guard(mutation=True):
            return

        if path == "/api/orion/sessions":
            body = self._read_json()
            if body is None:
                return
            title = body.get("title", "orion-hud-main")
            if not isinstance(title, str) or not (1 <= len(title.strip()) <= 128):
                self._send_json(400, {"error": "invalid_session_title"})
                return
            self._proxy_json("POST", "/api/sessions", body={"title": title.strip()})
            return

        match = re.fullmatch(r"/api/orion/sessions/([^/]+)/chat/stream", path)
        if match:
            session_id = match.group(1)
            if not self._valid_id(session_id):
                self._send_json(400, {"error": "invalid_session_id"})
                return
            body = self._read_json()
            if body is None:
                return
            text = body.get("input")
            if not isinstance(text, str) or not text.strip() or len(text) > 65536:
                self._send_json(400, {"error": "invalid_input"})
                return
            self._proxy_stream(session_id, text)
            return

        match = re.fullmatch(r"/api/orion/runs/([^/]+)/stop", path)
        if match:
            run_id = match.group(1)
            if not self._valid_id(run_id):
                self._send_json(400, {"error": "invalid_run_id"})
                return
            body = self._read_json()
            if body is None:
                return
            if body:
                self._send_json(400, {"error": "stop_body_must_be_empty"})
                return
            self._proxy_json("POST", f"/v1/runs/{run_id}/stop", body={})
            return

        match = re.fullmatch(r"/api/orion/runs/([^/]+)/approval", path)
        if match:
            run_id = match.group(1)
            if not self._valid_id(run_id):
                self._send_json(400, {"error": "invalid_run_id"})
                return
            body = self._read_json()
            if body is None:
                return
            choice = body.get("choice")
            if choice not in APPROVAL_CHOICES:
                self._send_json(
                    400,
                    {
                        "error": "invalid_approval_choice",
                        "allowed": sorted(APPROVAL_CHOICES),
                    },
                )
                return
            self._proxy_json(
                "POST", f"/v1/runs/{run_id}/approval", body={"choice": choice}
            )
            return

        self._send_json(404, {"error": "operation_not_allowlisted"})

    def _proxy_stream(self, session_id: str, text: str) -> None:
        try:
            conn, response = self.hermes.open_stream(
                f"/api/sessions/{session_id}/chat/stream",
                body={"input": text},
            )
        except BridgeConfigError as exc:
            self._send_json(
                503,
                {"error": "hermes_credentials_unavailable", "message": str(exc)},
            )
            return
        except (OSError, http.client.HTTPException) as exc:
            self._send_json(
                502,
                {"error": "hermes_unavailable", "message": type(exc).__name__},
            )
            return

        try:
            if response.status < 200 or response.status >= 300:
                data = response.read(MAX_PROXY_BYTES + 1)
                if len(data) > MAX_PROXY_BYTES:
                    data = b'{"error":"upstream_error_too_large"}'
                self._send_bytes(
                    response.status,
                    data,
                    response.getheader("Content-Type", "application/json"),
                )
                return

            self.send_response(response.status)
            self._security_headers()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            while True:
                # Forward available SSE bytes without waiting to fill the buffer.
                # Early run/approval events must arrive before upstream completion.
                chunk = response.read1(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
            self.close_connection = True
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        finally:
            conn.close()


def build_state(args: argparse.Namespace) -> BridgeState:
    if args.host != DEFAULT_BIND_HOST:
        raise BridgeConfigError("Phase 2A bridge may bind only to 127.0.0.1")
    if not (1 <= args.port <= 65535):
        raise BridgeConfigError("Invalid bridge port")
    target = parse_hermes_target(args.hermes_url)
    env_path = Path(args.hermes_env).expanduser() if args.hermes_env else None
    key = load_hermes_api_key(env_path)
    static_root = Path(__file__).resolve().parent / "static"
    return BridgeState(
        target=target,
        api_key=key,
        ui_cookie=secrets.token_urlsafe(32),
        static_root=static_root,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orion Phase 2A loopback HUD bridge")
    parser.add_argument("--host", default=DEFAULT_BIND_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_BIND_PORT)
    parser.add_argument("--hermes-url", default=DEFAULT_HERMES_URL)
    parser.add_argument(
        "--hermes-env", default="", help="Optional path to COMPANION .env"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        state = build_state(args)
        server = OrionHTTPServer((args.host, args.port), state)
    except (BridgeConfigError, OSError) as exc:
        print(f"ORION HUD BRIDGE FAILED: {exc}", file=sys.stderr)
        return 2

    print(f"Orion HUD Phase 2A: http://{args.host}:{args.port}")
    print(f"Hermes target: http://{state.target.host}:{state.target.port}")
    print(f"Hermes credentials available: {bool(state.api_key)}")
    print("Lifecycle authority: NONE (foreground bridge only)")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("Orion HUD bridge stopped. No runtime stop action was issued.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
