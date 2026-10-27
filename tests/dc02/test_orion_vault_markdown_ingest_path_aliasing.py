from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dc02"
    / "orion_vault_markdown_ingest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "orion_vault_markdown_ingest_path_aliasing", MODULE_PATH
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


def vendor_doc_tag_3_3_0(source_name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", source_name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


class FakeStore:
    def close(self) -> None:
        return None


class PathAliasingTests(unittest.TestCase):
    def _fixture(self, td: str):
        base = Path(td)
        vault = base / "vault"
        store = base / "store"
        vault.mkdir()
        (vault / "note.md").write_text("a sufficiently long note", encoding="utf-8")
        (store / "hippo").mkdir(parents=True)
        (store / "hippo" / "brain.sqlite3").write_bytes(b"fixture-db")
        return base, vault, store

    def _runtime(self, *, open_store=None):
        return mod.IaiRuntime(
            version="3.3.0",
            doc_tag=vendor_doc_tag_3_3_0,
            study_document=lambda *_a, **_kw: self.fail("unexpected study call"),
            open_store=open_store or (lambda _path: FakeStore()),
        )

    def _args(self, vault: Path, store: Path, state: Path):
        return [
            "--vault-root",
            str(vault),
            "--store-root",
            str(store),
            "--state-file",
            str(state),
            "--apply",
            "--json",
        ]

    def test_state_descendant_of_owner_file_is_rejected_before_path_poisoning(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store = self._fixture(td)
            owner = mod._store_owner_file_for(store)
            state = owner / "child-state.json"
            opens: list[Path] = []
            runtime = self._runtime(
                open_store=lambda path: opens.append(path) or FakeStore()
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))

            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("metadata_path_overlap", result["error"])
            self.assertEqual(opens, [])
            self.assertFalse(owner.exists(), "reserved owner filename was poisoned into a directory")
            self.assertFalse(mod._apply_lock_file_for(state).exists())
            self.assertFalse(mod._store_apply_lock_file_for(store).exists())

    def test_direct_lock_open_rejects_hardlink_before_writing_lock_byte(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            target = base / "target.bin"
            target.write_bytes(b"")
            lock = base / "lock.bin"
            try:
                os.link(target, lock)
            except (OSError, NotImplementedError):
                self.skipTest("hardlinks unavailable")
            self.assertGreater(os.stat(target).st_nlink, 1)

            with self.assertRaisesRegex(mod.AdapterError, "apply_lock_has_multiple_links"):
                mod._acquire_apply_lock(lock)

            self.assertEqual(target.read_bytes(), b"")
            self.assertEqual(lock.read_bytes(), b"")

    def test_hardlinked_state_lock_cannot_mutate_vault_alias(self):
        with tempfile.TemporaryDirectory() as td:
            base, vault, store = self._fixture(td)
            state = base / "state.json"
            vault_alias = vault / "lock-sentinel.txt"
            vault_alias.write_bytes(b"")
            state_lock = mod._apply_lock_file_for(state)
            try:
                os.link(vault_alias, state_lock)
            except (OSError, NotImplementedError):
                self.skipTest("hardlinks unavailable")
            before = vault_alias.read_bytes()
            opens: list[Path] = []
            runtime = self._runtime(
                open_store=lambda path: opens.append(path) or FakeStore()
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))

            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("metadata_path_has_multiple_links:state_lock", result["error"])
            self.assertEqual(vault_alias.read_bytes(), before)
            self.assertEqual(opens, [])
            self.assertFalse(state.exists())

    def test_hardlinked_semantic_db_is_rejected_before_native_store_open(self):
        with tempfile.TemporaryDirectory() as td:
            base, vault, store = self._fixture(td)
            state = base / "state.json"
            db = store / "hippo" / "brain.sqlite3"
            alias = vault / "db-alias.bin"
            try:
                os.link(db, alias)
            except (OSError, NotImplementedError):
                self.skipTest("hardlinks unavailable")
            before = db.read_bytes()
            opens: list[Path] = []
            runtime = self._runtime(
                open_store=lambda path: opens.append(path) or FakeStore()
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))

            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("metadata_path_has_multiple_links:semantic_db", result["error"])
            self.assertEqual(opens, [])
            self.assertEqual(db.read_bytes(), before)
            self.assertEqual(alias.read_bytes(), before)
            self.assertFalse(state.exists())

    def test_sibling_reserved_paths_remain_valid(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            paths = {
                "state": base / "state.json",
                "pending": base / "state.json.pending.json",
                "state_lock": base / "state.json.apply.lock",
                "owner": base / "owner.json",
            }
            mod.validate_metadata_path_disjointness(paths)


if __name__ == "__main__":
    unittest.main()
