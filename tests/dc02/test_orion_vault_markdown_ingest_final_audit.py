from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import subprocess
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
    "orion_vault_markdown_ingest_final_audit", MODULE_PATH
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


def vendor_doc_tag_3_3_0(source_name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", source_name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


def native_study(report: dict[str, int]):
    def _study(_store, **_kwargs):
        return dict(report)

    _study.__module__ = "iai_mcp.study"
    _study.__name__ = "study_document"
    return _study


class FakeStore:
    def close(self) -> None:
        return None


class FinalAuditTests(unittest.TestCase):
    def _fixture(self, td: str):
        base = Path(td)
        vault = base / "vault"
        store = base / "store"
        state = base / "state.json"
        vault.mkdir()
        (store / "hippo").mkdir(parents=True)
        (store / "hippo" / "brain.sqlite3").write_bytes(b"fixture")
        return base, vault, store, state

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

    def _runtime(self, report: dict[str, int], open_store=None):
        return mod.IaiRuntime(
            version="3.3.0",
            doc_tag=vendor_doc_tag_3_3_0,
            study_document=native_study(report),
            open_store=open_store or (lambda _path: FakeStore()),
        )

    def test_whitespace_only_note_fails_before_pending_owner_or_store_open(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store, state = self._fixture(td)
            (vault / "spaces.md").write_text("   \n\t  ", encoding="utf-8")
            opens: list[Path] = []
            runtime = self._runtime(
                {
                    "chunks_total": 0,
                    "inserted": 0,
                    "reinforced": 0,
                    "skipped": 0,
                    "recall_tested": 0,
                    "recall_verified": 0,
                },
                open_store=lambda path: opens.append(path) or FakeStore(),
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))
            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("markdown_below_iai_capture_floor:spaces.md:0<12", result["error"])
            self.assertEqual(opens, [])
            self.assertFalse(state.exists())
            self.assertFalse(mod._pending_file_for(state).exists())
            self.assertFalse(mod._store_owner_file_for(store).exists())

    def test_crlf_short_note_uses_vendor_universal_newline_length_before_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store, state = self._fixture(td)
            raw = b"a\r\nb\r\nc\r\nd\r\ne"
            self.assertEqual(len(raw), 13)
            (vault / "crlf.md").write_bytes(raw)
            opens: list[Path] = []
            runtime = self._runtime(
                {
                    "chunks_total": 0,
                    "inserted": 0,
                    "reinforced": 0,
                    "skipped": 0,
                    "recall_tested": 0,
                    "recall_verified": 0,
                },
                open_store=lambda path: opens.append(path) or FakeStore(),
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))
            self.assertEqual(rc, 1)
            result = json.loads(output.getvalue())
            self.assertIn("markdown_below_iai_capture_floor:crlf.md:9<12", result["error"])
            self.assertEqual(opens, [])
            self.assertFalse(state.exists())
            self.assertFalse(mod._pending_file_for(state).exists())
            self.assertFalse(mod._store_owner_file_for(store).exists())

    def test_zero_byte_note_remains_valid_native_empty_document(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store, state = self._fixture(td)
            (vault / "empty.md").write_bytes(b"")
            calls: list[str] = []

            def study(_store, **kwargs):
                calls.append(kwargs["source_name"])
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
            runtime = mod.IaiRuntime(
                version="3.3.0",
                doc_tag=vendor_doc_tag_3_3_0,
                study_document=study,
                open_store=lambda _path: FakeStore(),
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))
            self.assertEqual(rc, 0, output.getvalue())
            self.assertEqual(calls, ["empty.md"])
            self.assertTrue(state.is_file())

    def test_chunk_floor_rejects_source_changed_after_admission(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            path = vault / "note.md"
            path.write_text("long enough original content", encoding="utf-8")
            note = mod.scan_markdown_vault(vault)[0]
            path.write_text("long enough replacement content", encoding="utf-8")
            with self.assertRaisesRegex(
                mod.AdapterError, "markdown_changed_before_chunk_floor:note.md"
            ):
                mod._validate_native_chunk_floor("note.md", note)

    def test_snapshot_over_limit_fails_with_bounded_reader(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            path = vault / "large.md"
            path.write_bytes(b"abcdefghijk")
            with self.assertRaisesRegex(mod.AdapterError, "markdown_file_too_large"):
                mod._strict_utf8_snapshot(path, vault.resolve(), max_file_bytes=10)

    @unittest.skipIf(sys.platform.startswith("win") or not hasattr(os, "mkfifo"), "POSIX FIFO regression")
    def test_fifo_markdown_is_rejected_without_blocking_admission(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            os.mkfifo(vault / "pipe.md")
            code = r'''
import importlib.util
import sys
from pathlib import Path
module_path = Path(sys.argv[1])
vault = Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("dc02_fifo_probe", module_path)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
try:
    mod.scan_markdown_vault(vault)
except mod.AdapterError as exc:
    print(str(exc))
    raise SystemExit(0 if "markdown_not_regular_file:" in str(exc) else 2)
raise SystemExit(3)
'''
            result = subprocess.run(
                [sys.executable, "-c", code, str(MODULE_PATH), str(vault)],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("markdown_not_regular_file:", result.stdout)

    def test_native_recall_self_test_miss_rejects_checkpointable_report(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            path = vault / "note.md"
            path.write_text("this content is long enough", encoding="utf-8")
            note = mod.scan_markdown_vault(vault)[0]
            study = native_study(
                {
                    "chunks_total": 1,
                    "inserted": 1,
                    "reinforced": 0,
                    "skipped": 0,
                    "recall_tested": 1,
                    "recall_verified": 0,
                }
            )
            with self.assertRaisesRegex(
                mod.AdapterError, "study_recall_self_test_miss:note.md:0!=1"
            ):
                mod.apply_plan(
                    store=object(),
                    vault_root=vault,
                    notes=[note],
                    plan=mod.SyncPlan(new=("note.md",), changed=(), unchanged=(), deleted=()),
                    study_document=study,
                )

    def test_native_recall_self_test_must_test_expected_sample(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            path = vault / "note.md"
            path.write_text("this content is long enough", encoding="utf-8")
            note = mod.scan_markdown_vault(vault)[0]
            study = native_study(
                {
                    "chunks_total": 1,
                    "inserted": 1,
                    "reinforced": 0,
                    "skipped": 0,
                    "recall_tested": 0,
                    "recall_verified": 0,
                }
            )
            with self.assertRaisesRegex(
                mod.AdapterError, "study_recall_test_count_mismatch:note.md:0!=1"
            ):
                mod.apply_plan(
                    store=object(),
                    vault_root=vault,
                    notes=[note],
                    plan=mod.SyncPlan(new=("note.md",), changed=(), unchanged=(), deleted=()),
                    study_document=study,
                )

    def test_native_recall_self_test_full_success_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            path = vault / "note.md"
            path.write_text("this content is long enough", encoding="utf-8")
            note = mod.scan_markdown_vault(vault)[0]
            study = native_study(
                {
                    "chunks_total": 1,
                    "inserted": 1,
                    "reinforced": 0,
                    "skipped": 0,
                    "recall_tested": 1,
                    "recall_verified": 1,
                }
            )
            result = mod.apply_plan(
                store=object(),
                vault_root=vault,
                notes=[note],
                plan=mod.SyncPlan(new=("note.md",), changed=(), unchanged=(), deleted=()),
                study_document=study,
            )
            self.assertEqual(result["studied"]["note.md"]["recall_verified"], 1)

    def test_vendor_counters_must_be_real_integers(self):
        with self.assertRaisesRegex(mod.AdapterError, "study_report_invalid:note.md:skipped"):
            mod._report_count({"skipped": False}, "skipped", "note.md")
        with self.assertRaisesRegex(mod.AdapterError, "study_report_invalid:note.md:chunks_total"):
            mod._report_count({"chunks_total": 1.0}, "chunks_total", "note.md")

    @unittest.skipIf(sys.platform.startswith("win"), "POSIX directory fsync contract")
    def test_new_metadata_directory_chain_is_fsynced_before_use(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            target = base / "one" / "two" / "three"
            synced: list[Path] = []
            original = mod._fsync_directory

            def tracked(path: Path):
                synced.append(Path(path))
                original(Path(path))

            with mock.patch.object(mod, "_fsync_directory", side_effect=tracked):
                mod._ensure_directory_durable(target)
            self.assertTrue(target.is_dir())
            self.assertIn(base, synced)
            self.assertIn(base / "one", synced)
            self.assertIn(base / "one" / "two", synced)
            self.assertIn(target, synced)


if __name__ == "__main__":
    unittest.main()
