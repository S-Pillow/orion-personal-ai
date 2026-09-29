#!/usr/bin/env python3
"""P5-03C Stage D disposable protected-action reconnect qualification.

Owner-authorized scope:
- temporary disposable vault/inbox/recovery roots only;
- fresh real Hermes human ALLOW ONCE for the exact disposable plan;
- installed plugin private disposable executor only;
- no production mutation mode;
- no real Orion vault/inbox mutation;
- no live Hermes SessionDB injection.

After the disposable edit succeeds, the exact structured plugin result is placed
only into an isolated in-memory fake-Hermes persisted-session fixture. The real
Orion bridge/projection is then reconstructed twice from that persisted result
to prove the consequential state is not browser/process-owned.

On PASS the disposable filesystem fixture is deleted. On failure it is
preserved and its path is printed for investigation.
"""
from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import importlib.util
import inspect
import json
import os
import secrets
import shutil
import socket
import sys
import tempfile
import threading
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch


AUTHORIZATION_TOKEN = "I_AUTHORIZE_P5_03C_STAGE_D_DISPOSABLE"
EXPECTED_BRANCH = "feature/orion-phase5-p5-03c-reconnect-hydration"
EXPECTED_TOOLS = {
    "orion_vault_preview_edit",
    "orion_vault_preview_move_draft",
    "orion_vault_recommend_destination",
    "orion_vault_apply_plan",
}
EXPECTED_HOOKS = {"pre_tool_call", "post_approval_response"}


class PluginContext:
    def __init__(self):
        self.tools = {}
        self.hooks = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def call_mcp(self, *_args, **_kwargs):
        raise RuntimeError("MCP calls are forbidden in P5-03C Stage D")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gateway_is_listening() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex(("127.0.0.1", 8642)) == 0


@contextmanager
def env_scope(values: dict[str, str | None]):
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def git_text(repo: Path, *args: str) -> str:
    import subprocess
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(
            "git_failed:" + (proc.stderr or proc.stdout).strip()[:400]
        )
    return proc.stdout.strip()


def load_installed_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    if not plugin_file.is_file():
        raise RuntimeError(f"installed plugin missing: {plugin_file}")
    spec = importlib.util.spec_from_file_location(
        "orion_p5_03c_stage_d_installed_plugin",
        plugin_file,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed plugin import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PersistedEvidenceHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    @property
    def fixture(self):
        return self.server.fixture

    def _send(self, status: int, payload) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, {"status": "ok"})
            return
        if path == "/health/detailed":
            self._send(200, {"status": "ok"})
            return
        if path == "/v1/capabilities":
            self._send(200, {"features": {"sessions": True}})
            return
        if path == "/v1/skills":
            self._send(200, {"data": []})
            return
        if path == "/v1/toolsets":
            self._send(200, {"data": []})
            return
        if path == "/api/jobs":
            self._send(200, {"data": []})
            return
        if path == "/api/sessions":
            self._send(200, {
                "data": [{
                    "id": self.fixture.session_id,
                    "title": "P5-03C isolated persisted evidence",
                }]
            })
            return
        if path == f"/api/sessions/{self.fixture.session_id}":
            self._send(200, {
                "id": self.fixture.session_id,
                "title": "P5-03C isolated persisted evidence",
            })
            return
        if path == f"/api/sessions/{self.fixture.session_id}/messages":
            self._send(200, {"data": self.fixture.messages})
            return
        self._send(404, {"error": "not_found"})

    def do_POST(self):
        self._send(409, {"error": "p5_03c_stage_d_fixture_read_only"})


class PersistedEvidenceFixture:
    def __init__(self, bridge, tool_name: str, result: dict):
        self.bridge = bridge
        self.session_id = "p5_03c_stage_d"
        self.run_id = "p5_03c_stage_d_run"
        self.messages = [
            {
                "id": "user-1",
                "session_id": self.session_id,
                "role": "user",
                "content": "P5-03C isolated disposable reconnect qualification.",
            },
            {
                "id": "assistant-1",
                "session_id": self.session_id,
                "role": "assistant",
                "content": "Disposable protected action completed in isolated fixture.",
            },
            {
                "id": "tool-1",
                "session_id": self.session_id,
                "run_id": self.run_id,
                "role": "tool",
                "tool_name": tool_name,
                "tool_call_id": "p5_03c_stage_d_call",
                "content": json.dumps(result, separators=(",", ":")),
            },
        ]
        self.hermes = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            PersistedEvidenceHandler,
        )
        self.hermes.fixture = self
        self.hermes_thread = threading.Thread(
            target=self.hermes.serve_forever,
            kwargs={"poll_interval": 0.1},
            daemon=True,
        )
        self.hermes_thread.start()

    def new_orion(self):
        state = self.bridge.BridgeState(
            target=self.bridge.HermesTarget(
                "127.0.0.1",
                self.hermes.server_port,
            ),
            api_key="p5-03c-stage-d-isolated",
            ui_cookie=secrets.token_urlsafe(32),
            static_root=Path(self.bridge.__file__).resolve().parent / "static",
        )
        server = self.bridge.OrionHTTPServer(("127.0.0.1", 0), state)
        thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.1},
            daemon=True,
        )
        thread.start()
        return server, thread

    def close(self):
        self.hermes.shutdown()
        self.hermes.server_close()
        self.hermes_thread.join(timeout=3)


class OrionClient:
    def __init__(self, origin: str):
        self.origin = origin.rstrip("/")
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def establish(self) -> None:
        with self.opener.open(self.origin + "/", timeout=8) as response:
            if int(response.status) != 200:
                raise RuntimeError(f"orion_root_http_{response.status}")
            response.read(32)

    def get_json(self, path: str):
        request = urllib.request.Request(
            self.origin + path,
            method="GET",
            headers={"Accept": "application/json"},
        )
        with self.opener.open(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))


def evidence_items(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("items")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def qualify_reconstruction(bridge, plugin, result: dict) -> tuple[dict, dict]:
    fixture = PersistedEvidenceFixture(bridge, plugin.APPLY_TOOL, result)
    snapshots = []
    try:
        for generation in (1, 2):
            server, thread = fixture.new_orion()
            try:
                client = OrionClient(
                    f"http://127.0.0.1:{server.server_port}"
                )
                client.establish()
                payload = client.get_json(
                    f"/api/orion/sessions/{fixture.session_id}/action-evidence"
                )
                items = evidence_items(payload)
                if len(items) != 1:
                    raise RuntimeError(
                        f"generation_{generation}_evidence_count:{len(items)}"
                    )
                item = items[0]
                if item.get("state") != "succeeded":
                    raise RuntimeError(
                        f"generation_{generation}_state:{item.get('state')}"
                    )
                if item.get("durability") != "completed_record":
                    raise RuntimeError(
                        f"generation_{generation}_durability:"
                        f"{item.get('durability')}"
                    )
                if item.get("mutation_performed") is not True:
                    raise RuntimeError(
                        f"generation_{generation}_mutation_not_projected"
                    )
                if payload.get("current_recovery_visibility") != "unavailable":
                    raise RuntimeError(
                        f"generation_{generation}_recovery_visibility_not_unavailable"
                    )
                serialized = json.dumps(payload, sort_keys=True)
                for forbidden in (
                    "recovery_dir",
                    "API_SERVER_KEY",
                    "ORION_HERMES_API_KEY",
                    str(result.get("recovery_dir") or ""),
                ):
                    if forbidden and forbidden in serialized:
                        raise RuntimeError(
                            f"generation_{generation}_private_field_leak"
                        )
                snapshots.append(item)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                if thread.is_alive():
                    raise RuntimeError(
                        f"generation_{generation}_orion_thread_did_not_stop"
                    )
    finally:
        fixture.close()

    if snapshots[0] != snapshots[1]:
        raise RuntimeError("fresh_hud_process_reconstruction_mismatch")
    return snapshots[0], snapshots[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--authorization-token",
        required=True,
        choices=[AUTHORIZATION_TOKEN],
    )
    parser.add_argument(
        "--fixture-parent",
        type=Path,
        required=True,
        help="Existing neutral parent for disposable roots, e.g. D:\\Orion",
    )
    args = parser.parse_args()

    if args.authorization_token != AUTHORIZATION_TOKEN:
        raise RuntimeError("explicit_stage_d_authorization_required")

    repo = Path(__file__).resolve().parents[2]
    if git_text(repo, "branch", "--show-current") != EXPECTED_BRANCH:
        raise RuntimeError("unexpected_orion_branch")
    if git_text(repo, "status", "--porcelain=v1"):
        raise RuntimeError("orion_worktree_not_clean")

    fixture_parent = args.fixture_parent.resolve()
    if not fixture_parent.is_dir():
        raise RuntimeError(f"fixture_parent_missing:{fixture_parent}")

    if gateway_is_listening():
        raise RuntimeError(
            "Hermes gateway is listening on 127.0.0.1:8642; "
            "Stage D uses the accepted isolated CLI approval path and "
            "requires the gateway stopped"
        )

    for name in (
        "ORION_P5_MUTATION_MODE",
        "ORION_P5_PRODUCTION_RECOVERY_ROOT",
        "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
        "ORION_P5_RECOVERY_ROOT",
    ):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(
                f"unexpected_preexisting_process_setting:{name}"
            )

    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA_unavailable")
    plugin_dir = (
        Path(local)
        / "hermes"
        / "profiles"
        / "companion"
        / "plugins"
        / "orion-vault-actions"
    )
    plugin = load_installed_plugin(plugin_dir)
    ctx = PluginContext()
    plugin.register(ctx)

    if set(ctx.tools) != EXPECTED_TOOLS:
        raise RuntimeError("installed_tool_registration_mismatch")
    if set(ctx.hooks) != EXPECTED_HOOKS:
        raise RuntimeError("installed_hook_registration_mismatch")
    registered_handlers = {
        row["handler"]
        for row in ctx.tools.values()
        if isinstance(row, dict) and "handler" in row
    }
    if plugin._execute_disposable_plan_candidate in registered_handlers:
        raise RuntimeError("private_disposable_executor_registered")
    if "require_fresh_approval" not in inspect.signature(
        plugin._execute_disposable_plan_candidate
    ).parameters:
        raise RuntimeError("installed_disposable_executor_lacks_fresh_approval_seam")

    mode = plugin._production_mutation_mode()
    if (
        not mode.get("valid")
        or mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED
        or mode.get("mutation_allowed")
    ):
        raise RuntimeError("production_mutation_mode_not_disabled")

    hud_root = repo / "hud"
    if str(hud_root) not in sys.path:
        sys.path.insert(0, str(hud_root))
    import orion_hud_bridge as bridge

    fixture = Path(
        tempfile.mkdtemp(
            prefix="orion-p5-03c-stage-d-",
            dir=str(fixture_parent),
        )
    )
    passed = False
    print(f"P5_03C_STAGE_D_DISPOSABLE_FIXTURE={fixture}", flush=True)

    try:
        vault = fixture / "vault"
        inbox = fixture / "inbox"
        recovery = fixture / "recovery"
        vault.mkdir()
        inbox.mkdir()
        recovery.mkdir()

        note = vault / "reconnect-evidence.md"
        before_bytes = b"# P5-03C disposable reconnect\r\nbefore\r\n"
        after_text = (
            "# P5-03C disposable reconnect\r\n"
            "after fresh allow-once\r\n"
        )
        after_bytes = after_text.encode("utf-8")
        note.write_bytes(before_bytes)

        roots = {
            "ORION_VAULT_ROOT": str(vault),
            "ORION_INBOX_ROOT": str(inbox),
            plugin.RECOVERY_ROOT_ENV: str(recovery),
        }

        with env_scope({
            **roots,
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
            plugin.PRODUCTION_MUTATION_MODE_ENV: None,
            plugin.PRODUCTION_RECOVERY_ROOT_ENV: None,
            "HERMES_INTERACTIVE": "1",
            "HERMES_GATEWAY_SESSION": None,
            "HERMES_SESSION_PLATFORM": None,
            "HERMES_CRON_SESSION": None,
            "HERMES_SINGLE_QUERY_SESSION": None,
        }):
            resolved = plugin._candidate_disposable_roots()
            expected_roots = (
                vault.resolve(),
                inbox.resolve(),
                recovery.resolve(),
            )
            if tuple(path.resolve() for path in resolved) != expected_roots:
                raise RuntimeError("disposable_root_resolution_mismatch")

            preview = json.loads(plugin.preview_edit({
                "target_relative_path": "reconnect-evidence.md",
                "new_content": after_text,
            }))
            if (
                preview.get("success") is not True
                or preview.get("mutation_performed") is not False
            ):
                raise RuntimeError("disposable_preview_failed")

            from hermes_cli import lifecycle

            def route_hook(name, **fields):
                callback = ctx.hooks.get(name)
                if callback is None:
                    return []
                response = callback(**fields)
                return [] if response is None else [response]

            print("", flush=True)
            print("P5-03C STAGE D DISPOSABLE EDIT", flush=True)
            print(
                "At the Hermes approval prompt choose ALLOW ONCE.",
                flush=True,
            )
            print(
                "Do NOT choose session/always. DENY safely aborts the probe.",
                flush=True,
            )

            with patch.object(
                lifecycle,
                "invoke_hook",
                side_effect=route_hook,
            ):
                evidence = plugin._fresh_once_approval_evidence(
                    preview["plan_token"]
                )

            if evidence.get("approved") is not True:
                raise RuntimeError(
                    "fresh_allow_once_not_obtained:"
                    + str(evidence.get("error"))
                )
            if (
                evidence.get("choice") != "once"
                or evidence.get("authorization_reusable") is not False
                or evidence.get("plan_token") != preview["plan_token"]
            ):
                raise RuntimeError("fresh_approval_evidence_contract_mismatch")

            result = plugin._execute_disposable_plan_candidate(
                preview["plan_token"],
                approval_evidence=evidence,
                require_fresh_approval=True,
            )
            if (
                result.get("success") is not True
                or result.get("mutation_performed") is not True
                or result.get("recovery_required") is not False
            ):
                raise RuntimeError(
                    "disposable_edit_failed:"
                    + json.dumps(
                        {
                            "success": result.get("success"),
                            "mutation_performed": result.get("mutation_performed"),
                            "recovery_required": result.get("recovery_required"),
                            "error": result.get("error"),
                        },
                        sort_keys=True,
                    )
                )
            if note.read_bytes() != after_bytes:
                raise RuntimeError("disposable_edit_bytes_mismatch")

            recovery_dir = Path(result.get("recovery_dir") or "").resolve()
            try:
                recovery_dir.relative_to(recovery.resolve())
            except ValueError as exc:
                raise RuntimeError("recovery_record_escaped_disposable_root") from exc

            manifest = recovery_dir / "manifest.json"
            receipt = recovery_dir / "receipt.json"
            backup = recovery_dir / "original.bin"
            if not all(path.is_file() for path in (manifest, receipt, backup)):
                raise RuntimeError("committed_recovery_artifacts_missing")
            if backup.read_bytes() != before_bytes:
                raise RuntimeError("recovery_backup_mismatch")

            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
            if manifest_data.get("state") != "committed":
                raise RuntimeError("recovery_manifest_not_committed")
            if receipt_data.get("state") != "committed":
                raise RuntimeError("receipt_not_committed")
            if receipt_data.get("approval", {}).get("choice") != "once":
                raise RuntimeError("receipt_approval_choice_not_once")
            if (
                receipt_data.get("approval", {}).get("authorization_reusable")
                is not False
            ):
                raise RuntimeError("receipt_authorization_reusable")

            replay = plugin._execute_disposable_plan_candidate(
                preview["plan_token"],
                approval_evidence=evidence,
                require_fresh_approval=True,
            )
            if (
                replay.get("success") is not False
                or replay.get("error") not in {
                    "approval_evidence_already_consumed",
                    "plan_already_consumed",
                }
                or replay.get("mutation_performed") is not False
            ):
                raise RuntimeError("disposable_plan_replay_not_refused")
            if note.read_bytes() != after_bytes:
                raise RuntimeError("replay_changed_disposable_note")

            first, second = qualify_reconstruction(
                bridge,
                plugin,
                result,
            )
            if first != second:
                raise RuntimeError("reconstruction_changed_across_hud_restart")

            public_apply = ctx.tools[plugin.APPLY_TOOL]["handler"]({
                "plan_token": preview["plan_token"]
            })
            if isinstance(public_apply, str):
                public_apply = json.loads(public_apply)
            if (
                not isinstance(public_apply, dict)
                or public_apply.get("mutation_performed") is not False
            ):
                raise RuntimeError("registered_apply_not_fail_closed")

            print(
                "P5_03C_STAGE_D_DISPOSABLE_MUTATION_PERFORMED=true",
                flush=True,
            )
            print(
                f"P5_03C_STAGE_D_BEFORE_SHA256={sha256(before_bytes)}",
                flush=True,
            )
            print(
                f"P5_03C_STAGE_D_AFTER_SHA256={sha256(after_bytes)}",
                flush=True,
            )
            print("P5_03C_STAGE_D_APPROVAL_CHOICE=once", flush=True)
            print(
                "P5_03C_STAGE_D_AUTHORIZATION_REUSABLE=false",
                flush=True,
            )
            print("P5_03C_STAGE_D_RECOVERY_STATE=committed", flush=True)
            print("P5_03C_STAGE_D_RECEIPT_STATE=committed", flush=True)
            print("P5_03C_STAGE_D_REPLAY_REFUSED=true", flush=True)
            print(
                "P5_03C_STAGE_D_PROJECTED_STATE=succeeded",
                flush=True,
            )
            print(
                "P5_03C_STAGE_D_PROJECTED_DURABILITY=completed_record",
                flush=True,
            )
            print(
                "P5_03C_STAGE_D_CURRENT_RECOVERY_VISIBILITY=unavailable",
                flush=True,
            )
            print(
                "P5_03C_STAGE_D_HUD_RESTART_RECONSTRUCTION_MATCH=true",
                flush=True,
            )
            print(
                "P5_03C_STAGE_D_PRIVATE_PATH_EGRESS=false",
                flush=True,
            )
            print(
                "P5_03C_STAGE_D_LIVE_SESSIONDB_WRITTEN=false",
                flush=True,
            )
            print(
                "P5_03C_STAGE_D_PRODUCTION_MUTATION_MODE_PRESENT=false",
                flush=True,
            )
            print(
                "P5_03C_STAGE_D_REAL_VAULT_INBOX_TOUCHED=false",
                flush=True,
            )

        passed = True
        return 0
    finally:
        if passed:
            shutil.rmtree(fixture)
            print(
                "P5_03C_STAGE_D_DISPOSABLE_FIXTURE_CLEANED=true",
                flush=True,
            )
            print("P5_03C_STAGE_D_QUALIFICATION=PASS", flush=True)
        else:
            print(
                "P5_03C_STAGE_D_QUALIFICATION=FAIL; "
                f"FIXTURE_PRESERVED={fixture}",
                file=sys.stderr,
                flush=True,
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print(
            "P5_03C_STAGE_D_QUALIFICATION=ABORTED",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(130)
    except Exception as exc:
        print(
            "P5_03C_STAGE_D_QUALIFICATION=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
