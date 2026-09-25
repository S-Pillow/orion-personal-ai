"""Exercise the Orion once-only candidate through installed Hermes dispatch.

Run explicitly in the Hermes venv. A synthetic test-only tool is registered in
this process, using disposable roots; the plugin's real apply tool is not
registered or invoked. Every handler returns a boolean and writes no files.
The prompt callback supplies a simulated answer, so no user prompt is sent.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import model_tools
from hermes_cli import lifecycle
from tools import approval
from tools.registry import registry


PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("orion_dispatch_probe_plugin", PLUGIN_DIR / "__init__.py")
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)

PROBE_TOOL = "orion_vault_isolated_approval_probe"


class Context:
    def __init__(self):
        self.hooks = {}

    def register_tool(self, **_kwargs):
        pass  # Never register the real apply tool in the isolated dispatcher.

    def register_hook(self, name, callback):
        self.hooks[name] = callback


class HermesDispatchProbe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.vault, self.inbox = base / "vault", base / "inbox"
        self.vault.mkdir()
        self.inbox.mkdir()
        self.note = self.vault / "note.md"
        self.note.write_bytes(b"old\n")
        self.env = patch.dict(os.environ, {
            "ORION_VAULT_ROOT": str(self.vault),
            "ORION_INBOX_ROOT": str(self.inbox),
        })
        self.env.start()
        plugin._PREVIEWS.clear()
        plugin._PREVIEW_TIMES.clear()
        plugin._APPROVAL_ATTEMPTS.clear()
        self.token = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "new\n",
        }))["plan_token"]
        self.ctx = Context()
        plugin.register(self.ctx)
        self.previous = registry.snapshot_registration(PROBE_TOOL)

        def probe_handler(args, **_kwargs):
            allowed = plugin._probe_fresh_once_approval(args["plan_token"])
            return json.dumps({"fresh_once": allowed, "mutation_performed": False})

        registry.register(
            name=PROBE_TOOL,
            toolset="orion_vault_probe",
            schema={"name": PROBE_TOOL, "description": "Isolated no-write approval probe",
                    "parameters": {"type": "object", "properties": {
                        "plan_token": {"type": "string"}}, "required": ["plan_token"]}},
            handler=probe_handler,
        )
        self.current = registry.snapshot_registration(PROBE_TOOL)
        if self.current is None:
            raise AssertionError("synthetic probe tool was not registered")

    def tearDown(self):
        registry.restore_registration(PROBE_TOOL, self.current, self.previous)
        self.env.stop()
        self.tmp.cleanup()

    def _call(self, *, choice="once", yolo=False, observer_fails=False, dispatch_fails=False):
        def route_hook(name, **fields):
            if observer_fails and name == "post_approval_response":
                raise RuntimeError("simulated observer failure")
            cb = self.ctx.hooks.get(name)
            if cb is None:
                return []
            result = cb(**fields)
            return [] if result is None else [result]

        with ExitStack() as stack:
            for item in (
                patch.object(lifecycle, "invoke_hook", side_effect=route_hook),
                patch.object(approval, "_YOLO_MODE_FROZEN", False),
                patch.object(approval, "is_current_session_yolo_enabled", return_value=yolo),
                patch.object(approval, "is_approved", return_value=False),
                patch.object(approval, "get_current_session_key", return_value="orion-probe"),
                patch.object(approval, "_is_interactive_cli", return_value=True),
                patch.object(approval, "_is_gateway_approval_context", return_value=False),
                patch.object(approval, "_is_single_query_approval_context", return_value=False),
                patch.object(approval, "_is_cron_approval_context", return_value=False),
                patch.object(approval, "approve_session"),
                patch.object(approval, "approve_permanent"),
                patch.object(approval, "save_permanent_allowlist"),
                patch("tools.terminal_tool._get_approval_callback",
                      return_value=lambda *_args, **_kwargs: choice),
            ):
                stack.enter_context(item)
            if dispatch_fails:
                stack.enter_context(patch(
                    "hermes_cli.plugins._dispatch_pre_tool_call_hooks",
                    side_effect=RuntimeError("simulated pre-dispatch failure"),
                ))
            raw = model_tools.handle_function_call(
                PROBE_TOOL, {"plan_token": self.token},
                task_id="orion-probe", session_id="orion-probe",
                tool_call_id="orion-probe-call",
                enabled_tools=[PROBE_TOOL],
                skip_tool_request_middleware=True,
                skip_tool_execution_middleware=True,
            )
        self.assertEqual(self.note.read_bytes(), b"old\n")
        self.assertFalse(plugin._APPROVAL_ATTEMPTS)
        return json.loads(raw)

    def test_dispatch_requires_once_and_refuses_bypass_or_missing_observer(self):
        self.assertEqual(self._call()["fresh_once"], True)
        for kwargs in ({"choice": "session"}, {"yolo": True},
                       {"observer_fails": True}):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self._call(**kwargs)["fresh_once"], False)

    def test_pre_dispatch_failure_cannot_replace_handler_side_approval(self):
        self.assertEqual(self._call(dispatch_fails=True, yolo=True)["fresh_once"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
