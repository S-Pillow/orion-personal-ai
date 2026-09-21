"""P5-02B disposable mutation candidate tests.

These tests opt into the private source-only executor with temporary roots.
The registered Hermes apply tool remains the P5-01 refusing placeholder.
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
    "orion_vault_actions_p502b", PLUGIN_DIR / "__init__.py"
)
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class DisposableMutationCandidateTests(unittest.TestCase):
    def setUp(self):
        plugin._PREVIEWS.clear()
        plugin._PREVIEW_TIMES.clear()
        plugin._APPROVAL_ATTEMPTS.clear()
        plugin._CANDIDATE_CONSUMED_PLANS.clear()

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

    def _edit_preview(self, before=b"before\n", after="after\n"):
        note = self.vault / "note.md"
        note.write_bytes(before)
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": after,
        }))
        self.assertTrue(preview["success"])
        return note, preview

    def _draft_preview(self, target="Folder/draft.md"):
        (self.vault / "Folder").mkdir(exist_ok=True)
        draft = self.inbox / "draft.md"
        draft.write_bytes(
            b"---\r\norion_draft: true\r\nstatus: draft\r\n---\r\nbody"
        )
        preview = json.loads(plugin.preview_move_draft({
            "source_draft": "draft.md",
            "target_relative_path": target,
        }))
        self.assertTrue(preview["success"])
        return draft, self.vault / Path(target), preview

    def test_candidate_rejects_live_default_root_identity(self):
        with patch.dict(os.environ, {
            "ORION_VAULT_ROOT": plugin.DEFAULT_VAULT_ROOT,
            "ORION_INBOX_ROOT": str(self.inbox),
            plugin.RECOVERY_ROOT_ENV: str(self.recovery),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
        }):
            with self.assertRaisesRegex(RuntimeError, "live_vault_root_overlap_rejected"):
                plugin._candidate_disposable_roots()

    def test_candidate_rejects_ancestor_descendant_overlap_with_live_roots(self):
        cases = [
            ("ORION_VAULT_ROOT", r"C:\\Personal", "live_vault_root_overlap_rejected"),
            ("ORION_VAULT_ROOT", r"C:\\Personal\\Me\\fixture", "live_vault_root_overlap_rejected"),
            ("ORION_INBOX_ROOT", r"C:\\Personal", "live_inbox_root_overlap_rejected"),
            ("ORION_INBOX_ROOT", r"C:\\Personal\\Orion-Inbox\\fixture", "live_inbox_root_overlap_rejected"),
            (plugin.RECOVERY_ROOT_ENV, r"C:\\Personal\\Me\\recovery", "live_recovery_root_overlap_rejected"),
        ]
        base = {
            "ORION_VAULT_ROOT": str(self.vault),
            "ORION_INBOX_ROOT": str(self.inbox),
            plugin.RECOVERY_ROOT_ENV: str(self.recovery),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
        }
        for key, value, error in cases:
            with self.subTest(key=key, value=value):
                env = dict(base)
                env[key] = value
                with patch.dict(os.environ, env):
                    with self.assertRaisesRegex(RuntimeError, error):
                        plugin._candidate_disposable_roots()

    def test_candidate_requires_recovery_root_disjoint_from_data_roots(self):
        nested = self.vault / "recovery"
        nested.mkdir()
        with patch.dict(os.environ, {
            "ORION_VAULT_ROOT": str(self.vault),
            "ORION_INBOX_ROOT": str(self.inbox),
            plugin.RECOVERY_ROOT_ENV: str(nested),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
        }):
            with self.assertRaisesRegex(RuntimeError, "recovery_root_must_be_disjoint"):
                plugin._candidate_disposable_roots()

    def test_candidate_is_not_registered_and_requires_disposable_opt_in(self):
        class Context:
            def __init__(self):
                self.tools = {}

            def register_tool(self, *, name, handler, **_kwargs):
                self.tools[name] = handler

            def register_hook(self, *_args, **_kwargs):
                pass

        ctx = Context()
        plugin.register(ctx)
        self.assertIs(ctx.tools[plugin.APPLY_TOOL], plugin.apply_plan_placeholder)

        note, preview = self._edit_preview()
        with patch.dict(os.environ, {plugin.DISPOSABLE_MUTATION_FLAG: "0"}):
            result = plugin._execute_disposable_plan_candidate(
                preview["plan_token"]
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "disposable_mutation_not_enabled")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"before\n")

    def test_edit_commit_creates_recovery_and_replay_fails(self):
        note, preview = self._edit_preview()
        token = preview["plan_token"]

        result = plugin._execute_disposable_plan_candidate(token)

        self.assertTrue(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"after\n")
        recovery = Path(result["recovery_dir"])
        self.assertEqual((recovery / "original.bin").read_bytes(), b"before\n")
        manifest = json.loads((recovery / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "committed")
        self.assertEqual(manifest["plan_token"], token)

        replay = plugin._execute_disposable_plan_candidate(token)
        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "plan_already_consumed")
        self.assertEqual(note.read_bytes(), b"after\n")

    def test_edit_stale_hash_fails_before_recovery_or_mutation(self):
        note, preview = self._edit_preview()
        note.write_bytes(b"external change\n")

        result = plugin._execute_disposable_plan_candidate(preview["plan_token"])

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "stale_original_hash")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"external change\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_edit_failure_after_replace_preserves_original_recovery_bytes(self):
        note, preview = self._edit_preview()

        def fail(name):
            if name == "edit_after_replace":
                raise RuntimeError("simulated crash window")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(note.read_bytes(), b"after\n")
        recovery = Path(result["recovery_dir"])
        self.assertEqual((recovery / "original.bin").read_bytes(), b"before\n")
        self.assertEqual(
            json.loads((recovery / "manifest.json").read_text(encoding="utf-8"))["state"],
            "prepared",
        )

    def test_move_commit_is_exclusive_verified_and_replay_fails(self):
        draft, target, preview = self._draft_preview()
        source_bytes = draft.read_bytes()

        result = plugin._execute_disposable_plan_candidate(preview["plan_token"])

        self.assertTrue(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertFalse(draft.exists())
        self.assertEqual(target.read_bytes(), source_bytes)
        recovery = Path(result["recovery_dir"])
        self.assertEqual((recovery / "source.bin").read_bytes(), source_bytes)
        self.assertEqual(
            json.loads((recovery / "manifest.json").read_text(encoding="utf-8"))["state"],
            "committed",
        )

        replay = plugin._execute_disposable_plan_candidate(preview["plan_token"])
        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "plan_already_consumed")
        self.assertEqual(target.read_bytes(), source_bytes)

    def test_move_target_race_fails_without_touching_source(self):
        draft, target, preview = self._draft_preview()
        source_bytes = draft.read_bytes()
        target.write_bytes(b"someone else won\n")

        result = plugin._execute_disposable_plan_candidate(preview["plan_token"])

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "target_already_exists")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        self.assertEqual(target.read_bytes(), b"someone else won\n")

    def test_move_source_change_after_target_create_cleans_our_target(self):
        draft, target, preview = self._draft_preview()

        def change_source(name):
            if name == "move_after_target_create":
                draft.write_bytes(b"external source change\n")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=change_source
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "source_changed_before_delete")
        self.assertTrue(result["mutation_performed"])
        self.assertFalse(result["recovery_required"])
        self.assertEqual(draft.read_bytes(), b"external source change\n")
        self.assertFalse(target.exists())
        self.assertTrue(Path(result["recovery_dir"], "source.bin").is_file())

    def test_move_failure_before_source_delete_reports_recovery_state(self):
        draft, target, preview = self._draft_preview()
        source_bytes = draft.read_bytes()

        def fail(name):
            if name == "move_before_source_delete":
                raise RuntimeError("simulated interruption")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], failure_hook=fail
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        self.assertEqual(target.read_bytes(), source_bytes)
        self.assertTrue(Path(result["recovery_dir"], "source.bin").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
