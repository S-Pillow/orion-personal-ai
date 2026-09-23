"""P5-02N guarded public apply registration tests.

Source-only tests. They do not install the plugin, start Hermes, change the
COMPANION profile, or touch production vault/inbox/recovery content.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "orion_vault_actions_p502n", PLUGIN_DIR / "__init__.py"
)
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class Context:
    def __init__(self):
        self.tools = {}
        self.schemas = {}
        self.hooks = {}

    def register_tool(self, *, name, schema, handler, **_kwargs):
        self.tools[name] = handler
        self.schemas[name] = schema

    def register_hook(self, name, callback):
        self.hooks[name] = callback


class GuardedRegistrationTests(unittest.TestCase):
    def setUp(self):
        plugin._PREVIEWS.clear()
        plugin._PREVIEW_TIMES.clear()
        plugin._APPROVAL_ATTEMPTS.clear()
        plugin._CANDIDATE_CONSUMED_PLANS.clear()
        plugin._CANDIDATE_CONSUMED_APPROVAL_ATTEMPTS.clear()

        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.inbox = self.root / "inbox"
        self.recovery = self.root / "recovery"
        for path in (self.vault, self.inbox, self.recovery):
            path.mkdir()

        self.env = patch.dict(
            os.environ,
            {
                "ORION_VAULT_ROOT": str(self.vault),
                "ORION_INBOX_ROOT": str(self.inbox),
                plugin.PRODUCTION_RECOVERY_ROOT_ENV: str(self.recovery),
            },
            clear=False,
        )
        self.env.start()
        os.environ.pop(plugin.PRODUCTION_MUTATION_MODE_ENV, None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _edit_preview(self):
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(
            plugin.preview_edit(
                {
                    "target_relative_path": "note.md",
                    "new_content": "after\n",
                }
            )
        )
        self.assertTrue(preview["success"])
        return note, preview

    def test_registration_uses_guarded_wrapper_and_plan_token_only_schema(self):
        ctx = Context()
        plugin.register(ctx)

        self.assertEqual(len(ctx.tools), 4)
        self.assertEqual(
            set(ctx.hooks), {"pre_tool_call", "post_approval_response"}
        )
        self.assertIs(
            ctx.tools[plugin.APPLY_TOOL], plugin.apply_plan_production_guarded
        )
        self.assertNotIn(
            plugin._execute_production_plan_candidate, ctx.tools.values()
        )

        parameters = ctx.schemas[plugin.APPLY_TOOL]["parameters"]
        self.assertEqual(set(parameters["properties"]), {"plan_token"})
        self.assertEqual(parameters["required"], ["plan_token"])
        self.assertIs(parameters["additionalProperties"], False)

        manifest = (PLUGIN_DIR / "plugin.yaml").read_text(encoding="utf-8")
        self.assertIn('version: "0.2.0"', manifest)
        self.assertIn("guarded vault preview and apply plugin", manifest)

    def test_non_enabled_and_invalid_modes_refuse_before_executor(self):
        note, preview = self._edit_preview()
        token = preview["plan_token"]

        cases = (
            (None, "production_mutation_not_enabled"),
            (plugin.PRODUCTION_MODE_DISABLED, "production_mutation_not_enabled"),
            (
                plugin.PRODUCTION_MODE_PREVIEW_ONLY,
                "production_mutation_not_enabled",
            ),
            ("go-fast", "invalid_production_mutation_mode"),
        )

        for raw_mode, expected_error in cases:
            if raw_mode is None:
                os.environ.pop(plugin.PRODUCTION_MUTATION_MODE_ENV, None)
            else:
                os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = raw_mode

            with patch.object(
                plugin,
                "_execute_production_plan_candidate",
                side_effect=AssertionError("executor must not run"),
            ):
                result = json.loads(
                    plugin.apply_plan_production_guarded(
                        {
                            "plan_token": token,
                            "approval_request": "caller-controlled",
                            "recovery_root": "caller-controlled",
                            "proposed_bytes": "caller-controlled",
                        }
                    )
                )

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], expected_error)
            self.assertFalse(result["mutation_performed"])
            self.assertEqual(note.read_bytes(), b"before\n")
            self.assertEqual(list(self.recovery.iterdir()), [])

    def test_pretool_blocks_without_approval_until_mutation_enabled(self):
        _note, preview = self._edit_preview()
        token = preview["plan_token"]

        for raw_mode in (
            None,
            plugin.PRODUCTION_MODE_DISABLED,
            plugin.PRODUCTION_MODE_PREVIEW_ONLY,
            "go-fast",
        ):
            if raw_mode is None:
                os.environ.pop(plugin.PRODUCTION_MUTATION_MODE_ENV, None)
            else:
                os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = raw_mode
            directive = plugin.pre_tool_call(
                plugin.APPLY_TOOL, {"plan_token": token}
            )
            self.assertEqual(directive["action"], "block")
            self.assertNotIn("rule_key", directive)

        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        self.assertIsNone(
            plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})
        )

    def test_mutation_enabled_wrapper_delegates_only_plan_token_once(self):
        _note, preview = self._edit_preview()
        token = preview["plan_token"]
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        calls = []

        def fake_executor(plan_token, **kwargs):
            calls.append((plan_token, kwargs))
            return {
                "success": False,
                "error": "probe_stop",
                "mutation_performed": False,
            }

        with patch.object(
            plugin, "_execute_production_plan_candidate", fake_executor
        ):
            result = json.loads(
                plugin.apply_plan_production_guarded(
                    {
                        "plan_token": token,
                        "approval_request": "must_be_ignored",
                        "redact": "must_be_ignored",
                        "failure_hook": "must_be_ignored",
                        "local_fs_probe": "must_be_ignored",
                        "acl_probe": "must_be_ignored",
                        "access_probe": "must_be_ignored",
                        "recovery_root": "must_be_ignored",
                        "proposed_bytes": "must_be_ignored",
                    }
                )
            )

        self.assertEqual(calls, [(token, {})])
        self.assertEqual(result["error"], "probe_stop")
        self.assertNotIn("approval_request", result)
        self.assertNotIn("proposed_bytes", result)

    def test_missing_plan_token_cannot_inject_callbacks(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        seen = []

        def fake_executor(plan_token, **kwargs):
            seen.append((plan_token, kwargs))
            return {
                "success": False,
                "error": "unknown_or_expired_plan",
                "mutation_performed": False,
            }

        with patch.object(
            plugin, "_execute_production_plan_candidate", fake_executor
        ):
            result = json.loads(
                plugin.apply_plan_production_guarded(
                    {
                        "approval_request": "caller-controlled",
                        "failure_hook": "caller-controlled",
                    }
                )
            )

        self.assertEqual(seen, [("", {})])
        self.assertEqual(result["error"], "unknown_or_expired_plan")
        self.assertFalse(result["mutation_performed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
