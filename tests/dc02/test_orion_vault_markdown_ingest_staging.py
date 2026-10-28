from __future__ import annotations

import importlib.util
import tempfile
import unittest
from unittest import mock
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest_core.py"
SPEC = importlib.util.spec_from_file_location("dc02_stage_test", CORE)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class StagingTests(unittest.TestCase):
    def test_study_receives_immutable_staged_path_not_live_vault_path(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            live = vault / "note.md"
            live.write_text("original admitted content", encoding="utf-8")
            notes = mod.scan_markdown_vault(vault)
            plan = mod.SyncPlan(new=("note.md",), changed=(), unchanged=(), deleted=())
            store = Path(td) / "store"
            store.mkdir()
            staged = mod.stage_plan_sources(vault, store, notes, plan)
            try:
                stage_path = staged.paths["note.md"]
                self.assertNotEqual(stage_path, live)
                self.assertEqual(stage_path.read_text(encoding="utf-8"), "original admitted content")
                self.assertEqual(stage_path.stat().st_mtime_ns, notes[0].mtime_ns)
                live.write_text("changed after freeze", encoding="utf-8")
                seen = {}

                def study(_store, **kwargs):
                    seen["path"] = Path(kwargs["path"])
                    seen["text"] = Path(kwargs["path"]).read_text(encoding="utf-8")
                    seen["source"] = kwargs["source_name"]
                    return {"skipped": 0, "chars_truncated": 0, "chunks_truncated": 0}

                report = mod.apply_plan(object(), staged.paths, plan, study)
                self.assertEqual(seen["path"], stage_path)
                self.assertEqual(seen["text"], "original admitted content")
                self.assertEqual(seen["source"], "note.md")
                self.assertIn("note.md", report["studied"])
            finally:
                staged.close()

    def test_temp_root_inside_vault_or_store_is_rejected_before_stage_creation(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            store = Path(td) / "store"
            vault.mkdir(); store.mkdir()
            (vault / "note.md").write_text("immutable staging boundary", encoding="utf-8")
            notes = mod.scan_markdown_vault(vault)
            plan = mod.SyncPlan(new=("note.md",), changed=(), unchanged=(), deleted=())
            before_vault = set(vault.iterdir())
            with mock.patch.object(mod.tempfile, "gettempdir", return_value=str(vault)):
                with self.assertRaisesRegex(mod.AdapterError, "staging_temp_root_inside_vault"):
                    mod.stage_plan_sources(vault, store, notes, plan)
            self.assertEqual(set(vault.iterdir()), before_vault)
            with mock.patch.object(mod.tempfile, "gettempdir", return_value=str(store)):
                with self.assertRaisesRegex(mod.AdapterError, "staging_temp_root_inside_store"):
                    mod.stage_plan_sources(vault, store, notes, plan)

    def test_source_change_before_staging_aborts(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"; vault.mkdir()
            path = vault / "note.md"
            path.write_text("original admitted content", encoding="utf-8")
            notes = mod.scan_markdown_vault(vault)
            path.write_text("replacement before freeze", encoding="utf-8")
            (Path(td) / "store").mkdir()
            plan = mod.SyncPlan(new=("note.md",), changed=(), unchanged=(), deleted=())
            with self.assertRaisesRegex(mod.AdapterError, "markdown_changed_before_staging"):
                mod.stage_plan_sources(vault, Path(td) / "store", notes, plan)

    def test_whitespace_and_zero_byte_are_left_to_native_semantics(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"; vault.mkdir()
            (vault / "space.md").write_text("   \n\t", encoding="utf-8")
            (vault / "empty.md").write_bytes(b"")
            notes = mod.scan_markdown_vault(vault)
            plan = mod.SyncPlan(new=("empty.md", "space.md"), changed=(), unchanged=(), deleted=())
            store = Path(td) / "store"
            store.mkdir()
            staged = mod.stage_plan_sources(vault, store, notes, plan)
            calls = []
            try:
                def study(_store, **kwargs):
                    calls.append((kwargs["source_name"], Path(kwargs["path"]).read_bytes()))
                    return {"skipped": 0, "chars_truncated": 0, "chunks_truncated": 0}
                mod.apply_plan(object(), staged.paths, plan, study)
            finally:
                staged.close()
            self.assertEqual([x[0] for x in calls], ["empty.md", "space.md"])
            self.assertEqual(calls[0][1], b"")

    def test_native_zero_chunk_document_is_valid_native_semantics(self):
        def study(_store, **_kwargs):
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
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td) / "0.md"
            stage.write_text("   \n\t", encoding="utf-8")
            plan = mod.SyncPlan(new=("space.md",), changed=(), unchanged=(), deleted=())
            result = mod.apply_plan(object(), {"space.md": stage}, plan, study)
            self.assertEqual(result["studied"]["space.md"]["chunks_total"], 0)

    def test_apply_order_is_new_then_changed_then_deleted(self):
        calls = []
        def study(_store, **kwargs):
            calls.append(kwargs["source_name"])
            return {"skipped": 0, "chars_truncated": 0, "chunks_truncated": 0}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            n = root / "n.md"; c = root / "c.md"
            n.write_text("n", encoding="utf-8"); c.write_text("c", encoding="utf-8")
            plan = mod.SyncPlan(new=("n.md",), changed=("c.md",), unchanged=(), deleted=("d.md",))
            mod.apply_plan(object(), {"n.md": n, "c.md": c}, plan, study)
        self.assertEqual(calls, ["n.md", "c.md", "d.md"])

    def test_native_report_accounting_and_recall_are_fail_closed(self):
        def native(report):
            def study(_store, **_kwargs):
                return dict(report)
            study.__module__ = "iai_mcp.study"
            study.__name__ = "study_document"
            return study

        with tempfile.TemporaryDirectory() as td:
            stage = Path(td) / "0.md"; stage.write_text("content", encoding="utf-8")
            plan = mod.SyncPlan(new=("note.md",), changed=(), unchanged=(), deleted=())
            with self.assertRaisesRegex(mod.AdapterError, "study_recall_self_test_miss"):
                mod.apply_plan(
                    object(), {"note.md": stage}, plan,
                    native({
                        "chunks_total": 1, "inserted": 1, "reinforced": 0,
                        "skipped": 0, "recall_tested": 1, "recall_verified": 0,
                    })
                )


if __name__ == "__main__":
    unittest.main()
