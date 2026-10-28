from __future__ import annotations

import importlib
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest_core.py"
SPEC = importlib.util.spec_from_file_location("dc02_contract_test", CORE)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)
contract = importlib.import_module("orion_vault_ingest_contract")


class CrossModuleContractTests(unittest.TestCase):
    def _fixture(self, td: str):
        base = Path(td)
        vault = base / "vault"
        store = base / "store"
        vault.mkdir()
        (store / "hippo").mkdir(parents=True)
        (store / "hippo" / "brain.sqlite3").write_bytes(b"db")
        return vault, store, mod.metadata_paths(store)

    def test_real_hippo_directory_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, _paths = self._fixture(td)
            db = mod.validate_store(vault, store, require_db=True)
            self.assertEqual(db, store.resolve() / "hippo" / "brain.sqlite3")

    def test_reparse_hippo_is_rejected_by_public_store_contract(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, _paths = self._fixture(td)
            hippo = store.resolve() / "hippo"
            original = contract._fs._is_reparse_point

            def fake_reparse(path: Path) -> bool:
                if Path(path) == hippo:
                    return True
                return original(Path(path))

            with mock.patch.object(contract._fs, "_is_reparse_point", side_effect=fake_reparse):
                with self.assertRaisesRegex(
                    mod.AdapterError, "semantic_store_hippo_is_reparse_point"
                ):
                    mod.validate_store(vault, store, require_db=True)

    @unittest.skipIf(os.name == "nt", "POSIX symlink fixture; Windows reparse is covered above")
    def test_redirected_hippo_cannot_share_one_db_across_two_lock_namespaces(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "vault"
            vault.mkdir()
            nested = base / "outer" / "nested-store"
            (nested / "hippo").mkdir(parents=True)
            (nested / "hippo" / "brain.sqlite3").write_bytes(b"db")

            outer = base / "outer"
            redirected = outer / "hippo"
            redirected.symlink_to(nested / "hippo", target_is_directory=True)

            # The nested store is valid and has its own canonical lock namespace.
            mod.validate_store(vault, nested, require_db=True)
            nested_paths = mod.metadata_paths(nested)
            nested_lock = mod.acquire_apply_lock(nested_paths.lock)
            try:
                # The apparent outer store reaches the same DB through the hippo
                # alias, but must be rejected before its independent lock can be
                # considered a valid serialization boundary.
                with self.assertRaisesRegex(
                    mod.AdapterError, "semantic_store_hippo_is_reparse_point"
                ):
                    mod.validate_store(vault, outer, require_db=True)
            finally:
                nested_lock.close()

    def test_persisted_state_cannot_use_empty_state_null_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            paths.root.mkdir(parents=True, exist_ok=True)
            malformed = mod._empty_state(vault, store)
            mod._atomic_write(paths.state, malformed, "state")
            with self.assertRaisesRegex(mod.AdapterError, "state_success_timestamp_invalid"):
                mod.load_state(paths.state, vault, store)

    def test_synthetic_empty_state_still_allows_null_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            state = mod.load_state(paths.state, vault, store)
            self.assertIsNone(state["successful_run_utc"])
            self.assertEqual(state["files"], {})


if __name__ == "__main__":
    unittest.main()
