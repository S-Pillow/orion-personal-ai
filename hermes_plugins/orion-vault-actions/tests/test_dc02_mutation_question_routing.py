from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[2] / "orion-vault-recall-injector"
SPEC = importlib.util.spec_from_file_location(
    "orion_vault_recall_injector_dc02_mutation_question",
    PLUGIN_DIR / "__init__.py",
)
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class FakeContext:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.hooks = {}
        self.mcp_calls = []

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def call_mcp(self, server, tool, arguments=None, timeout=30):
        self.mcp_calls.append((server, tool, dict(arguments or {}), timeout))
        if not self.responses:
            raise AssertionError("unexpected MCP call")
        return self.responses.pop(0)


class DC02MutationQuestionRoutingTests(unittest.TestCase):
    def setUp(self):
        plugin._INFLIGHT = None
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        self.vault.mkdir()
        self.old_vault = os.environ.get("ORION_VAULT_ROOT")
        os.environ["ORION_VAULT_ROOT"] = str(self.vault)

    def tearDown(self):
        if self.old_vault is None:
            os.environ.pop("ORION_VAULT_ROOT", None)
        else:
            os.environ["ORION_VAULT_ROOT"] = self.old_vault
        self.tmp.cleanup()

    def test_question_about_renaming_notes_still_retrieves(self):
        surface = "Rename notes only after checking backlinks and confirming the destination. " * 2
        (self.vault / "Note Workflow.md").write_text(surface, encoding="utf-8")
        ctx = FakeContext([
            {
                "ok": True,
                "result": {
                    "hits": [{
                        "record_id": "r1",
                        "score": 0.82,
                        "literal_surface": surface,
                        "session_id": plugin.VAULT_STUDY_SESSION_ID,
                    }]
                },
            }
        ])
        plugin.register(ctx)
        result = ctx.hooks["pre_llm_call"](
            user_message="What did I write about how to rename a note?",
            conversation_history=[],
        )

        self.assertIsNotNone(result)
        self.assertIn('status="relevant"', result["context"])
        self.assertIn("Note Workflow.md", result["context"])
        self.assertEqual(len(ctx.mcp_calls), 1)

    def test_actual_rename_request_still_bypasses_automatic_recall(self):
        ctx = FakeContext([])
        plugin.register(ctx)
        result = ctx.hooks["pre_llm_call"](
            user_message="Please rename the note Note Workflow.md to Note Process.md.",
            conversation_history=[],
        )

        self.assertIsNone(result)
        self.assertEqual(ctx.mcp_calls, [])


if __name__ == "__main__":
    unittest.main()
