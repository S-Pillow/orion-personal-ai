"""P5-02E private disposable restore-execution candidate tests.

These tests use only temporary disposable roots. The registered Hermes apply
tool remains the refusing placeholder; the restore executor is private and
unregistered.
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
    "orion_vault_actions_p502e", PLUGIN_DIR / "__init__.py"
)
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class DisposableRestoreExecutionTests(unittest.TestCase):
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

    def _fresh_once_evidence(self, plan_token, surface="gateway"):
        def gate(_tool_name, description, *, rule_key):
            plugin.post_approval_response(
                pattern_key=f"plugin_rule:{rule_key}",
                description=description,
                choice="once",
                surface=surface,
            )
            return {"approved": True}

        evidence = plugin._fresh_once_approval_evidence(
            plan_token, approval_request=gate, redact=lambda text: text,
        )
        self.assertTrue(evidence["approved"])
        return evidence

    def _edit_origin(self):
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))
        self.assertTrue(preview["success"])
        evidence = self._fresh_once_evidence(preview["plan_token"])
        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], approval_evidence=evidence
        )
        self.assertTrue(result["success"])
        self.assertEqual(note.read_bytes(), b"after\n")
        return note, preview, result, evidence

    def _move_origin(self):
        (self.vault / "Folder").mkdir(exist_ok=True)
        draft = self.inbox / "draft.md"
        source_bytes = (
            b"---\r\norion_draft: true\r\nstatus: draft\r\n---\r\nbody"
        )
        draft.write_bytes(source_bytes)
        target = self.vault / "Folder" / "draft.md"
        preview = json.loads(plugin.preview_move_draft({
            "source_draft": "draft.md",
            "target_relative_path": "Folder/draft.md",
        }))
        self.assertTrue(preview["success"])
        evidence = self._fresh_once_evidence(preview["plan_token"])
        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"], approval_evidence=evidence
        )
        self.assertTrue(result["success"])
        self.assertFalse(draft.exists())
        self.assertEqual(target.read_bytes(), source_bytes)
        return draft, target, source_bytes, preview, result, evidence

    def _snapshot_tree(self, root):
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def _edit_restore_preview(self):
        note, origin, origin_result, origin_evidence = self._edit_origin()
        restore = plugin._preview_disposable_restore_candidate(
            origin["plan_token"]
        )
        self.assertTrue(restore["success"])
        self.assertEqual(restore["plan"]["action"], "restore_edit")
        return note, origin, origin_result, origin_evidence, restore

    def _move_restore_preview(self):
        draft, target, source_bytes, origin, origin_result, origin_evidence = (
            self._move_origin()
        )
        restore = plugin._preview_disposable_restore_candidate(
            origin["plan_token"]
        )
        self.assertTrue(restore["success"])
        self.assertEqual(
            restore["plan"]["action"], "restore_move_source"
        )
        return (
            draft, target, source_bytes, origin, origin_result,
            origin_evidence, restore,
        )

    def test_restore_executor_is_private_and_public_apply_still_refuses(self):
        class Context:
            def __init__(self):
                self.tools = {}

            def register_tool(self, *, name, handler, **_kwargs):
                self.tools[name] = handler

            def register_hook(self, *_args, **_kwargs):
                pass

        ctx = Context()
        plugin.register(ctx)
        self.assertIs(
            ctx.tools[plugin.APPLY_TOOL], plugin.apply_plan_production_guarded
        )
        self.assertNotIn(
            plugin._execute_disposable_restore_candidate, ctx.tools.values()
        )

        note, _origin, _origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        result = json.loads(plugin.apply_plan_production_guarded({
            "plan_token": restore["plan_token"]
        }))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "production_mutation_not_enabled")
        self.assertEqual(note.read_bytes(), b"after\n")

    def test_restore_edit_requires_fresh_approval_evidence(self):
        note, _origin, _origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=None
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "approval_evidence_required")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"after\n")
        self.assertFalse((self.recovery / restore["plan_token"]).exists())

    def test_originating_approval_evidence_cannot_authorize_restore(self):
        note, _origin, _origin_result, origin_evidence, restore = (
            self._edit_restore_preview()
        )

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=origin_evidence
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "approval_evidence_invalid")
        self.assertEqual(note.read_bytes(), b"after\n")
        self.assertFalse((self.recovery / restore["plan_token"]).exists())

    def test_restore_edit_commit_creates_independent_recovery_and_receipt(self):
        note, origin, origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        origin_dir = Path(origin_result["recovery_dir"])
        origin_snapshot = self._snapshot_tree(origin_dir)
        evidence = self._fresh_once_evidence(restore["plan_token"])

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"before\n")
        self.assertEqual(result["recovery_id"], restore["plan_token"])
        self.assertNotEqual(result["recovery_id"], origin["plan_token"])

        recovery = Path(result["recovery_dir"])
        self.assertEqual((recovery / "before_restore.bin").read_bytes(), b"after\n")
        manifest = json.loads(
            (recovery / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["state"], "committed")
        self.assertEqual(manifest["action"], "restore_edit")
        self.assertEqual(
            manifest["origin_recovery_id"], origin["plan_token"]
        )
        receipt = json.loads(
            (recovery / "receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["state"], "committed")
        self.assertEqual(
            receipt["origin_recovery_id"], origin["plan_token"]
        )
        self.assertEqual(
            receipt["approval"]["attempt_id"], evidence["attempt_id"]
        )

        inspected = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["classification"], "committed")
        receipt_inspected = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertTrue(receipt_inspected["success"])
        self.assertEqual(
            receipt_inspected["current_classification"], "committed"
        )
        self.assertEqual(self._snapshot_tree(origin_dir), origin_snapshot)

    def test_restore_edit_stale_after_approval_consumes_evidence(self):
        note, _origin, _origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])
        note.write_bytes(b"newer user edit\n")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "restore_current_state_changed")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"newer user edit\n")
        self.assertFalse((self.recovery / restore["plan_token"]).exists())

        # Returning the file to its old bytes does not revive the already-used
        # approval evidence.
        note.write_bytes(b"after\n")
        replay = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )
        self.assertFalse(replay["success"])
        self.assertEqual(
            replay["error"], "approval_evidence_already_consumed"
        )
        self.assertEqual(note.read_bytes(), b"after\n")

    def test_windows_restore_edit_rejects_same_bytes_file_replacement_after_approval(self):
        if os.name != "nt":
            self.skipTest("Windows file identity is the hardening target")

        note, _origin, _origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])
        replacement = self.vault / "replacement.md"
        replacement.write_bytes(note.read_bytes())
        os.replace(replacement, note)

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "restore_target_file_id_changed")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"after\n")
        self.assertFalse((self.recovery / restore["plan_token"]).exists())

    def test_restore_edit_failure_before_replace_is_prepared_no_effect(self):
        note, _origin, _origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])

        def fail(name):
            if name == "restore_edit_before_replace":
                raise RuntimeError("simulated before replace")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=fail,
        )

        self.assertFalse(result["success"])
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"after\n")
        inspected = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["classification"], "prepared_no_effect")
        receipt = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertTrue(receipt["success"])
        self.assertTrue(receipt["receipt_reconciliation_required"])
        self.assertEqual(
            receipt["current_classification"], "prepared_no_effect"
        )

    def test_restore_edit_failure_after_replace_is_applied_unfinalized(self):
        note, _origin, _origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])

        def fail(name):
            if name == "restore_edit_after_replace":
                raise RuntimeError("simulated after replace")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=fail,
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(note.read_bytes(), b"before\n")
        inspected = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        self.assertEqual(inspected["classification"], "applied_unfinalized")
        receipt = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertEqual(
            receipt["current_classification"], "applied_unfinalized"
        )

        fresh = self._fresh_once_evidence(restore["plan_token"])
        replay = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=fresh
        )
        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "plan_already_consumed")

    def test_restore_edit_receipt_finalization_failure_does_not_replay_write(self):
        note, _origin, _origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])

        def fail(name):
            if name == "restore_edit_before_receipt_commit":
                raise RuntimeError("simulated receipt finalization failure")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=fail,
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(note.read_bytes(), b"before\n")

        recovery = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        self.assertEqual(recovery["classification"], "committed")
        receipt = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertEqual(receipt["receipt_state"], "prepared")
        self.assertTrue(receipt["receipt_reconciliation_required"])
        self.assertEqual(
            receipt["current_classification"], "applied_unfinalized"
        )

        fresh = self._fresh_once_evidence(restore["plan_token"])
        replay = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=fresh
        )
        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "plan_already_consumed")
        self.assertEqual(note.read_bytes(), b"before\n")

    def test_restore_edit_post_write_hash_mismatch_is_recovery_required(self):
        note, _origin, _origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])

        def corrupt(name):
            if name == "restore_edit_after_replace":
                note.write_bytes(b"unexpected after restore\n")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=corrupt,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "restore_post_write_hash_mismatch")
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(note.read_bytes(), b"unexpected after restore\n")

    def test_restore_of_edit_restore_creates_another_independent_record(self):
        note, origin, _origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])
        first = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )
        self.assertTrue(first["success"])
        self.assertEqual(note.read_bytes(), b"before\n")
        first_dir = Path(first["recovery_dir"])
        first_snapshot = self._snapshot_tree(first_dir)

        second_preview = plugin._preview_disposable_restore_candidate(
            restore["plan_token"]
        )
        self.assertTrue(second_preview["success"])
        self.assertEqual(
            second_preview["plan"]["recovery_action"], "restore_edit"
        )
        second_evidence = self._fresh_once_evidence(
            second_preview["plan_token"]
        )
        second = plugin._execute_disposable_restore_candidate(
            second_preview["plan_token"], approval_evidence=second_evidence
        )

        self.assertTrue(second["success"])
        self.assertEqual(note.read_bytes(), b"after\n")
        self.assertNotEqual(second["recovery_id"], first["recovery_id"])
        self.assertNotEqual(second["recovery_id"], origin["plan_token"])
        self.assertEqual(self._snapshot_tree(first_dir), first_snapshot)

    def test_restore_move_source_requires_fresh_approval_evidence(self):
        draft, target, _source_bytes, _origin, _origin_result, _oe, restore = (
            self._move_restore_preview()
        )

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=None
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "approval_evidence_required")
        self.assertFalse(draft.exists())
        self.assertTrue(target.exists())
        self.assertFalse((self.recovery / restore["plan_token"]).exists())

    def test_restore_move_source_commit_is_exclusive_and_leaves_target_untouched(self):
        draft, target, source_bytes, origin, origin_result, _oe, restore = (
            self._move_restore_preview()
        )
        target_before = target.read_bytes()
        origin_dir = Path(origin_result["recovery_dir"])
        origin_snapshot = self._snapshot_tree(origin_dir)
        evidence = self._fresh_once_evidence(restore["plan_token"])

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )

        self.assertTrue(result["success"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        self.assertEqual(target.read_bytes(), target_before)
        recovery = Path(result["recovery_dir"])
        self.assertEqual(
            (recovery / "created_source.bin").read_bytes(), source_bytes
        )
        manifest = json.loads(
            (recovery / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["action"], "restore_move_source")
        self.assertEqual(manifest["state"], "committed")
        self.assertEqual(
            manifest["origin_recovery_id"], origin["plan_token"]
        )
        inspected = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["current_classification"], "committed")
        self.assertEqual(self._snapshot_tree(origin_dir), origin_snapshot)

    def test_restore_move_source_appearance_after_approval_fails_before_transaction(self):
        draft, target, _source_bytes, _origin, _origin_result, _oe, restore = (
            self._move_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])
        draft.write_bytes(b"someone created this\n")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "restore_source_no_longer_absent")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(draft.read_bytes(), b"someone created this\n")
        self.assertTrue(target.exists())
        self.assertFalse((self.recovery / restore["plan_token"]).exists())

        draft.unlink()
        retry = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )
        self.assertFalse(retry["success"])
        self.assertEqual(
            retry["error"], "approval_evidence_already_consumed"
        )

    def test_restore_move_source_failure_before_create_is_prepared_no_effect(self):
        draft, target, _source_bytes, _origin, _origin_result, _oe, restore = (
            self._move_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])

        def fail(name):
            if name == "restore_move_before_create":
                raise RuntimeError("simulated before exclusive create")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=fail,
        )

        self.assertFalse(result["success"])
        self.assertFalse(result["mutation_performed"])
        self.assertFalse(draft.exists())
        self.assertTrue(target.exists())
        recovery = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        self.assertTrue(recovery["success"])
        self.assertEqual(recovery["classification"], "prepared_no_effect")
        receipt = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertTrue(receipt["success"])
        self.assertTrue(receipt["receipt_reconciliation_required"])
        self.assertEqual(
            receipt["current_classification"], "prepared_no_effect"
        )

    def test_restore_move_source_exclusive_create_race_never_overwrites(self):
        draft, target, _source_bytes, _origin, _origin_result, _oe, restore = (
            self._move_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])
        competitor = b"competitor won\n"

        def race(name):
            if name == "restore_move_before_create":
                draft.write_bytes(competitor)

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=race,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "restore_source_create_race")
        self.assertFalse(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(draft.read_bytes(), competitor)
        self.assertTrue(target.exists())

        inspected = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        self.assertEqual(
            inspected["classification"], "divergent_unresolved"
        )

    def test_restore_move_source_failure_after_create_is_applied_unfinalized(self):
        draft, _target, source_bytes, _origin, _origin_result, _oe, restore = (
            self._move_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])

        def fail(name):
            if name == "restore_move_after_create":
                raise RuntimeError("simulated after create")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=fail,
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        inspected = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        self.assertEqual(inspected["classification"], "applied_unfinalized")
        receipt = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertEqual(
            receipt["current_classification"], "applied_unfinalized"
        )

    def test_restore_move_source_receipt_finalization_failure_is_not_replayed(self):
        draft, _target, source_bytes, _origin, _origin_result, _oe, restore = (
            self._move_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])

        def fail(name):
            if name == "restore_move_before_receipt_commit":
                raise RuntimeError("simulated receipt failure")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=fail,
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        recovery = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        self.assertEqual(recovery["classification"], "committed")
        receipt = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertEqual(receipt["receipt_state"], "prepared")
        self.assertEqual(
            receipt["current_classification"], "applied_unfinalized"
        )

        fresh = self._fresh_once_evidence(restore["plan_token"])
        replay = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=fresh
        )
        self.assertFalse(replay["success"])
        self.assertEqual(replay["error"], "plan_already_consumed")

    def test_restore_move_source_post_create_hash_mismatch_is_recovery_required(self):
        draft, _target, _source_bytes, _origin, _origin_result, _oe, restore = (
            self._move_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])

        def corrupt(name):
            if name == "restore_move_after_create":
                draft.write_bytes(b"unexpected after create\n")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=corrupt,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "restore_post_create_hash_mismatch")
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(draft.read_bytes(), b"unexpected after create\n")

    def test_restore_move_source_ignores_reference_target_disappearance(self):
        draft, target, source_bytes, _origin, _origin_result, _oe, restore = (
            self._move_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])
        target.unlink()

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )

        self.assertTrue(result["success"])
        self.assertEqual(draft.read_bytes(), source_bytes)
        self.assertFalse(target.exists())

    def test_corrupt_origin_backup_after_approval_fails_before_new_transaction(self):
        note, origin, origin_result, _origin_evidence, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])
        origin_backup = Path(origin_result["recovery_dir"], "original.bin")
        origin_backup.write_bytes(b"corrupt origin backup")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "restore_recovery_record_changed")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"after\n")
        self.assertFalse((self.recovery / restore["plan_token"]).exists())
        self.assertTrue((self.recovery / origin["plan_token"]).exists())

    def test_corrupt_restore_artifact_fails_recovery_and_receipt_inspection(self):
        _note, _origin, _origin_result, _oe, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])

        def fail(name):
            if name == "restore_edit_before_replace":
                raise RuntimeError("leave prepared restore")

        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"],
            approval_evidence=evidence,
            failure_hook=fail,
        )
        self.assertFalse(result["success"])
        recovery_dir = Path(result["recovery_dir"])
        (recovery_dir / "before_restore.bin").write_bytes(b"corrupt")

        recovery = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        self.assertFalse(recovery["success"])
        self.assertEqual(recovery["error"], "recovery_backup_hash_mismatch")
        receipt = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertFalse(receipt["success"])
        self.assertEqual(receipt["error"], "receipt_backup_hash_mismatch")

    def test_restore_receipt_cannot_authorize_a_second_restore(self):
        note, _origin, _origin_result, _oe, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])
        first = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )
        self.assertTrue(first["success"])
        self.assertEqual(note.read_bytes(), b"before\n")

        second_preview = plugin._preview_disposable_restore_candidate(
            restore["plan_token"]
        )
        self.assertTrue(second_preview["success"])
        receipt = json.loads(
            Path(first["recovery_dir"], "receipt.json").read_text(
                encoding="utf-8"
            )
        )

        misuse = plugin._execute_disposable_restore_candidate(
            second_preview["plan_token"],
            approval_evidence=receipt["approval"],
        )

        self.assertFalse(misuse["success"])
        self.assertEqual(misuse["error"], "approval_evidence_invalid")
        self.assertEqual(note.read_bytes(), b"before\n")
        self.assertFalse(
            (self.recovery / second_preview["plan_token"]).exists()
        )

    def test_restore_receipt_survives_memory_reset_without_recreating_authority(self):
        note, _origin, _origin_result, _oe, restore = (
            self._edit_restore_preview()
        )
        evidence = self._fresh_once_evidence(restore["plan_token"])
        result = plugin._execute_disposable_restore_candidate(
            restore["plan_token"], approval_evidence=evidence
        )
        self.assertTrue(result["success"])
        self.assertEqual(note.read_bytes(), b"before\n")

        plugin._PREVIEWS.clear()
        plugin._PREVIEW_TIMES.clear()
        plugin._APPROVAL_ATTEMPTS.clear()
        plugin._CANDIDATE_CONSUMED_PLANS.clear()
        plugin._CANDIDATE_CONSUMED_APPROVAL_ATTEMPTS.clear()

        recovery = plugin._inspect_disposable_recovery_candidate(
            restore["plan_token"]
        )
        receipt = plugin._inspect_disposable_receipt_candidate(
            restore["plan_token"]
        )
        self.assertTrue(recovery["success"])
        self.assertTrue(receipt["success"])
        self.assertEqual(recovery["classification"], "committed")
        self.assertEqual(receipt["current_classification"], "committed")
        self.assertFalse(receipt["authorization_reusable"])

        # The durable receipt survives, but without a live preview there is no
        # approval authority to reconstruct.
        self.assertFalse(plugin._probe_fresh_once_approval(
            restore["plan_token"],
            approval_request=lambda *_args, **_kwargs: {"approved": True},
            redact=lambda text: text,
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
