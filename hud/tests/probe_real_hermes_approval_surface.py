"""Exercise real Hermes approval queue/resolution through the real Orion HUD.

This is an isolated operator probe. It imports the installed Hermes approval
engine, uses its real request_tool_approval -> _await_gateway_decision ->
resolve_gateway_approval path, and routes the resulting approval card through
the real Orion bridge/HUD.

It does NOT install a plugin, start the COMPANION gateway, read COMPANION
credentials, call a model, invoke the registered apply tool, or mutate the
vault/inbox. A temporary note is created under the Orion parent directory only
to build an exact edit preview. The probe calls the source-only
_probe_fresh_once_approval helper; that helper never writes files.

For determinism and safety the fixture:
- forces a fresh random approval key through the helper;
- ignores any stale session/permanent grant for the probe key;
- exposes only DENY and ALLOW ONCE in the HUD;
- rejects session/always at the HTTP fixture boundary;
- forbids persistence callbacks even if something attempts to widen choice;
- routes Hermes approval hooks directly to the candidate plugin observer
  without installing/discovering the plugin.
"""
from __future__ import annotations

import importlib.util
import json
import os
import secrets
import sys
import tempfile
import threading
import time
from contextlib import ExitStack
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from test_bridge import FakeHermesHandler, HUD_ROOT, bridge


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "hermes_plugins" / "orion-vault-actions"
PLUGIN_SPEC = importlib.util.spec_from_file_location(
    "orion_real_hud_probe_plugin", PLUGIN_DIR / "__init__.py"
)
plugin = importlib.util.module_from_spec(PLUGIN_SPEC)
assert PLUGIN_SPEC and PLUGIN_SPEC.loader
sys.modules[PLUGIN_SPEC.name] = plugin
PLUGIN_SPEC.loader.exec_module(plugin)

ALLOWED_CHOICES = frozenset({"once", "deny"})


def hud_approval_event(run_id: str, approval_data: dict) -> dict:
    """Project real Hermes approval data into the pinned Orion HUD event shape."""
    event = dict(approval_data)
    event.update({
        "event": "approval.request",
        "run_id": run_id,
        "allow_session": False,
        "allow_permanent": False,
        "choices": ["once", "deny"],
    })
    return event


class RealHermesApprovalHandler(FakeHermesHandler):
    def _record(self, body=b""):
        pass  # Never retain request bodies/headers in this operator fixture.

    def do_GET(self):
        if self.path == "/health/detailed":
            self._send(200, {"status": "ok"})
        elif self.path == "/api/sessions/session_1/messages":
            self._send(200, {"messages": [{
                "role": "assistant",
                "content": (
                    "REAL HERMES APPROVAL ENGINE / NO-WRITE FIXTURE. "
                    "Send 'probe'. Choose DENY first. Send 'probe' again and "
                    "choose ALLOW ONCE. The candidate handler never mutates files."
                ),
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
                pending = {
                    "run_id": "real_hermes_" + secrets.token_hex(8),
                    "session_key": "orion-real-hud-" + secrets.token_hex(8),
                    "approval_ready": threading.Event(),
                    "done": threading.Event(),
                    "approval_data": None,
                    "fresh_once": None,
                    "error": None,
                }
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

            worker = threading.Thread(
                target=fixture.run_real_approval,
                args=(pending,),
                daemon=True,
            )
            worker.start()

            try:
                run_id = pending["run_id"]
                send("run.started", {"run_id": run_id, "session_id": "session_1"})
                if not pending["approval_ready"].wait(15):
                    raise RuntimeError("real_hermes_approval_not_published")
                if pending["error"]:
                    raise RuntimeError(pending["error"])
                send("approval.request", hud_approval_event(
                    run_id, pending["approval_data"]
                ))
                # Hermes itself owns the human approval timeout. This outer
                # wait is deliberately looser and only protects the fixture.
                pending["done"].wait(360)
                if not pending["done"].is_set():
                    raise RuntimeError("real_hermes_probe_did_not_finish")
                if pending["error"]:
                    raise RuntimeError(pending["error"])
                note_unchanged = fixture.note.read_bytes() == b"before\n"
                print(
                    "REAL HERMES result: "
                    f"fresh_once={str(bool(pending['fresh_once'])).lower()}; "
                    "mutation_performed=false; "
                    f"note_unchanged={str(note_unchanged).lower()}",
                    flush=True,
                )
                send("run.completed", {
                    "run_id": run_id,
                    "status": "completed",
                    "fresh_once": bool(pending["fresh_once"]),
                    "mutation_performed": False,
                })
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as exc:
                pending["error"] = type(exc).__name__
                try:
                    send("run.failed", {
                        "run_id": pending["run_id"],
                        "error": pending["error"],
                    })
                except (BrokenPipeError, ConnectionResetError):
                    pass
            finally:
                worker.join(timeout=2)
                with fixture.lock:
                    if fixture.pending is pending:
                        fixture.pending = None
            return

        if self.path.startswith("/v1/runs/real_hermes_") and self.path.endswith(
            ("/approval", "/stop")
        ):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            try:
                choice = (
                    "deny"
                    if self.path.endswith("/stop")
                    else json.loads(raw).get("choice")
                )
            except (ValueError, AttributeError):
                self._send(400, {"error": "invalid_json"})
                return

            if choice not in ALLOWED_CHOICES:
                self._send(400, {
                    "error": "probe_choice_not_allowed",
                    "allowed": sorted(ALLOWED_CHOICES),
                })
                return

            fixture = self.server.fixture
            with fixture.lock:
                pending = fixture.pending
                if (
                    not pending
                    or self.path.split("/")[3] != pending["run_id"]
                    or pending["done"].is_set()
                ):
                    self._send(409, {"error": "no_pending_fixture"})
                    return
                session_key = pending["session_key"]

            try:
                from tools.approval import resolve_gateway_approval

                resolved = resolve_gateway_approval(session_key, choice)
            except Exception as exc:
                self._send(500, {"error": type(exc).__name__})
                return

            if resolved <= 0:
                self._send(409, {"error": "approval_not_pending"})
                return

            self._send(200, {
                "status": "resolved_by_real_hermes",
                "choice": choice,
                "resolved": resolved,
                "mutation_performed": False,
            })
            return

        super().do_POST()


class RealHermesApprovalSurfaceFixture:
    def __init__(self):
        # Keep the disposable files outside the git worktree and away from the
        # protected live defaults. D:\Orion is the expected parent on Windows.
        base_parent = REPO_ROOT.parent if REPO_ROOT.parent.is_dir() else None
        self.tmp = tempfile.TemporaryDirectory(
            prefix="orion-real-approval-",
            dir=str(base_parent) if base_parent else None,
        )
        base = Path(self.tmp.name)
        self.vault = base / "vault"
        self.inbox = base / "inbox"
        self.vault.mkdir()
        self.inbox.mkdir()
        self.note = self.vault / "note.md"
        self.note.write_bytes(b"before\n")

        self.env = patch.dict(os.environ, {
            "ORION_VAULT_ROOT": str(self.vault),
            "ORION_INBOX_ROOT": str(self.inbox),
            # Process-local marker only; this script does not start a gateway.
            "HERMES_GATEWAY_SESSION": "1",
        })
        self.env.start()

        plugin._PREVIEWS.clear()
        plugin._PREVIEW_TIMES.clear()
        plugin._APPROVAL_ATTEMPTS.clear()
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))
        if not preview.get("success"):
            self.env.stop()
            self.tmp.cleanup()
            raise RuntimeError("disposable_preview_failed")
        self.plan_token = preview["plan_token"]

        self.lock = threading.Lock()
        self.pending = None
        self.cookie = secrets.token_urlsafe(32)
        self.hermes = ThreadingHTTPServer(
            ("127.0.0.1", 0), RealHermesApprovalHandler
        )
        self.hermes.fixture = self
        state = bridge.BridgeState(
            target=bridge.HermesTarget("127.0.0.1", self.hermes.server_port),
            api_key="real-hermes-probe-dummy-http-key",
            ui_cookie=self.cookie,
            static_root=HUD_ROOT / "static",
        )
        self.orion = bridge.OrionHTTPServer(("127.0.0.1", 0), state)
        self.threads = [
            threading.Thread(target=s.serve_forever, daemon=True)
            for s in (self.hermes, self.orion)
        ]
        for thread in self.threads:
            thread.start()

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.orion.server_port}"

    def run_real_approval(self, pending):
        session_token = None
        try:
            from hermes_cli import lifecycle
            from tools import approval

            session_token = approval.set_current_session_key(
                pending["session_key"]
            )

            def notify(data):
                pending["approval_data"] = dict(data)
                pending["approval_ready"].set()

            def route_hook(name, **fields):
                if name == "post_approval_response":
                    plugin.post_approval_response(**fields)
                return []

            def forbid_persistence(*_args, **_kwargs):
                raise RuntimeError("approval_persistence_forbidden_in_probe")

            approval.register_gateway_notify(pending["session_key"], notify)
            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(lifecycle, "invoke_hook", side_effect=route_hook)
                )
                # Fresh private attempt keys must not inherit any ambient grant.
                stack.enter_context(
                    patch.object(approval, "is_approved", return_value=False)
                )
                stack.enter_context(
                    patch.object(approval, "_YOLO_MODE_FROZEN", False)
                )
                stack.enter_context(
                    patch.object(
                        approval,
                        "is_current_session_yolo_enabled",
                        return_value=False,
                    )
                )
                # The fixture boundary exposes only once/deny. These patches
                # are a second safety belt against accidental persistence.
                stack.enter_context(
                    patch.object(
                        approval,
                        "approve_session",
                        side_effect=forbid_persistence,
                    )
                )
                stack.enter_context(
                    patch.object(
                        approval,
                        "approve_permanent",
                        side_effect=forbid_persistence,
                    )
                )
                stack.enter_context(
                    patch.object(
                        approval,
                        "save_permanent_allowlist",
                        side_effect=forbid_persistence,
                    )
                )
                pending["fresh_once"] = plugin._probe_fresh_once_approval(
                    self.plan_token
                )
        except Exception as exc:
            pending["error"] = type(exc).__name__
            pending["approval_ready"].set()
        finally:
            try:
                from tools import approval

                approval.unregister_gateway_notify(pending["session_key"])
            except Exception:
                pass
            if session_token is not None:
                try:
                    from tools import approval

                    approval.reset_current_session_key(session_token)
                except Exception:
                    pass
            pending["done"].set()

    def close(self):
        with self.lock:
            pending = self.pending
        if pending and not pending["done"].is_set():
            try:
                from tools.approval import resolve_gateway_approval

                resolve_gateway_approval(pending["session_key"], "deny")
            except Exception:
                pass
            pending["done"].wait(2)
        for server in (self.orion, self.hermes):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(timeout=2)
        self.env.stop()
        self.tmp.cleanup()


def serve_until_interrupted(fixture, sleeper=time.sleep):
    try:
        while True:
            sleeper(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        fixture.close()


if __name__ == "__main__":
    fixture = RealHermesApprovalSurfaceFixture()
    print(f"REAL HERMES NO-WRITE HUD PROBE: {fixture.origin}", flush=True)
    print("Hermes gateway/service does NOT need to be started for this probe.", flush=True)
    print("Select orion-hud-main under SESSION, then send 'probe'.", flush=True)
    print("First run: choose DENY. Expected fresh_once=false.", flush=True)
    print("Second run: send 'probe' again, choose ALLOW ONCE.", flush=True)
    print("Expected fresh_once=true. Both runs must say mutation_performed=false.", flush=True)
    print("SESSION/ALWAYS are intentionally unavailable. Ctrl+C closes the fixture.", flush=True)
    serve_until_interrupted(fixture)
