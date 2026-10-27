from __future__ import annotations

import importlib.util
import io
import json
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
    "orion_vault_markdown_ingest_deep_audit", MODULE_PATH
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


class DeepAuditTests(unittest.TestCase):
    def _fixture(self, td: str):
        base = Path(td)
        vault = base / "vault"
        store = base / "store"
        vault.mkdir()
        (store / "hippo").mkdir(parents=True)
        (store / "hippo" / "brain.sqlite3").write_bytes(b"fixture")
        return base, vault, store

    def _runtime(self, study=None, *, open_store=None):
        return mod.IaiRuntime(
            version="3.3.0",
            doc_tag=vendor_doc_tag_3_3_0,
            study_document=study or (lambda *_a, **_kw: {}),
            open_store=open_store or (lambda _path: FakeStore()),
        )

    def _args(self, vault: Path, store: Path, state: Path, *, apply=False):
        args = [
            "--vault-root",
            str(vault),
            "--store-root",
            str(store),
            "--state-file",
            str(state),
            "--json",
        ]
        if apply:
            args.append("--apply")
        return args

    def test_custom_state_file_cannot_alias_store_owner_marker(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store = self._fixture(td)
            (vault / "note.md").write_text("a sufficiently long note", encoding="utf-8")
            state = mod._store_owner_file_for(store)
            open_calls: list[Path] = []
            runtime = self._runtime(
                lambda *_a, **_kw: self.fail("study reached after metadata collision"),
                open_store=lambda path: open_calls.append(path) or FakeStore(),
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state, apply=True))
            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("metadata_path_collision:state:store_owner", result["error"])
            self.assertEqual(open_calls, [])
            self.assertFalse(state.exists())

    def test_custom_state_file_inside_native_hippo_namespace_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store = self._fixture(td)
            (vault / "note.md").write_text("a sufficiently long note", encoding="utf-8")
            state = store / "hippo" / "operator-state.json"
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime()), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))
            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("state_file_inside_semantic_store_namespace", result["error"])
            self.assertFalse(state.exists())

    def test_existing_state_symlink_is_rejected_before_read_or_store_open(self):
        with tempfile.TemporaryDirectory() as td:
            base, vault, store = self._fixture(td)
            (vault / "note.md").write_text("a sufficiently long note", encoding="utf-8")
            target = base / "outside-state.json"
            target.write_text("{}", encoding="utf-8")
            state = base / "state.json"
            try:
                state.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unavailable")
            open_calls: list[Path] = []
            runtime = self._runtime(
                open_store=lambda path: open_calls.append(path) or FakeStore()
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state, apply=True))
            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("metadata_path_is_reparse_point:state", result["error"])
            self.assertEqual(open_calls, [])
            self.assertEqual(target.read_text(encoding="utf-8"), "{}")

    def test_existing_state_directory_is_rejected_as_nonregular_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            base, vault, store = self._fixture(td)
            (vault / "note.md").write_text("a sufficiently long note", encoding="utf-8")
            state = base / "state.json"
            state.mkdir()
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime()), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))
            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("metadata_path_not_regular:state", result["error"])

    def test_store_orion_metadata_root_cannot_be_reparse_alias(self):
        with tempfile.TemporaryDirectory() as td:
            base, vault, store = self._fixture(td)
            (vault / "note.md").write_text("a sufficiently long note", encoding="utf-8")
            external = base / "external-orion"
            external.mkdir()
            try:
                (store / "orion").symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            state = base / "state.json"
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime()), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))
            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("store_metadata_root_is_reparse_point", result["error"])

    def test_owned_store_missing_checkpoint_and_pending_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            base, vault, store = self._fixture(td)
            (vault / "note.md").write_text("a sufficiently long note", encoding="utf-8")
            state = base / "state.json"
            owner = mod._store_owner_file_for(store)
            mod.write_store_owner_atomic(
                owner,
                mod._store_owner_payload(
                    vault_root=vault, store_root=store, state_file=state
                ),
            )
            self.assertFalse(state.exists())
            self.assertFalse(mod._pending_file_for(state).exists())
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime()), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))
            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("owned_store_missing_state_and_pending", result["error"])

    def test_below_vendor_capture_floor_fails_before_vendor_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            path = root / "tiny.md"
            path.write_text("tiny", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            calls: list[str] = []

            def study(_store, **kwargs):
                calls.append(kwargs["source_name"])
                return {
                    "chunks_total": 0,
                    "inserted": 0,
                    "reinforced": 0,
                    "skipped": 0,
                }

            with self.assertRaisesRegex(
                mod.AdapterError, "markdown_below_iai_capture_floor:tiny.md:4<12"
            ):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[note],
                    plan=mod.SyncPlan(
                        new=("tiny.md",), changed=(), unchanged=(), deleted=()
                    ),
                    study_document=study,
                )
            self.assertEqual(calls, [])

    def test_nonempty_zero_chunk_vendor_report_is_rejected_as_second_defense(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            path = root / "note.md"
            path.write_text("this source is long enough", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            report = {
                "chunks_total": 0,
                "inserted": 0,
                "reinforced": 0,
                "skipped": 0,
            }
            with self.assertRaisesRegex(
                mod.AdapterError, "study_no_chunks_for_nonempty_source:note.md"
            ):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[note],
                    plan=mod.SyncPlan(
                        new=("note.md",), changed=(), unchanged=(), deleted=()
                    ),
                    study_document=lambda *_a, **_kw: report,
                )

    def test_vendor_chunk_accounting_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            path = root / "note.md"
            path.write_text("this source is long enough", encoding="utf-8")
            note = mod.scan_markdown_vault(root)[0]
            report = {
                "chunks_total": 2,
                "inserted": 1,
                "reinforced": 0,
                "skipped": 0,
            }
            with self.assertRaisesRegex(
                mod.AdapterError, "study_chunk_accounting_mismatch:note.md:1!=2"
            ):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[note],
                    plan=mod.SyncPlan(
                        new=("note.md",), changed=(), unchanged=(), deleted=()
                    ),
                    study_document=lambda *_a, **_kw: report,
                )

    def test_empty_source_zero_chunk_vendor_report_is_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            path = root / "empty.md"
            path.write_bytes(b"")
            note = mod.scan_markdown_vault(root)[0]
            report = {
                "chunks_total": 0,
                "inserted": 0,
                "reinforced": 0,
                "skipped": 0,
            }
            result = mod.apply_plan(
                store=object(),
                vault_root=root,
                notes=[note],
                plan=mod.SyncPlan(
                    new=("empty.md",), changed=(), unchanged=(), deleted=()
                ),
                study_document=lambda *_a, **_kw: report,
            )
            self.assertEqual(result["studied"]["empty.md"]["chunks_total"], 0)

    def test_reparse_hippo_store_alias_is_rejected_before_store_open(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "vault"
            store = base / "store"
            actual_hippo = base / "actual-hippo"
            vault.mkdir()
            store.mkdir()
            actual_hippo.mkdir()
            (actual_hippo / "brain.sqlite3").write_bytes(b"fixture")
            (vault / "note.md").write_text("a sufficiently long note", encoding="utf-8")
            try:
                (store / "hippo").symlink_to(actual_hippo, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            state = base / "state.json"
            open_calls: list[Path] = []
            runtime = self._runtime(
                open_store=lambda path: open_calls.append(path) or FakeStore()
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state, apply=True))
            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("canonical_store_hippo_is_reparse_point", result["error"])
            self.assertEqual(open_calls, [])
            self.assertFalse(state.exists())

    def test_durable_metadata_writer_replaces_without_temp_leak(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            mod.write_state_atomic(path, {"generation": 1})
            mod.write_state_atomic(path, {"generation": 2})
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")), {"generation": 2}
            )
            leftovers = list(path.parent.glob(path.name + ".*.tmp"))
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
