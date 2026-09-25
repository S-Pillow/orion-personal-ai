"""P5-02I stricter disposable approval-consumption tests.

The legacy disposable executor keeps its historical source-test behavior by
default. P5-02I qualification opts into require_fresh_approval=True, which
must consume a fresh approval attempt before post-approval stale checks.
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
    "orion_vault_actions_p502i_approval", PLUGIN_DIR / "__init__.py"
)
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class DisposableApprovalConsumptionTests(unittest.TestCase):
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

        self.env = patch.dict(os.environ, {
            "ORION_VAULT_ROOT": str(self.vault),
            "ORION_INBOX_ROOT": str(self.inbox),
            plugin.RECOVERY_ROOT_ENV: str(self.recovery),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _fresh_once_evidence(self, plan_token):
        def gate(_tool_name, description, *, rule_key):
            plugin.post_approval_response(
                pattern_key=f"plugin_rule:{rule_key}",
                description=description,
                choice="once",
                surface="gateway",
            )
            return {"approved": True}

        evidence = plugin._fresh_once_approval_evidence(
            plan_token,
            approval_request=gate,
            redact=lambda text: text,
        )
        self.assertTrue(evidence["approved"])
        return evidence

    def _edit_preview(self):
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))
        self.assertTrue(preview["success"])
        return note, preview

    def _move_preview(self):
        (self.vault / "Folder").mkdir(exist_ok=True)
        draft = self.inbox / "draft.md"
        source_bytes = (
            b"---\r\n"
            b"orion_draft: true\r\n"
            b"status: draft\r\n"
            b"---\r\n"
            b"body\r\n"
        )
        draft.write_bytes(source_bytes)
        target = self.vault / "Folder" / "draft.md"
        preview = json.loads(plugin.preview_move_draft({
            "source_draft": "draft.md",
            "target_relative_path": "Folder/draft.md",
        }))
        self.assertTrue(preview["success"])
        return draft, target, source_bytes, preview

    def test_required_mode_refuses_missing_approval_before_recovery(self):
        note, preview = self._edit_preview()

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"],
            require_fresh_approval=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "approval_evidence_required")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"before\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_stale_edit_consumes_approval_and_same_evidence_cannot_revive(self):
        note, preview = self._edit_preview()
        evidence = self._fresh_once_evidence(preview["plan_token"])

        note.write_bytes(b"external change\n")
        stale = plugin._execute_disposable_plan_candidate(
            preview["plan_token"],
            approval_evidence=evidence,
            require_fresh_approval=True,
        )

        self.assertFalse(stale["success"])
        self.assertEqual(stale["error"], "stale_original_hash")
        self.assertFalse(stale["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"external change\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

        # Returning to the previewed bytes must not revive the prior human once.
        note.write_bytes(b"before\n")
        replay = plugin._execute_disposable_plan_candidate(
            preview["plan_token"],
            approval_evidence=evidence,
            require_fresh_approval=True,
        )

        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "approval_evidence_already_consumed")
        self.assertFalse(replay["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"before\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_move_target_race_consumes_approval_and_same_evidence_cannot_revive(self):
        draft, target, source_bytes, preview = self._move_preview()
        evidence = self._fresh_once_evidence(preview["plan_token"])

        target.write_bytes(b"someone else won\n")
        stale = plugin._execute_disposable_plan_candidate(
            preview["plan_token"],
            approval_evidence=evidence,
            require_fresh_approval=True,
        )

        self.assertFalse(stale["success"])
        self.assertEqual(stale["error"], "target_already_exists")
        self.assertFalse(stale["mutation_performed"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        self.assertEqual(target.read_bytes(), b"someone else won\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

        target.unlink()
        replay = plugin._execute_disposable_plan_candidate(
            preview["plan_token"],
            approval_evidence=evidence,
            require_fresh_approval=True,
        )

        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "approval_evidence_already_consumed")
        self.assertFalse(replay["mutation_performed"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_mismatched_evidence_refuses_before_recovery_or_mutation(self):
        first_note, first = self._edit_preview()
        evidence = self._fresh_once_evidence(first["plan_token"])

        second_note = self.vault / "second.md"
        second_note.write_bytes(b"two-before\n")
        second = json.loads(plugin.preview_edit({
            "target_relative_path": "second.md",
            "new_content": "two-after\n",
        }))
        self.assertTrue(second["success"])

        result = plugin._execute_disposable_plan_candidate(
            second["plan_token"],
            approval_evidence=evidence,
            require_fresh_approval=True,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "approval_evidence_invalid")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(first_note.read_bytes(), b"before\n")
        self.assertEqual(second_note.read_bytes(), b"two-before\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_required_mode_valid_once_commits_and_replay_refuses(self):
        note, preview = self._edit_preview()
        evidence = self._fresh_once_evidence(preview["plan_token"])

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"],
            approval_evidence=evidence,
            require_fresh_approval=True,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"after\n")

        replay = plugin._execute_disposable_plan_candidate(
            preview["plan_token"],
            approval_evidence=evidence,
            require_fresh_approval=True,
        )
        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "plan_already_consumed")
        self.assertEqual(note.read_bytes(), b"after\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
