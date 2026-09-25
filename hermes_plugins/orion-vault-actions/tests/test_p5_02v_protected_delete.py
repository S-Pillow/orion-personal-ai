"""P5-02V protected delete source qualification tests.

All mutation tests use temporary vault/inbox/recovery roots. They do not install
or modify the live COMPANION plugin or the production Orion vault.
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
    "orion_vault_actions_p502v", PLUGIN_DIR / "__init__.py"
)
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class ProtectedDeleteTests(unittest.TestCase):
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
            plugin.PRODUCTION_RECOVERY_ROOT_ENV: str(self.recovery),
        }, clear=False)
        self.env.start()
        os.environ.pop(plugin.PRODUCTION_MUTATION_MODE_ENV, None)
        os.environ.pop(plugin.DISPOSABLE_MUTATION_FLAG, None)
        os.environ.pop(plugin.RECOVERY_ROOT_ENV, None)

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

    def _gate(self, _tool_name, description, *, rule_key):
        plugin.post_approval_response(
            pattern_key=f"plugin_rule:{rule_key}",
            description=description,
            choice="once",
            surface="gateway",
        )
        return {"approved": True}

    def _apply(self, token, *, failure_hook=None):
        os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = (
            plugin.PRODUCTION_MODE_MUTATION_ENABLED
        )
        try:
            return plugin._execute_production_plan_candidate(
                token,
                approval_request=self._gate,
                redact=lambda text: text,
                failure_hook=failure_hook,
                local_fs_probe=self._local,
                acl_probe=self._acl,
                access_probe=self._access,
            )
        finally:
            os.environ.pop(plugin.PRODUCTION_MUTATION_MODE_ENV, None)

    def test_delete_preview_is_side_effect_free_and_exact(self):
        note = self.vault / "delete-me.md"
        note.write_bytes(b"alpha\nbeta\n")

        preview = json.loads(plugin.preview_delete({
            "target_relative_path": "delete-me.md",
        }))

        self.assertTrue(preview["success"])
        self.assertFalse(preview["mutation_performed"])
        self.assertTrue(note.is_file())
        self.assertEqual(note.read_bytes(), b"alpha\nbeta\n")
        self.assertEqual(preview["plan"]["action"], "delete_note")
        self.assertEqual(preview["plan"]["target_state"], "present")
        self.assertEqual(
            preview["plan"]["target_sha256"],
            plugin._sha_bytes(b"alpha\nbeta\n"),
        )
        self.assertIn("--- vault/delete-me.md", preview["diff"])
        self.assertIn("+++ /dev/null", preview["diff"])
        self.assertIn("-alpha", preview["diff"])
        self.assertIn("-beta", preview["diff"])

    def test_delete_preview_stale_hash_fails_revalidation(self):
        note = self.vault / "delete-me.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_delete({
            "target_relative_path": "delete-me.md",
        }))
        note.write_bytes(b"changed\n")

        result = plugin._revalidate_delete_preview_at_roots(
            preview["plan_token"], self.vault
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "delete_target_hash_changed")
        self.assertEqual(note.read_bytes(), b"changed\n")

    def test_delete_pretool_requires_explicit_mutation_enabled_mode(self):
        note = self.vault / "delete-me.md"
        note.write_bytes(b"before\n")
        preview = json.loads(plugin.preview_delete({
            "target_relative_path": "delete-me.md",
        }))

        blocked = plugin.pre_tool_call(
            plugin.APPLY_TOOL, {"plan_token": preview["plan_token"]}
        )

        self.assertEqual(blocked["action"], "block")
        self.assertIn("not enabled", blocked["message"])
        self.assertTrue(note.exists())

    def test_production_delete_commits_recovery_before_removing_target(self):
        note = self.vault / "delete-me.md"
        original = b"protected delete bytes\n"
        note.write_bytes(original)
        preview = json.loads(plugin.preview_delete({
            "target_relative_path": "delete-me.md",
        }))

        result = self._apply(preview["plan_token"])

        self.assertTrue(result["success"])
        self.assertTrue(result["mutation_performed"])
        self.assertFalse(result["recovery_required"])
        self.assertEqual(result["action"], "delete_note")
        self.assertFalse(note.exists())

        recovery_dir = self.recovery / preview["plan_token"]
        self.assertEqual(
            sorted(item.name for item in recovery_dir.iterdir()),
            ["deleted_target.bin", "manifest.json", "receipt.json"],
        )
        self.assertEqual(
            (recovery_dir / "deleted_target.bin").read_bytes(), original
        )

        inventory = plugin._enumerate_production_recovery_records(
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=self._access,
        )
        self.assertTrue(inventory["success"])
        self.assertEqual(inventory["record_count"], 1)
        self.assertEqual(inventory["attention_count"], 0)
        record = inventory["records"][0]
        self.assertTrue(record["valid"])
        self.assertFalse(record["needs_attention"])
        self.assertEqual(record["recovery"]["action"], "delete_note")
        self.assertEqual(
            record["recovery"]["classification"], "committed"
        )
        self.assertEqual(
            record["recovery"]["backup_sha256"],
            plugin._sha_bytes(original),
        )
        self.assertIsNone(record["recovery"]["target_sha256"])
        self.assertEqual(record["receipt"]["receipt_state"], "committed")
        self.assertTrue(record["receipt"]["receipt_finalized"])
        self.assertEqual(record["receipt"]["approval_choice"], "once")

    def test_delete_failure_after_recovery_preserves_target_and_evidence(self):
        note = self.vault / "delete-me.md"
        original = b"preserve me\n"
        note.write_bytes(original)
        preview = json.loads(plugin.preview_delete({
            "target_relative_path": "delete-me.md",
        }))

        def fail(checkpoint):
            if checkpoint == "production_delete_after_recovery":
                raise RuntimeError("simulated crash")

        result = self._apply(preview["plan_token"], failure_hook=fail)

        self.assertFalse(result["success"])
        self.assertTrue(result["recovery_required"])
        self.assertTrue(note.exists())
        self.assertEqual(note.read_bytes(), original)
        recovery_dir = self.recovery / preview["plan_token"]
        self.assertTrue((recovery_dir / "deleted_target.bin").is_file())
        self.assertTrue((recovery_dir / "manifest.json").is_file())
        self.assertTrue((recovery_dir / "receipt.json").is_file())

    def test_committed_delete_becomes_committed_then_changed_if_target_reappears(self):
        note = self.vault / "delete-me.md"
        original = b"original\n"
        note.write_bytes(original)
        preview = json.loads(plugin.preview_delete({
            "target_relative_path": "delete-me.md",
        }))
        result = self._apply(preview["plan_token"])
        self.assertTrue(result["success"])
        self.assertFalse(note.exists())

        note.write_bytes(original)
        inventory = plugin._enumerate_production_recovery_records(
            local_fs_probe=self._local,
            acl_probe=self._acl,
            access_probe=self._access,
        )

        self.assertEqual(inventory["attention_count"], 0)
        record = inventory["records"][0]
        self.assertEqual(
            record["recovery"]["classification"], "committed_then_changed"
        )
        self.assertFalse(record["needs_attention"])

    def test_windows_delete_preview_binds_file_identity(self):
        if os.name != "nt":
            self.skipTest("Windows file identity is the production target")

        note = self.vault / "delete-me.md"
        note.write_bytes(b"windows\n")
        preview = json.loads(plugin.preview_delete({
            "target_relative_path": "delete-me.md",
        }))

        self.assertTrue(preview["success"])
        self.assertEqual(
            preview["plan"]["target_file_id"],
            plugin._windows_path_file_identity(note),
        )


if __name__ == "__main__":
    unittest.main()
