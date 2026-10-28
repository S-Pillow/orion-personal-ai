from __future__ import annotations

import importlib.util
import io
import re
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest.py"
SPEC = importlib.util.spec_from_file_location("dc02_live_db_binding_test", PUBLIC)
pub = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = pub
SPEC.loader.exec_module(pub)
core = pub.core


def tag(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


def make_sqlite(path: Path, marker: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        conn.execute("INSERT INTO marker(value) VALUES (?)", (marker,))
        conn.commit()
    finally:
        conn.close()


class SqliteBackedFakeStore:
    def __init__(self, db_path: Path, *, on_close=None):
        self._conn = sqlite3.connect(db_path)
        self._on_close = on_close
        self.db = type("FakeHippoDB", (), {})()
        self.db._conn = self._conn
        self.db._db_path = str(db_path)
        self.db._storage_driver = "stdlib"

    def close(self):
        self._conn.close()
        if self._on_close is not None:
            self._on_close()


def native_study(events: list[tuple]):
    def study(_store, **kwargs):
        source = kwargs["source_name"]
        events.append(("study" if kwargs.get("path") is not None else "fade", source))
        if kwargs.get("path") is not None:
            return {
                "chunks_total": 1,
                "inserted": 1,
                "reinforced": 0,
                "skipped": 0,
                "recall_tested": 1,
                "recall_verified": 1,
            }
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


class LiveDbBindingTests(unittest.TestCase):
    def _fixture(self, td: str):
        base = Path(td)
        vault = base / "vault"
        store = base / "store"
        vault.mkdir()
        (store / "hippo").mkdir(parents=True)
        db = store / "hippo" / "brain.sqlite3"
        make_sqlite(db, "A")
        (vault / "note.md").write_text("live DB binding content", encoding="utf-8")
        return vault, store, db, core.metadata_paths(store)

    def _args(self, vault: Path, store: Path):
        return ["--vault-root", str(vault), "--store-root", str(store), "--apply", "--json"]

    def test_live_store_verifier_accepts_expected_open_sqlite_file(self):
        with tempfile.TemporaryDirectory() as td:
            _vault, _store, db, _paths = self._fixture(td)
            expected = core.semantic_db_identity(db)
            store = SqliteBackedFakeStore(db)
            try:
                core.verify_open_store_db_identity(store, expected)
            finally:
                store.close()

    def test_swap_during_open_fails_before_study_and_retry_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store_root, db, paths = self._fixture(td)
            original_saved = db.with_name("brain.sqlite3.expected")
            replacement_source = db.with_name("brain.sqlite3.replacement")
            make_sqlite(replacement_source, "B")
            first_events: list[tuple] = []

            def restore_original():
                if db.exists():
                    db.unlink()
                original_saved.replace(db)

            def swapped_open(_root: Path):
                # Reproduce the review finding exactly: the expected DB is moved
                # away during native open, DB B is opened at the canonical path,
                # and DB A is restored only when the store closes.
                db.replace(original_saved)
                replacement_source.replace(db)
                return SqliteBackedFakeStore(db, on_close=restore_original)

            first_runtime = core.IaiRuntime(
                "3.3.0",
                tag,
                native_study(first_events),
                swapped_open,
                core.verify_open_store_db_identity,
            )
            out = io.StringIO()
            with mock.patch.object(core, "load_iai_runtime", return_value=first_runtime), redirect_stdout(out):
                rc = pub.main(self._args(vault, store_root))
            self.assertEqual(rc, 1, out.getvalue())
            self.assertEqual(first_events, [])
            self.assertIn("open_store_db_identity_mismatch", out.getvalue())
            self.assertTrue(paths.pending.is_file())
            self.assertFalse(paths.state.exists())
            self.assertTrue(db.is_file())

            second_events: list[tuple] = []
            second_runtime = core.IaiRuntime(
                "3.3.0",
                tag,
                native_study(second_events),
                lambda _root: SqliteBackedFakeStore(db),
                core.verify_open_store_db_identity,
            )
            with mock.patch.object(core, "load_iai_runtime", return_value=second_runtime), redirect_stdout(io.StringIO()):
                rc = pub.main(self._args(vault, store_root))
            self.assertEqual(rc, 0)
            self.assertEqual(second_events, [("study", "note.md")])
            self.assertTrue(paths.state.is_file())
            self.assertFalse(paths.pending.exists())


if __name__ == "__main__":
    unittest.main()
