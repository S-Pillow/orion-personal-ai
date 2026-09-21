"""Source-only approval-plan regression tests using disposable roots."""

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
SPEC = importlib.util.spec_from_file_location("orion_vault_actions_p502a", PLUGIN_DIR / "__init__.py")
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class PlanBindingTests(unittest.TestCase):
    def setUp(self):
        plugin._PREVIEWS.clear()
        plugin._PREVIEW_TIMES.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.inbox = self.root / "inbox"
        self.vault.mkdir()
        self.inbox.mkdir()
        self.old_vault = os.environ.get("ORION_VAULT_ROOT")
        self.old_inbox = os.environ.get("ORION_INBOX_ROOT")
        os.environ["ORION_VAULT_ROOT"] = str(self.vault)
        os.environ["ORION_INBOX_ROOT"] = str(self.inbox)

    def tearDown(self):
        for key, previous in (("ORION_VAULT_ROOT", self.old_vault),
                              ("ORION_INBOX_ROOT", self.old_inbox)):
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        self.tmp.cleanup()

    def test_identical_edits_get_fresh_rule_keys_and_exact_diff(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old")
        params = {"target_relative_path": "note.md", "new_content": "new"}
        first = json.loads(plugin.preview_edit(params))
        second = json.loads(plugin.preview_edit(params))

        self.assertNotEqual(first["plan_token"], second["plan_token"])
        self.assertNotEqual(first["plan"]["preview_nonce"], second["plan"]["preview_nonce"])
        self.assertEqual(plugin._PREVIEWS[first["plan_token"]]["_proposed_bytes"], b"new")
        self.assertEqual(plugin._PREVIEWS[second["plan_token"]]["_approval_diff"], second["diff"])

        approvals = [plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": item["plan_token"]})
                     for item in (first, second)]
        for item, approval in zip((first, second), approvals):
            self.assertEqual(approval["action"], "approve")
            self.assertIn(item["plan"]["target_canonical_path"], approval["message"])
            self.assertIn(item["diff"], approval["message"])
        self.assertNotEqual(approvals[0]["rule_key"], approvals[1]["rule_key"])
        self.assertEqual(note.read_bytes(), b"old")
        self.assertFalse(json.loads(plugin.apply_plan_placeholder(
            {"plan_token": first["plan_token"]}))["mutation_performed"])

    def test_move_approval_shows_canonical_target_and_bound_source_bytes(self):
        draft = self.inbox / "draft.md"
        draft_bytes = b"---\r\norion_draft: true\r\nstatus: draft\r\n---\r\nbody"
        draft.write_bytes(draft_bytes)
        target = self.vault / "New" / "draft.md"
        preview = json.loads(plugin.preview_move_draft({
            "source_draft": "draft.md", "target_relative_path": "New/draft.md",
        }))
        directive = plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": preview["plan_token"]})
        self.assertEqual(directive["action"], "approve")
        self.assertEqual(preview["plan"]["target_canonical_path"], str(target.resolve(strict=False)))
        self.assertIn(preview["plan"]["target_canonical_path"], directive["message"])
        self.assertIn(preview["diff"], directive["message"])
        self.assertEqual(plugin._PREVIEWS[preview["plan_token"]]["_proposed_bytes"], draft_bytes)
        self.assertEqual(draft.read_bytes(), draft_bytes)
        self.assertFalse(target.exists())

    def test_missing_diff_and_hook_exception_block_without_mutation(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "new\n",
        }))
        token = preview["plan_token"]
        plugin._PREVIEWS[token].pop("_approval_diff")
        self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        plugin._PREVIEWS[token]["_approval_diff"] = preview["diff"] + "unexpected"
        self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        plugin._PREVIEWS[token]["_approval_diff"] = preview["diff"]
        plugin._PREVIEWS[token]["_proposed_bytes"] = b"different\n"
        self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        with patch.object(plugin, "_lookup_preview", side_effect=RuntimeError("cache unavailable")):
            self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        self.assertEqual(note.read_bytes(), b"old\n")

    def test_oversized_approval_payload_blocks_and_apply_still_refuses(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "x" * 17000,
        }))
        token = preview["plan_token"]
        self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        result = json.loads(plugin.apply_plan_placeholder({"plan_token": token}))
        self.assertEqual(result["error"], "p5_01_mutation_not_authorized")
        self.assertEqual(note.read_bytes(), b"old\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
