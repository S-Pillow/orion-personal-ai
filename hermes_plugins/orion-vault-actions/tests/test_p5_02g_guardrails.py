"""P5-02G production mutation guardrail tests.

These tests exercise production configuration/preflight logic only against
temporary roots. They do not install the plugin or touch the live COMPANION
profile, vault, inbox, or recovery location.
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
    "orion_vault_actions_p502g", PLUGIN_DIR / "__init__.py"
)
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class ProductionGuardrailTests(unittest.TestCase):
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
            plugin.PRODUCTION_RECOVERY_ROOT_ENV: str(self.recovery),
            plugin.DISPOSABLE_MUTATION_FLAG: "1",
        }, clear=False)
        self.env.start()
        os.environ.pop(plugin.PRODUCTION_MUTATION_MODE_ENV, None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    @staticmethod
    def _local(_path):
        return True

    @staticmethod
    def _acl(_path):
        return []

    @staticmethod
    def _access(_path):
        return None

    def _preflight(self):
        return plugin._validate_production_roots(
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=self._access,
        )

    def _fresh_once_evidence(self, plan_token):
        def gate(_tool_name, description, *, rule_key):
            plugin.post_approval_response(
                pattern_key=f"plugin_rule:{rule_key}",
                description=description,
                choice="once",
                surface="gateway",
            )
            return {"approved": True}

        result = plugin._fresh_once_approval_evidence(
            plan_token, approval_request=gate, redact=lambda text: text
        )
        self.assertTrue(result["approved"])
        return result

    def _committed_edit_record(self):
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
        return note, preview, result

    def test_missing_mode_defaults_fail_closed_disabled(self):
        mode = plugin._production_mutation_mode()

        self.assertTrue(mode["valid"])
        self.assertFalse(mode["configured"])
        self.assertEqual(mode["mode"], plugin.PRODUCTION_MODE_DISABLED)
        self.assertFalse(mode["mutation_allowed"])

    def test_invalid_mode_is_fail_closed(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = "go-fast"

        mode = plugin._production_mutation_mode()
        preflight = self._preflight()

        self.assertFalse(mode["valid"])
        self.assertEqual(mode["mode"], plugin.PRODUCTION_MODE_DISABLED)
        self.assertFalse(mode["mutation_allowed"])
        self.assertFalse(preflight["success"])
        self.assertEqual(
            preflight["error"], "invalid_production_mutation_mode"
        )

    def test_preview_only_preflight_is_valid_but_not_mutation_capable(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_PREVIEW_ONLY
        )

        result = self._preflight()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["mutation_mode"], plugin.PRODUCTION_MODE_PREVIEW_ONLY
        )
        self.assertFalse(result["mutation_allowed"])
        self.assertEqual(
            Path(result["recovery_root"]), self.recovery.resolve(strict=True)
        )

    def test_mutation_enabled_preflight_is_explicit(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )

        result = self._preflight()

        self.assertTrue(result["success"])
        self.assertTrue(result["mutation_allowed"])
        self.assertEqual(
            result["mutation_mode"], plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )

    def test_production_recovery_root_is_required(self):
        os.environ.pop(plugin.PRODUCTION_RECOVERY_ROOT_ENV, None)

        result = self._preflight()

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "production_recovery_root_required")

    def test_production_recovery_root_overlap_is_rejected(self):
        os.environ[plugin.PRODUCTION_RECOVERY_ROOT_ENV] = str(self.vault)

        result = self._preflight()

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "production_root_overlap_rejected")

    def test_broad_write_acl_is_rejected(self):
        result = plugin._validate_production_roots(
            local_fs_probe=self._local,
            acl_probe=lambda _path: ["S-1-1-0"],
            access_probe=self._access,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error"], "production_recovery_acl_too_broad"
        )
        self.assertEqual(result["broad_write_principals"], ["S-1-1-0"])

    def test_non_fixed_or_remote_recovery_storage_is_rejected(self):
        result = plugin._validate_production_roots(
            local_fs_probe=lambda _path: False,
            acl_probe=self._acl,
            access_probe=self._access,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error"], "production_recovery_root_not_fixed_local"
        )

    def test_recovery_access_probe_failure_is_fail_closed(self):
        def fail(_path):
            raise PermissionError("denied")

        result = plugin._validate_production_roots(
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=fail,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error"],
            "production_recovery_validation_failed:PermissionError",
        )

    def test_inventory_surfaces_committed_record_without_attention(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_PREVIEW_ONLY
        )
        _note, preview, _result = self._committed_edit_record()

        inventory = plugin._enumerate_production_recovery_records(
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=self._access,
        )

        self.assertTrue(inventory["success"])
        self.assertEqual(inventory["record_count"], 1)
        self.assertEqual(inventory["attention_count"], 0)
        record = inventory["records"][0]
        self.assertEqual(record["recovery_id"], preview["plan_token"])
        self.assertTrue(record["valid"])
        self.assertFalse(record["needs_attention"])
        self.assertEqual(
            record["recovery"]["classification"], "committed"
        )

    def test_inventory_surfaces_prepared_unfinalized_record(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_PREVIEW_ONLY
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))
        evidence = self._fresh_once_evidence(preview["plan_token"])

        def fail(name):
            if name == "edit_after_replace":
                raise RuntimeError("simulated crash")

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"],
            approval_evidence=evidence,
            failure_hook=fail,
        )
        self.assertFalse(result["success"])

        inventory = plugin._enumerate_production_recovery_records(
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=self._access,
        )

        self.assertTrue(inventory["success"])
        self.assertEqual(inventory["attention_count"], 1)
        record = inventory["records"][0]
        self.assertTrue(record["needs_attention"])
        self.assertEqual(
            record["recovery"]["classification"], "applied_unfinalized"
        )

    def test_inventory_is_bounded_and_marks_invalid_entries(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_PREVIEW_ONLY
        )
        for index in range(5):
            (self.recovery / f"not-a-record-{index}").mkdir()

        inventory = plugin._enumerate_production_recovery_records(
            limit=3,
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=self._access,
        )

        self.assertTrue(inventory["success"])
        self.assertEqual(inventory["record_count"], 3)
        self.assertTrue(inventory["truncated"])
        self.assertEqual(inventory["attention_count"], 3)
        self.assertTrue(all(
            item["error"] == "invalid_recovery_record_entry"
            for item in inventory["records"]
        ))

    def test_inventory_rejects_invalid_limit(self):
        result = plugin._enumerate_production_recovery_records(
            limit=0,
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=self._access,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_recovery_scan_limit")

    def test_windows_edit_preview_binds_file_identity(self):
        if os.name != "nt":
            self.skipTest("Windows file identity is the production target")

        note = self.vault / "note.md"
        note.write_bytes(b"before\n")

        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))

        self.assertTrue(preview["success"])
        self.assertIn("target_file_id", preview["plan"])
        self.assertEqual(
            preview["plan"]["target_file_id"],
            plugin._windows_path_file_identity(note),
        )

    def test_windows_edit_rejects_same_bytes_different_file_object(self):
        if os.name != "nt":
            self.skipTest("Windows file identity is the production target")

        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))
        self.assertTrue(preview["success"])

        replacement = self.vault / "replacement.md"
        replacement.write_bytes(note.read_bytes())
        os.replace(replacement, note)

        result = plugin._execute_disposable_plan_candidate(
            preview["plan_token"]
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "target_file_id_changed")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"before\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def _production_once_gate(self, after_once=None):
        def gate(_tool_name, description, *, rule_key):
            plugin.post_approval_response(
                pattern_key=f"plugin_rule:{rule_key}",
                description=description,
                choice="once",
                surface="gateway",
            )
            if after_once is not None:
                after_once()
            return {"approved": True}
        return gate

    def _production_apply(self, plan_token, *, gate=None, failure_hook=None):
        return plugin._execute_production_plan_candidate(
            plan_token,
            approval_request=gate,
            redact=lambda text: text,
            failure_hook=failure_hook,
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=self._access,
        )

    def test_mutation_enabled_pretool_validates_without_owning_approval(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))

        directive = plugin.pre_tool_call(
            plugin.APPLY_TOOL, {"plan_token": preview["plan_token"]}
        )
        blocked = plugin.pre_tool_call(
            plugin.APPLY_TOOL, {"plan_token": "f" * 64}
        )

        self.assertIsNone(directive)
        self.assertEqual(blocked["action"], "block")
        self.assertEqual(note.read_bytes(), b"before\n")

    def test_preview_only_pretool_keeps_non_mutating_approval_contract(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_PREVIEW_ONLY
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))

        directive = plugin.pre_tool_call(
            plugin.APPLY_TOOL, {"plan_token": preview["plan_token"]}
        )

        self.assertEqual(directive["action"], "approve")
        self.assertIn("fail-closed", directive["message"])
        self.assertEqual(note.read_bytes(), b"before\n")

    def test_production_candidate_is_unregistered_and_public_apply_refuses(self):
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
        self.assertNotIn(
            plugin._execute_production_plan_candidate, ctx.tools.values()
        )

    def test_production_candidate_refuses_preview_only_before_approval(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_PREVIEW_ONLY
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))
        called = {"value": False}

        def gate(*_args, **_kwargs):
            called["value"] = True
            return {"approved": True}

        result = self._production_apply(preview["plan_token"], gate=gate)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "production_mutation_not_enabled")
        self.assertFalse(called["value"])
        self.assertEqual(note.read_bytes(), b"before\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_production_edit_deny_has_no_side_effect(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))

        result = self._production_apply(
            preview["plan_token"],
            gate=lambda *_args, **_kwargs: {"approved": False},
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "fresh_once_not_observed")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"before\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_production_edit_once_commits_schema2_receipt(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))

        result = self._production_apply(
            preview["plan_token"],
            gate=self._production_once_gate(),
        )

        self.assertTrue(result["success"])
        self.assertEqual(note.read_bytes(), b"after\n")
        recovery = self.recovery / preview["plan_token"]
        manifest = json.loads(
            (recovery / "manifest.json").read_text(encoding="utf-8")
        )
        receipt = json.loads(
            (recovery / "receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["recovery_id"], preview["plan_token"])
        self.assertEqual(manifest["state"], "committed")
        self.assertEqual(receipt["schema_version"], 2)
        self.assertEqual(receipt["state"], "committed")
        self.assertIn(
            "private production mutation candidate",
            receipt["approval"]["approval_message"],
        )
        inspected = plugin._inspect_receipt_at_roots(
            self.vault, self.inbox, self.recovery, preview["plan_token"]
        )
        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["current_classification"], "committed")
        self.assertFalse(inspected["authorization_reusable"])

    def test_production_edit_stale_after_human_once_fails_before_recovery(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))

        result = self._production_apply(
            preview["plan_token"],
            gate=self._production_once_gate(
                lambda: note.write_bytes(b"changed while deciding\n")
            ),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "stale_original_hash")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"changed while deciding\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_windows_production_edit_same_bytes_swap_after_once_is_stale(self):
        if os.name != "nt":
            self.skipTest("Windows file identity is the production target")
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))

        def replace_same_bytes():
            replacement = self.vault / "replacement.md"
            replacement.write_bytes(note.read_bytes())
            os.replace(replacement, note)

        result = self._production_apply(
            preview["plan_token"],
            gate=self._production_once_gate(replace_same_bytes),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "target_file_id_changed")
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(note.read_bytes(), b"before\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_production_edit_receipt_finalization_failure_is_reconcilable(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))

        def fail(name):
            if name == "production_edit_before_receipt_commit":
                raise RuntimeError("simulated receipt failure")

        result = self._production_apply(
            preview["plan_token"],
            gate=self._production_once_gate(),
            failure_hook=fail,
        )

        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertTrue(result["recovery_required"])
        self.assertEqual(note.read_bytes(), b"after\n")
        inspected = plugin._inspect_receipt_at_roots(
            self.vault, self.inbox, self.recovery, preview["plan_token"]
        )
        self.assertTrue(inspected["success"])
        self.assertEqual(inspected["receipt_state"], "prepared")
        self.assertTrue(inspected["receipt_reconciliation_required"])
        self.assertEqual(
            inspected["current_classification"], "applied_unfinalized"
        )

    def test_production_edit_replay_is_refused_before_second_approval(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))
        first = self._production_apply(
            preview["plan_token"],
            gate=self._production_once_gate(),
        )
        self.assertTrue(first["success"])
        called = {"value": False}

        def second_gate(*_args, **_kwargs):
            called["value"] = True
            return {"approved": True}

        second = self._production_apply(
            preview["plan_token"], gate=second_gate
        )

        self.assertFalse(second["success"])
        self.assertEqual(second["error"], "plan_already_consumed")
        self.assertFalse(called["value"])
        self.assertEqual(note.read_bytes(), b"after\n")

    def test_production_move_once_commits_without_disposable_guard(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        (self.vault / "Folder").mkdir()
        draft = self.inbox / "draft.md"
        draft_bytes = (
            b"---\r\norion_draft: true\r\nstatus: draft\r\n---\r\nbody"
        )
        draft.write_bytes(draft_bytes)
        target = self.vault / "Folder" / "draft.md"
        preview = json.loads(plugin.preview_move_draft({
            "source_draft": "draft.md",
            "target_relative_path": "Folder/draft.md",
        }))

        # Prove this path is not relying on the disposable opt-in.
        os.environ.pop(plugin.DISPOSABLE_MUTATION_FLAG, None)
        result = self._production_apply(
            preview["plan_token"],
            gate=self._production_once_gate(),
        )

        self.assertTrue(result["success"])
        self.assertFalse(draft.exists())
        self.assertEqual(target.read_bytes(), draft_bytes)
        manifest = json.loads(
            Path(result["recovery_dir"], "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["state"], "committed")

    def test_production_move_target_appears_after_approval_is_refused(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        (self.vault / "Folder").mkdir()
        draft = self.inbox / "draft.md"
        draft.write_text(
            "---\norion_draft: true\nstatus: draft\n---\nbody\n",
            encoding="utf-8",
        )
        target = self.vault / "Folder" / "draft.md"
        preview = json.loads(plugin.preview_move_draft({
            "source_draft": "draft.md",
            "target_relative_path": "Folder/draft.md",
        }))

        result = self._production_apply(
            preview["plan_token"],
            gate=self._production_once_gate(
                lambda: target.write_bytes(b"competitor\n")
            ),
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "target_already_exists")
        self.assertFalse(result["mutation_performed"])
        self.assertTrue(draft.exists())
        self.assertEqual(target.read_bytes(), b"competitor\n")
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_unresolved_recovery_blocks_new_production_mutation_before_approval(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        (self.recovery / "not-a-valid-record").mkdir()
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))
        called = {"value": False}

        def gate(*_args, **_kwargs):
            called["value"] = True
            return {"approved": True}

        result = self._production_apply(preview["plan_token"], gate=gate)

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error"], "production_recovery_attention_required"
        )
        self.assertFalse(called["value"])
        self.assertEqual(note.read_bytes(), b"before\n")

    def test_production_restore_edit_uses_new_schema2_transaction(self):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        note = self.vault / "note.md"
        note.write_bytes(b"before\n")
        edit = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md",
            "new_content": "after\n",
        }))
        first = self._production_apply(
            edit["plan_token"], gate=self._production_once_gate()
        )
        self.assertTrue(first["success"])
        self.assertEqual(note.read_bytes(), b"after\n")

        restore = plugin._preview_production_restore_candidate(
            edit["plan_token"],
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=self._access,
        )
        self.assertTrue(restore["success"])
        second = self._production_apply(
            restore["plan_token"], gate=self._production_once_gate()
        )

        self.assertTrue(second["success"])
        self.assertEqual(note.read_bytes(), b"before\n")
        self.assertNotEqual(second["recovery_id"], edit["plan_token"])
        manifest = json.loads(
            Path(second["recovery_dir"], "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["action"], "restore_edit")
        self.assertEqual(
            manifest["origin_recovery_id"], edit["plan_token"]
        )

    def test_windows_native_recovery_probes_are_read_only_smoke(self):
        if os.name != "nt":
            self.skipTest("Windows production preflight smoke")

        before = sorted(path.name for path in self.recovery.iterdir())

        self.assertTrue(plugin._windows_path_is_fixed_local(self.recovery))
        plugin._windows_directory_access_probe(self.recovery)
        offenders = plugin._windows_recovery_acl_broad_writers(self.recovery)

        self.assertIsInstance(offenders, list)
        self.assertEqual(
            sorted(path.name for path in self.recovery.iterdir()), before
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
