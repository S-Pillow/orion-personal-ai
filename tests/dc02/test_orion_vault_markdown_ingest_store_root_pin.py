from __future__ import annotations

import importlib.util
import io
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest.py"
SPEC = importlib.util.spec_from_file_location("dc02_store_root_pin_test", PUBLIC)
pub = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = pub
SPEC.loader.exec_module(pub)
core = pub.core


def tag(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


def native_study(_store, **kwargs):
    if kwargs.get("path") is None:
        return {
            "chunks_total": 0,
            "inserted": 0,
            "reinforced": 0,
            "skipped": 0,
            "recall_tested": 0,
            "recall_verified": 0,
        }
    Path(kwargs["path"]).read_bytes()
    return {
        "chunks_total": 1,
        "inserted": 1,
        "reinforced": 0,
        "skipped": 0,
        "recall_tested": 1,
        "recall_verified": 1,
    }


native_study.__module__ = "iai_mcp.study"
native_study.__name__ = "study_document"


class FakeStore:
    def close(self) -> None:
        return None


@unittest.skipIf(sys.platform.startswith("win"), "POSIX symlink-retarget fixture")
class StoreRootPinTests(unittest.TestCase):
    def test_store_root_alias_retarget_after_staging_cannot_split_metadata_from_db(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "vault"
            store_a = base / "store-a"
            store_b = base / "store-b"
            alias = base / "store-alias"
            vault.mkdir()
            for store in (store_a, store_b):
                (store / "hippo").mkdir(parents=True)
                (store / "hippo" / "brain.sqlite3").write_bytes(b"fixture-db")
            alias.symlink_to(store_a, target_is_directory=True)
            (vault / "note.md").write_text("canonical store pin content", encoding="utf-8")

            paths_a = core.metadata_paths(store_a)
            paths_b = core.metadata_paths(store_b)
            opened: list[Path] = []
            runtime = core.IaiRuntime(
                "3.3.0",
                tag,
                native_study,
                lambda root: opened.append(Path(root)) or FakeStore(),
            )
            original_stage = core.stage_plan_sources

            def stage_then_retarget(vault_root, store_root, notes, plan):
                # The coordinator must have pinned the canonical target before
                # any transaction state is derived.
                self.assertEqual(Path(store_root), store_a.resolve())
                staged = original_stage(vault_root, store_root, notes, plan)
                alias.unlink()
                alias.symlink_to(store_b, target_is_directory=True)
                self.assertEqual(alias.resolve(), store_b.resolve())
                return staged

            out = io.StringIO()
            args = [
                "--vault-root",
                str(vault),
                "--store-root",
                str(alias),
                "--apply",
                "--json",
            ]
            with (
                mock.patch.object(core, "load_iai_runtime", return_value=runtime),
                mock.patch.object(core, "stage_plan_sources", side_effect=stage_then_retarget),
                redirect_stdout(out),
            ):
                rc = pub.main(args)

            self.assertEqual(rc, 0, out.getvalue())
            self.assertEqual(opened, [store_a.resolve()])
            self.assertTrue(paths_a.state.is_file())
            self.assertTrue(paths_a.owner.is_file())
            self.assertFalse(paths_a.pending.exists())
            self.assertFalse(paths_b.root.exists())


if __name__ == "__main__":
    unittest.main()
