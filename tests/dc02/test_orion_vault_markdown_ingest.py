from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


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


def vendor_doc_tag_3_3_0(source_name: str) -> str:
    """Independent compatibility fixture copied from iai 3.3.0's _doc_tag rule."""
    slug = re.sub(r"[^a-z0-9._-]+", "-", source_name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


def state_payload(root: Path, files: dict | None = None, **overrides):
    payload = {
        "schema_version": mod.STATE_SCHEMA_VERSION,
        "session_id": mod.SESSION_ID,
        "vault_root": str(root.resolve()),
        "iai_version": mod.EXPECTED_IAI_VERSION,
        "successful_run_utc": "2026-10-27T05:00:00Z",
        "files": files or {},
    }
    payload.update(overrides)
    return payload


def state_entry(content: bytes = b"x", *, doc_tag: str = "doc:a.md"):
    import hashlib

    return {
        "size": len(content),
        "mtime_ns": 1,
        "sha256": hashlib.sha256(content).hexdigest(),
        "doc_tag": doc_tag,
    }


class MarkdownVaultScanTests(unittest.TestCase):
    def test_only_md_recursive_case_insensitive_and_relative_posix(self):
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

    def test_deterministic_casefold_then_literal_order(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            for name in ["z.md", "B.md", "a.md"]:
                (root / name).write_text(name, encoding="utf-8")
            first = [n.relative_path for n in mod.scan_markdown_vault(root)]
            second = [n.relative_path for n in mod.scan_markdown_vault(root)]
            self.assertEqual(first, ["a.md", "B.md", "z.md"])
            self.assertEqual(first, second)

    def test_invalid_utf8_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            (root / "bad.md").write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(mod.AdapterError, "markdown_not_utf8"):
                mod.scan_markdown_vault(root)

    def test_two_megabyte_boundary_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            (root / "boundary.md").write_bytes(b"a" * mod.MAX_SOURCE_FILE_BYTES)
            notes = mod.scan_markdown_vault(root)
            self.assertEqual(notes[0].size, mod.MAX_SOURCE_FILE_BYTES)

    def test_over_two_megabytes_fails_instead_of_silently_skipping(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            (root / "large.md").write_bytes(b"a" * (mod.MAX_SOURCE_FILE_BYTES + 1))
            with self.assertRaisesRegex(mod.AdapterError, "markdown_file_too_large"):
                mod.scan_markdown_vault(root)

    def test_file_cap_fails_instead_of_truncating(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            for i in range(3):
                (root / f"{i}.md").write_text(str(i), encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "vault_file_limit_exceeded"):
                mod.scan_markdown_vault(root, max_files=2)

    def test_symlinked_markdown_fails_entire_scan(self):
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
            with self.assertRaisesRegex(mod.AdapterError, "unsafe_reparse_markdown"):
                mod.scan_markdown_vault(root)

    def test_symlinked_directory_fails_entire_scan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            outside = Path(td) / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "note.md").write_text("outside", encoding="utf-8")
            link = root / "linked-dir"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            with self.assertRaisesRegex(mod.AdapterError, "unsafe_reparse_directory"):
                mod.scan_markdown_vault(root)

    def test_outside_root_target_is_rejected_by_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            outside = Path(td) / "outside.md"
            root.mkdir()
            outside.write_text("outside", encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "markdown_escaped_vault"):
                mod._strict_utf8_snapshot(outside, root.resolve())

    def test_casefold_path_collision_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            first = root / "A.md"
            second = root / "a.md"
            first.write_text("one", encoding="utf-8")
            try:
                second.write_text("two", encoding="utf-8")
            except OSError:
                self.skipTest("filesystem is case-insensitive")
            try:
                if first.samefile(second):
                    self.skipTest("filesystem is case-insensitive")
            except OSError:
                self.skipTest("cannot distinguish case variants")
            with self.assertRaisesRegex(mod.AdapterError, "casefold_path_collision"):
                mod.scan_markdown_vault(root)


class OwnershipAndVendorContractTests(unittest.TestCase):
    def _note(self, rel: str, sha: str = "x"):
        return mod.NoteSnapshot(rel, f"/tmp/{rel}", 1, 1, sha)

    def test_vendor_doc_tag_fixture_matches_expected_examples(self):
        self.assertEqual(vendor_doc_tag_3_3_0("Projects/Orion/Shared Brain.md"), "doc:projects-orion-shared-brain.md")
        self.assertEqual(vendor_doc_tag_3_3_0("A  B.md"), "doc:a-b.md")
        self.assertEqual(vendor_doc_tag_3_3_0("___"), "doc:___")
        self.assertLessEqual(len(vendor_doc_tag_3_3_0("x" * 100 + ".md")) - 4, 64)

    def test_doc_tag_collision_is_refused(self):
        notes = [self._note("a/b.md"), self._note("a-b.md")]
        with self.assertRaisesRegex(mod.AdapterError, "doc_tag_collision"):
            mod.validate_doc_tag_uniqueness(notes, vendor_doc_tag_3_3_0)

    def test_unique_doc_tags_are_returned_per_path(self):
        notes = [self._note("a.md"), self._note("b.md")]
        got = mod.validate_doc_tag_uniqueness(notes, vendor_doc_tag_3_3_0)
        self.assertEqual(got, {"a.md": "doc:a.md", "b.md": "doc:b.md"})

    def test_study_signature_contract_accepts_iai_330_shape(self):
        def fake_doc_tag(source_name):
            return "doc:" + source_name

        def fake_study(store, *, path=None, text=None, source_name=None, session_id="study", link_top_k=5, critic=None):
            return {}

        mod._validate_vendor_contract(fake_doc_tag, fake_study)

    def test_study_signature_contract_rejects_missing_critic(self):
        def fake_doc_tag(source_name):
            return "doc:" + source_name

        def bad_study(store, *, path=None, text=None, source_name=None, session_id="study"):
            return {}

        with self.assertRaisesRegex(mod.AdapterError, "iai_study_signature_mismatch"):
            mod._validate_vendor_contract(fake_doc_tag, bad_study)


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

    def test_rename_becomes_new_plus_deleted(self):
        note = self._note("new-name.md", "same")
        plan = mod.build_plan(
            [note],
            {"files": {"old-name.md": {"sha256": "same"}}},
        )
        self.assertEqual(plan.new, ("new-name.md",))
        self.assertEqual(plan.deleted, ("old-name.md",))


class ApplyTests(unittest.TestCase):
    def test_current_files_are_studied_before_deleted_paths_are_faded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            current = root / "renamed.md"
            current.write_text("same content", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            plan = mod.SyncPlan(
                new=("renamed.md",), changed=(), unchanged=(), deleted=("old.md",)
            )
            calls = []

            def fake_study(_store, **kwargs):
                calls.append(kwargs)
                return {"skipped": 0}

            mod.apply_plan(
                store=object(),
                vault_root=root,
                notes=[note],
                plan=plan,
                study_document=fake_study,
            )
            self.assertEqual(calls[0]["source_name"], "renamed.md")
            self.assertEqual(calls[0]["session_id"], "vault-study")
            self.assertIsNone(calls[0]["critic"])
            self.assertIn("path", calls[0])
            self.assertEqual(calls[1], {
                "text": "",
                "source_name": "old.md",
                "session_id": "vault-study",
                "critic": None,
            })

    def test_changed_file_is_restudied_and_unchanged_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            changed = root / "changed.md"
            same = root / "same.md"
            changed.write_text("new", encoding="utf-8")
            same.write_text("same", encoding="utf-8")
            notes = mod.scan_markdown_vault(root)
            calls = []

            def fake_study(_store, **kwargs):
                calls.append(kwargs["source_name"])
                return {}

            mod.apply_plan(
                store=object(),
                vault_root=root,
                notes=notes,
                plan=mod.SyncPlan(new=(), changed=("changed.md",), unchanged=("same.md",), deleted=()),
                study_document=fake_study,
            )
            self.assertEqual(calls, ["changed.md"])

    def test_partial_skipped_study_fails(self):
        self._assert_partial_report_fails({"skipped": 1})

    def test_partial_char_truncation_fails(self):
        self._assert_partial_report_fails({"chars_truncated": 1})

    def test_partial_chunk_truncation_fails(self):
        self._assert_partial_report_fails({"chunks_truncated": 1})

    def _assert_partial_report_fails(self, report):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            path = root / "a.md"
            path.write_text("content", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            plan = mod.SyncPlan(new=("a.md",), changed=(), unchanged=(), deleted=())
            with self.assertRaisesRegex(mod.AdapterError, "study_partial"):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[note],
                    plan=plan,
                    study_document=lambda _store, **_kwargs: report,
                )

    def test_file_changed_before_study_fails_without_vendor_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            path = root / "a.md"
            path.write_text("before", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            path.write_text("after", encoding="utf-8")
            calls = []
            with self.assertRaisesRegex(mod.AdapterError, "markdown_changed_before_study"):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[note],
                    plan=mod.SyncPlan(new=("a.md",), changed=(), unchanged=(), deleted=()),
                    study_document=lambda _store, **kwargs: calls.append(kwargs) or {},
                )
            self.assertEqual(calls, [])

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
                    store=object(), vault_root=root, notes=[note], plan=plan, study_document=fake_study
                )

    def test_vendor_exception_is_wrapped_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            (root / "a.md").write_text("content", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]

            def fail(_store, **_kwargs):
                raise RuntimeError("boom")

            with self.assertRaisesRegex(mod.AdapterError, "study_call_failed:a.md:RuntimeError"):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[note],
                    plan=mod.SyncPlan(new=("a.md",), changed=(), unchanged=(), deleted=()),
                    study_document=fail,
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

    def test_missing_state_is_clean_bootstrap_state_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            got = mod.load_state(Path(td) / "missing.json", root)
            self.assertEqual(got["files"], {})
            self.assertEqual(got["iai_version"], "3.3.0")
            self.assertIsNone(got["successful_run_utc"])

    def test_atomic_state_round_trip_contains_no_raw_note_content(self):
        with tempfile.TemporaryDirectory() as td:
            state_file = Path(td) / "state" / "sync.json"
            payload = {
                "schema_version": 1,
                "session_id": "vault-study",
                "vault_root": "X",
                "iai_version": "3.3.0",
                "successful_run_utc": "2026-10-27T05:00:00Z",
                "files": {"a.md": state_entry(b"secret note body")},
            }
            mod.write_state_atomic(state_file, payload)
            text = state_file.read_text(encoding="utf-8")
            self.assertEqual(json.loads(text), payload)
            self.assertNotIn("secret note body", text)
            self.assertEqual(list(state_file.parent.glob("*.tmp")), [])

    def test_state_root_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            other = Path(td) / "other"
            root.mkdir()
            other.mkdir()
            state_file = Path(td) / "state.json"
            state_file.write_text(json.dumps(state_payload(other)), encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "state_vault_root_mismatch"):
                mod.load_state(state_file, root)

    def test_corrupt_json_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            state_file = Path(td) / "state.json"
            state_file.write_text("{bad", encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "state_read_failed"):
                mod.load_state(state_file, root)

    def test_state_wrong_iai_version_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            state_file = Path(td) / "state.json"
            state_file.write_text(json.dumps(state_payload(root, iai_version="3.2.0")), encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "state_iai_version_mismatch"):
                mod.load_state(state_file, root)

    def test_state_invalid_file_metadata_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            state_file = Path(td) / "state.json"
            bad = state_payload(root, {"a.md": {"sha256": "not-a-hash"}})
            state_file.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(mod.AdapterError, "state_file_size_invalid|state_file_sha256_invalid"):
                mod.load_state(state_file, root)

    def test_state_payload_records_success_timestamp_and_hash_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            (root / "a.md").write_text("hello", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            payload = mod._state_payload(root, [note], {"a.md": "doc:a.md"}, "3.3.0")
            self.assertEqual(payload["iai_version"], "3.3.0")
            self.assertIn("successful_run_utc", payload)
            self.assertEqual(payload["files"]["a.md"]["size"], 5)
            self.assertEqual(payload["files"]["a.md"]["doc_tag"], "doc:a.md")
            self.assertEqual(len(payload["files"]["a.md"]["sha256"]), 64)


class MainDryRunTests(unittest.TestCase):
    def test_default_plan_does_not_open_store_or_write_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            store = Path(td) / "store"
            state = Path(td) / "state.json"
            root.mkdir()
            (root / "a.md").write_text("hello", encoding="utf-8")
            open_calls = []
            fake_runtime = mod.IaiRuntime(
                version="3.3.0",
                doc_tag=vendor_doc_tag_3_3_0,
                study_document=lambda *_args, **_kwargs: self.fail("study called in dry run"),
                open_store=lambda path: open_calls.append(path),
            )
            with mock.patch.object(mod, "load_iai_runtime", return_value=fake_runtime):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    rc = mod.main([
                        "--vault-root", str(root),
                        "--store-root", str(store),
                        "--state-file", str(state),
                    ])
            self.assertEqual(rc, 0)
            self.assertEqual(open_calls, [])
            self.assertFalse(state.exists())
            self.assertIn("ORION_VAULT_MARKDOWN_INGEST_STORE_MUTATION=false", stdout.getvalue())

    def test_apply_failure_does_not_advance_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            store_root = Path(td) / "store"
            state_file = Path(td) / "state.json"
            root.mkdir()
            (root / "a.md").write_text("hello", encoding="utf-8")
            (store_root / "hippo").mkdir(parents=True)
            (store_root / "hippo" / "brain.sqlite3").write_bytes(b"fixture")

            class FakeStore:
                def close(self):
                    return None

            fake_runtime = mod.IaiRuntime(
                version="3.3.0",
                doc_tag=vendor_doc_tag_3_3_0,
                study_document=lambda *_args, **_kwargs: {"skipped": 1},
                open_store=lambda _path: FakeStore(),
            )
            with mock.patch.object(mod, "load_iai_runtime", return_value=fake_runtime):
                rc = mod.main([
                    "--vault-root", str(root),
                    "--store-root", str(store_root),
                    "--state-file", str(state_file),
                    "--apply",
                ])
            self.assertEqual(rc, 1)
            self.assertFalse(state_file.exists())

    def test_successful_apply_advances_checkpoint_only_after_store_close(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            store_root = Path(td) / "store"
            state_file = Path(td) / "state.json"
            root.mkdir()
            (root / "a.md").write_text("hello", encoding="utf-8")
            (store_root / "hippo").mkdir(parents=True)
            (store_root / "hippo" / "brain.sqlite3").write_bytes(b"fixture")
            events = []

            class FakeStore:
                def close(self):
                    events.append("close")

            fake_runtime = mod.IaiRuntime(
                version="3.3.0",
                doc_tag=vendor_doc_tag_3_3_0,
                study_document=lambda *_args, **_kwargs: events.append("study") or {},
                open_store=lambda _path: events.append("open") or FakeStore(),
            )
            original_write = mod.write_state_atomic

            def tracked_write(path, payload):
                events.append("state")
                original_write(path, payload)

            with mock.patch.object(mod, "load_iai_runtime", return_value=fake_runtime), mock.patch.object(mod, "write_state_atomic", side_effect=tracked_write):
                rc = mod.main([
                    "--vault-root", str(root),
                    "--store-root", str(store_root),
                    "--state-file", str(state_file),
                    "--apply",
                ])
            self.assertEqual(rc, 0)
            self.assertEqual(events, ["open", "study", "close", "state"])
            persisted = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["files"]["a.md"]["doc_tag"], "doc:a.md")


if __name__ == "__main__":
    unittest.main()
