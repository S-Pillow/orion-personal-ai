from __future__ import annotations

import importlib.util
import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest.py"
SPEC = importlib.util.spec_from_file_location("dc02_db_identity_test", PUBLIC)
pub = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = pub
SPEC.loader.exec_module(pub)
core = pub.core


def tag(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


def native_study(events: list[tuple]):
    def study(_store, **kwargs):
        source = kwargs["source_name"]
        if kwargs.get("path") is not None:
            events.append(("study", source))
            return {
                "chunks_total": 1,
                "inserted": 1,
                "reinforced": 0,
                "skipped": 0,
                "recall_tested": 1,
                "recall_verified": 1,
            }
        events.append(("fade", source))
        return {
            "chunks_total": 0,
            "inserted": 0,
            "reinforced": 0,
            "skipped": 0,
            "recall_tested": 0,
            "recall_verified": 0,
        }

    study.__module__ = "iai_mcp.study"
    study.__name__ = "study_document"
    return study


class FakeStore:
    def close(self) -> None:
        return None


class DbIdentityTests(unittest.TestCase):
    def _fixture(self, td: str):
        base = Path(td)
        vault = base / "vault"
        store = base / "store"
        vault.mkdir()
        (store / "hippo").mkdir(parents=True)
        db = store / "hippo" / "brain.sqlite3"
        db.write_bytes(b"fixture-db")
        return base, vault, store, db, core.metadata_paths(store)

    def _runtime(self, events: list[tuple], open_store):
        return core.IaiRuntime("3.3.0", tag, native_study(events), open_store)

    def _args(self, vault: Path, store: Path):
        return [
            "--vault-root",
            str(vault),
            "--store-root",
            str(store),
            "--apply",
            "--json",
        ]

    def _replace_db(self, db: Path, payload: bytes = b"replacement-db") -> None:
        replacement = db.with_name("replacement.sqlite3")
        replacement.write_bytes(payload)
        old = core.semantic_db_identity(db)
        new_file = core.semantic_db_identity(replacement)
        self.assertNotEqual(
            (old["device"], old["inode"]),
            (new_file["device"], new_file["inode"]),
        )
        os.replace(replacement, db)
        current = core.semantic_db_identity(db)
        self.assertEqual(
            (current["device"], current["inode"]),
            (new_file["device"], new_file["inode"]),
        )

    def test_semantic_store_cannot_overlap_read_only_vault(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            store = base / "store"
            vault = store / "hippo"
            vault.mkdir(parents=True)
            (vault / "brain.sqlite3").write_bytes(b"fixture-db")
            (vault / "note.md").write_text("vault overlap content", encoding="utf-8")
            paths = core.metadata_paths(store)
            opened: list[Path] = []
            runtime = self._runtime([], lambda root: opened.append(Path(root)) or FakeStore())
            out = io.StringIO()
            with mock.patch.object(core, "load_iai_runtime", return_value=runtime), redirect_stdout(out):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 1)
            self.assertIn("vault_store_overlap", out.getvalue())
            self.assertEqual(opened, [])
            self.assertFalse(paths.root.exists())

    def test_replaced_db_rejects_existing_checkpoint_before_noop_success(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store, db, paths = self._fixture(td)
            (vault / "note.md").write_text("stable source content", encoding="utf-8")
            first_events: list[tuple] = []
            first = self._runtime(first_events, lambda _root: FakeStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=first), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 0)
            self.assertEqual([event[0] for event in first_events], ["study"])
            self.assertTrue(paths.state.is_file())
            self.assertTrue(paths.owner.is_file())

            self._replace_db(db)
            opened: list[Path] = []
            second = self._runtime([], lambda root: opened.append(Path(root)) or FakeStore())
            out = io.StringIO()
            with mock.patch.object(core, "load_iai_runtime", return_value=second), redirect_stdout(out):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 1)
            self.assertIn("state_semantic_db_identity_mismatch", out.getvalue())
            self.assertEqual(opened, [])

    def test_db_replacement_after_native_close_blocks_checkpoint_commit(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store, db, paths = self._fixture(td)
            (vault / "note.md").write_text("replace during transaction", encoding="utf-8")
            events: list[tuple] = []

            test_case = self

            class ReplaceOnCloseStore:
                def close(self) -> None:
                    test_case._replace_db(db, b"replacement-on-close")

            runtime = self._runtime(events, lambda _root: ReplaceOnCloseStore())
            out = io.StringIO()
            with mock.patch.object(core, "load_iai_runtime", return_value=runtime), redirect_stdout(out):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 1)
            self.assertIn("semantic_db_identity_mismatch", out.getvalue())
            self.assertEqual([event[0] for event in events], ["study"])
            self.assertTrue(paths.pending.is_file())
            self.assertTrue(paths.owner.is_file())
            self.assertFalse(paths.state.exists())

    def test_in_place_db_write_keeps_identity_and_noop_checkpoint_valid(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store, db, _paths = self._fixture(td)
            (vault / "note.md").write_text("stable in-place identity", encoding="utf-8")
            first = self._runtime([], lambda _root: FakeStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=first), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 0)

            before = core.semantic_db_identity(db)
            with db.open("ab") as handle:
                handle.write(b"in-place-change")
                handle.flush()
                os.fsync(handle.fileno())
            after = core.semantic_db_identity(db)
            self.assertEqual(before, after)

            opened: list[Path] = []
            second = self._runtime([], lambda root: opened.append(Path(root)) or FakeStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=second), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 0)
            self.assertEqual(opened, [])


if __name__ == "__main__":
    unittest.main()
