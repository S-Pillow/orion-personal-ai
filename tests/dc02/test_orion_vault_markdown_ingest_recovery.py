from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest_core.py"
SPEC = importlib.util.spec_from_file_location("dc02_recovery_test", CORE)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


def tag(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


class RecoveryStateMachineTests(unittest.TestCase):
    def _fixture(self, td: str):
        base = Path(td); vault = base / "vault"; store = base / "store"
        vault.mkdir(); (store / "hippo").mkdir(parents=True)
        (store / "hippo" / "brain.sqlite3").write_bytes(b"db")
        return vault, store, mod.metadata_paths(store)

    def test_pending_state_machine_active_then_completed(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            (vault / "a.md").write_text("first admitted content", encoding="utf-8")
            notes = mod.scan_markdown_vault(vault)
            empty = mod._empty_state(vault, store)
            tags = {"a.md": tag("a.md")}
            plan = mod.build_plan(notes, empty)
            target = "1" * 64
            pending = mod._pending_payload(vault, store, empty, notes, tags, plan, target)
            mod._atomic_write(paths.pending, pending, "pending")
            pending_status = mod.load_pending(paths.pending, vault, store, empty, tags, tag)
            self.assertEqual(pending_status.status, "active")
            self.assertEqual(pending_status.paths, ("a.md",))

            committed = mod._state_payload(vault, store, notes, tags, target)
            pending_status = mod.load_pending(paths.pending, vault, store, committed, tags, tag)
            self.assertEqual(pending_status.status, "completed")
            self.assertEqual(pending_status.paths, ("a.md",))

    def test_active_pending_forces_restudy_after_source_reverts(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            p = vault / "a.md"; p.write_text("original admitted content", encoding="utf-8")
            base_notes = mod.scan_markdown_vault(vault)
            tags = {"a.md": tag("a.md")}
            base_state = mod._state_payload(vault, store, base_notes, tags, "2" * 64)

            p.write_text("changed failed transaction", encoding="utf-8")
            target_notes = mod.scan_markdown_vault(vault)
            plan = mod.build_plan(target_notes, base_state)
            pending = mod._pending_payload(vault, store, base_state, target_notes, tags, plan, "3" * 64)
            mod._atomic_write(paths.pending, pending, "pending")

            p.write_text("original admitted content", encoding="utf-8")
            current = mod.scan_markdown_vault(vault)
            normal = mod.build_plan(current, base_state)
            self.assertEqual(normal.unchanged, ("a.md",))
            pending_status = mod.load_pending(paths.pending, vault, store, base_state, tags, tag)
            self.assertEqual(pending_status.status, "active")
            reconciled = mod.reconcile_active_pending(normal, current, base_state, pending_status.paths)
            self.assertEqual(reconciled.changed, ("a.md",))
            self.assertEqual(reconciled.unchanged, ())

    def test_completed_pending_does_not_reserve_old_tag(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            old = mod.NoteSnapshot("a/b.md", str(vault / "a" / "b.md"), 1, 1, "a" * 64)
            old_tags = {"a/b.md": tag("a/b.md")}
            base = mod._state_payload(vault, store, [old], old_tags, "4" * 64)
            plan = mod.SyncPlan(new=(), changed=(), unchanged=(), deleted=("a/b.md",))
            pending = mod._pending_payload(vault, store, base, [], {}, plan, "5" * 64)
            mod._atomic_write(paths.pending, pending, "pending")
            committed = mod._state_payload(vault, store, [], {}, "5" * 64)
            current_tags = {"a-b.md": tag("a-b.md")}
            pending_status = mod.load_pending(paths.pending, vault, store, committed, current_tags, tag)
            self.assertEqual(pending_status.status, "completed")

    def test_pending_only_new_path_deleted_before_retry_keeps_recovery_tag(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            state = mod._empty_state(vault, store)
            note = mod.NoteSnapshot(
                "new.md",
                str(vault / "new.md"),
                len(b"new content"),
                1,
                mod.hashlib.sha256(b"new content").hexdigest(),
            )
            initial_plan = mod.SyncPlan(new=("new.md",), changed=(), unchanged=(), deleted=())
            initial_pending = mod._pending_payload(
                vault, store, state, [note], {"new.md": tag("new.md")}, initial_plan, "7" * 64
            )
            mod._atomic_write(paths.pending, initial_pending, "pending")

            pending_status = mod.load_pending(paths.pending, vault, store, state, {}, tag)
            self.assertEqual(pending_status.status, "active")
            self.assertEqual(pending_status.doc_tags["new.md"], tag("new.md"))

            reconciled = mod.reconcile_active_pending(
                mod.SyncPlan(new=(), changed=(), unchanged=(), deleted=()),
                [],
                state,
                pending_status.paths,
            )
            self.assertEqual(reconciled.deleted, ("new.md",))
            replacement = mod._pending_payload(
                vault,
                store,
                state,
                [],
                {},
                reconciled,
                "8" * 64,
                recovery_doc_tags=pending_status.doc_tags,
            )
            self.assertEqual(replacement["base_files_sha256"], replacement["target_files_sha256"])
            self.assertEqual(replacement["paths"]["new.md"]["doc_tag"], tag("new.md"))
            mod._atomic_write(paths.pending, replacement, "pending")
            again = mod.load_pending(paths.pending, vault, store, state, {}, tag)
            self.assertEqual(again.status, "active")
            self.assertEqual(again.paths, ("new.md",))

    def test_corrupt_target_digest_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            state = mod._empty_state(vault, store)
            payload = {
                "schema_version": mod.PENDING_SCHEMA_VERSION,
                "session_id": mod.SESSION_ID,
                "iai_version": mod.EXPECTED_IAI_VERSION,
                "vault_root": str(vault.resolve()),
                "store_root": str(store.resolve()),
                "started_run_utc": "2026-10-27T00:00:00Z",
                "base_checkpoint_id": state["checkpoint_id"],
                "target_checkpoint_id": "6" * 64,
                "base_files_sha256": mod._files_digest({}),
                "target_files_sha256": "0" * 64,
                "paths": {"a.md": {"doc_tag": tag("a.md")}},
            }
            mod._atomic_write(paths.pending, payload, "pending")
            committed = mod._state_payload(vault, store, [], {}, "6" * 64)
            with self.assertRaisesRegex(mod.AdapterError, "pending_target_digest_mismatch"):
                mod.load_pending(paths.pending, vault, store, committed, {}, tag)

    def test_owner_binds_store_to_one_vault(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            other = Path(td) / "other"; other.mkdir()
            mod._atomic_write(paths.owner, mod.owner_payload(vault, store), "owner")
            with self.assertRaisesRegex(mod.AdapterError, "owner_vault_root_mismatch"):
                mod.load_owner(paths.owner, other, store)


if __name__ == "__main__":
    unittest.main()
