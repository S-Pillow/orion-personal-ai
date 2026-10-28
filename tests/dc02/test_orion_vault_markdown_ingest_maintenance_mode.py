from __future__ import annotations

import importlib.util
import io
import re
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest.py"
SPEC = importlib.util.spec_from_file_location("dc02_maintenance_mode_test", PUBLIC)
pub = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = pub
SPEC.loader.exec_module(pub)
core = pub.core


def tag(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


def native_study(store, *, path=None, text=None, source_name, session_id, critic):
    if path is not None:
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


native_study.__module__ = "iai_mcp.study"
native_study.__name__ = "study_document"


class MaintenanceModeTests(unittest.TestCase):
    def test_pinned_runtime_requests_native_exclusive_store_lock(self):
        package = types.ModuleType("iai_mcp")
        package.__path__ = []
        hippo = types.ModuleType("iai_mcp.hippo")
        store_mod = types.ModuleType("iai_mcp.store")
        study_mod = types.ModuleType("iai_mcp.study")

        class AccessMode:
            EXCLUSIVE = object()
            SHARED = object()

        calls: list[tuple[Path, object, bool]] = []

        class MemoryStore:
            def __init__(self, root, *, access_mode, persist_index):
                calls.append((Path(root), access_mode, persist_index))

        def doc_tag(source_name: str) -> str:
            return tag(source_name)

        hippo.AccessMode = AccessMode
        store_mod.MemoryStore = MemoryStore
        study_mod._doc_tag = doc_tag
        study_mod.study_document = native_study

        modules = {
            "iai_mcp": package,
            "iai_mcp.hippo": hippo,
            "iai_mcp.store": store_mod,
            "iai_mcp.study": study_mod,
        }
        with (
            mock.patch.dict(sys.modules, modules, clear=False),
            mock.patch.object(core.importlib.metadata, "version", return_value="3.3.0"),
            tempfile.TemporaryDirectory() as td,
        ):
            runtime = core.load_iai_runtime()
            root = Path(td) / "store"
            runtime.open_store(root)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], root)
        self.assertIs(calls[0][1], AccessMode.EXCLUSIVE)
        self.assertFalse(calls[0][2])
        self.assertFalse(hasattr(runtime, "verify_open_store"))
        self.assertFalse(hasattr(core, "verify_open_store_db_identity"))
        self.assertFalse(hasattr(core, "_open_descriptor_matches_identity"))

    def test_native_exclusive_open_failure_leaves_recovery_active(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "vault"
            store = base / "store"
            vault.mkdir()
            (store / "hippo").mkdir(parents=True)
            (store / "hippo" / "brain.sqlite3").write_bytes(b"fixture-db")
            (vault / "note.md").write_text("maintenance lock content", encoding="utf-8")
            paths = core.metadata_paths(store)

            def locked_open(_root: Path):
                raise RuntimeError("HippoLockHeldError: stop daemon first")

            runtime = core.IaiRuntime("3.3.0", tag, native_study, locked_open)
            out = io.StringIO()
            with mock.patch.object(core, "load_iai_runtime", return_value=runtime), redirect_stdout(out):
                rc = pub.main([
                    "--vault-root", str(vault),
                    "--store-root", str(store),
                    "--apply", "--json",
                ])

            self.assertEqual(rc, 1, out.getvalue())
            self.assertIn("store_open_failed", out.getvalue())
            self.assertTrue(paths.pending.is_file())
            self.assertTrue(paths.owner.is_file())
            self.assertFalse(paths.state.exists())


if __name__ == "__main__":
    unittest.main()
