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
