from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
import sys
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dc02"
    / "orion_vault_markdown_ingest.py"
)
SPEC = importlib.util.spec_from_file_location("orion_vault_markdown_ingest", MODULE_PATH)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class MarkdownVaultScanTests(unittest.TestCase):
    def test_only_md_recursive_and_relative_posix(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            (root / "nested").mkdir(parents=True)
            (root / "A.md").write_text("# A\nalpha", encoding="utf-8")
            (root / "nested" / "B.MD").write_text("# B\nbeta", encoding="utf-8")
            (root / "nested" / "ignore.txt").write_text("no", encoding="utf-8")
            (root / "ignore.markdown").write_text("no", encoding="utf-8")
            notes = mod.scan_markdown_vault(root)
            self.assertEqual(
                [n.relative_path for n in notes],
                ["A.md", "nested/B.MD"],
            )

    def test_invalid_utf8_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            (root / "bad.md").write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(mod.AdapterError, "markdown_not_utf8"):
                mod.scan_markdown_vault(root)

    def test_oversize_fails_instead_of_silently_skipping(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            (root / "large.md").write_text("12345", encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "markdown_file_too_large"):
                mod.scan_markdown_vault(root, max_file_bytes=4)

    def test_file_cap_fails_instead_of_truncating(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            for i in range(3):
                (root / f"{i}.md").write_text(str(i), encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "vault_file_limit_exceeded"):
                mod.scan_markdown_vault(root, max_files=2)

    def test_symlinked_markdown_is_not_ingested(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            outside = Path(td) / "outside.md"
            root.mkdir()
            outside.write_text("outside", encoding="utf-8")
            (root / "safe.md").write_text("safe", encoding="utf-8")
            link = root / "linked.md"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            notes = mod.scan_markdown_vault(root)
            self.assertEqual([n.relative_path for n in notes], ["safe.md"])


class OwnershipTests(unittest.TestCase):
    def _note(self, rel: str, sha: str = "x"):
        return mod.NoteSnapshot(rel, f"/tmp/{rel}", 1, 1, sha)

    def test_doc_tag_collision_is_refused(self):
        notes = [self._note("a/b.md"), self._note("a-b.md")]
        with self.assertRaisesRegex(mod.AdapterError, "doc_tag_collision"):
            mod.validate_doc_tag_uniqueness(notes, lambda _name: "doc:a-b.md")

    def test_unique_doc_tags_are_returned_per_path(self):
        notes = [self._note("a.md"), self._note("b.md")]
        got = mod.validate_doc_tag_uniqueness(notes, lambda name: f"doc:{name}")
        self.assertEqual(got, {"a.md": "doc:a.md", "b.md": "doc:b.md"})


class PlanTests(unittest.TestCase):
    def _note(self, rel: str, sha: str):
        return mod.NoteSnapshot(rel, f"/tmp/{rel}", 1, 1, sha)

    def test_plan_new_changed_unchanged_deleted(self):
        notes = [
            self._note("new.md", "n"),
            self._note("changed.md", "new-hash"),
            self._note("same.md", "same-hash"),
        ]
        state = {
            "files": {
                "changed.md": {"sha256": "old-hash"},
                "same.md": {"sha256": "same-hash"},
                "gone.md": {"sha256": "gone"},
            }
        }
        plan = mod.build_plan(notes, state)
        self.assertEqual(plan.new, ("new.md",))
        self.assertEqual(plan.changed, ("changed.md",))
        self.assertEqual(plan.unchanged, ("same.md",))
        self.assertEqual(plan.deleted, ("gone.md",))

    def test_mtime_only_change_does_not_reinforce(self):
        note = mod.NoteSnapshot("same.md", "/tmp/same.md", 10, 999, "same")
        plan = mod.build_plan(
            [note],
            {"files": {"same.md": {"sha256": "same", "mtime_ns": 1}}},
        )
        self.assertEqual(plan.unchanged, ("same.md",))
        self.assertEqual(plan.mutation_count, 0)


class ApplyTests(unittest.TestCase):
    def test_current_files_are_studied_before_deleted_paths_are_faded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            current = root / "renamed.md"
            current.write_text("same content", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            plan = mod.SyncPlan(
                new=("renamed.md",),
                changed=(),
                unchanged=(),
                deleted=("old.md",),
            )
            calls = []

            def fake_study(_store, **kwargs):
                if "path" in kwargs:
                    calls.append(("study", kwargs["source_name"]))
                    return {"skipped": 0}
                calls.append(("fade", kwargs["source_name"]))
                return {"skipped": 0}

            mod.apply_plan(
                store=object(),
                vault_root=root,
                notes=[note],
                plan=plan,
                study_document=fake_study,
            )
            self.assertEqual(calls, [("study", "renamed.md"), ("fade", "old.md")])

    def test_partial_study_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            path = root / "a.md"
            path.write_text("content", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            plan = mod.SyncPlan(new=("a.md",), changed=(), unchanged=(), deleted=())

            def fake_study(_store, **_kwargs):
                return {"skipped": 1}

            with self.assertRaisesRegex(mod.AdapterError, "study_partial"):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[note],
                    plan=plan,
                    study_document=fake_study,
                )

    def test_file_changed_during_study_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            path = root / "a.md"
            path.write_text("before", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            plan = mod.SyncPlan(new=("a.md",), changed=(), unchanged=(), deleted=())

            def fake_study(_store, **_kwargs):
                path.write_text("after", encoding="utf-8")
                return {"skipped": 0}

            with self.assertRaisesRegex(mod.AdapterError, "markdown_changed_during_study"):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[note],
                    plan=plan,
                    study_document=fake_study,
                )


class StateTests(unittest.TestCase):
    def test_state_file_inside_vault_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            with self.assertRaisesRegex(mod.AdapterError, "state_file_inside_vault"):
                mod.validate_state_location(root / "state.json", root)

    def test_store_root_inside_vault_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            with self.assertRaisesRegex(mod.AdapterError, "store_root_inside_vault"):
                mod.validate_store_location(root / ".iai-mcp", root)

    def test_atomic_state_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = Path(td) / "state" / "sync.json"
            payload = {
                "schema_version": 1,
                "session_id": "vault-study",
                "vault_root": "X",
                "files": {"a.md": {"sha256": "abc"}},
            }
            mod.write_state_atomic(state_file, payload)
            self.assertEqual(json.loads(state_file.read_text(encoding="utf-8")), payload)
            leftovers = list(state_file.parent.glob("*.tmp"))
            self.assertEqual(leftovers, [])

    def test_state_root_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            other = Path(td) / "other"
            root.mkdir()
            other.mkdir()
            state_file = Path(td) / "state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "session_id": "vault-study",
                        "vault_root": str(other.resolve()),
                        "files": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(mod.AdapterError, "state_vault_root_mismatch"):
                mod.load_state(state_file, root)


if __name__ == "__main__":
    unittest.main()
