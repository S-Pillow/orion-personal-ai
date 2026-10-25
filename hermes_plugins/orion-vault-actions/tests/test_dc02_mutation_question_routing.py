from __future__ import annotations

import importlib.util
import json
import sys
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

    def test_question_about_renaming_notes_still_retrieves(self):
        calls = []

        def fake_retriever(params):
            calls.append(dict(params))
            return json.dumps({
                "success": True,
                "retrieval_count": 1,
                "sources": [{
                    "source_relative_path": "Note Workflow.md",
                    "source_sha256": "a" * 64,
                    "record_id": "r1",
                    "content": "Rename notes only after checking backlinks.",
                }],
                "mutation_performed": False,
            })

        original = plugin._get_retriever_handler
        plugin._get_retriever_handler = lambda: fake_retriever
        self.addCleanup(setattr, plugin, "_get_retriever_handler", original)

        ctx = FakeContext([
            {"ok": True, "result": {"hits": [{"record_id": "r1", "score": 0.82}]}}
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
        self.assertEqual(len(calls), 1)

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
