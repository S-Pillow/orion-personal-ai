from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
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
    "orion_vault_markdown_ingest_pending_journal", MODULE_PATH
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


def vendor_doc_tag_3_3_0(source_name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", source_name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


def state_entry(content: bytes, path: str) -> dict[str, object]:
    return {
        "size": len(content),
        "mtime_ns": 1,
        "sha256": hashlib.sha256(content).hexdigest(),
        "doc_tag": vendor_doc_tag_3_3_0(path),
    }


def write_success_state(state_file: Path, root: Path, files: dict[str, bytes]) -> None:
    payload = {
        "schema_version": mod.STATE_SCHEMA_VERSION,
        "session_id": mod.SESSION_ID,
        "vault_root": str(root.resolve()),
        "store_root": str((state_file.parent / "store").resolve()),
        "iai_version": mod.EXPECTED_IAI_VERSION,
        "successful_run_utc": "2026-10-27T05:00:00Z",
        "files": {path: state_entry(content, path) for path, content in files.items()},
    }
    state_file.write_text(json.dumps(payload), encoding="utf-8")


class FakeStore:
    def close(self) -> None:
        return None


class PendingJournalRecoveryTests(unittest.TestCase):
    def _runtime(self, study, open_store=None):
        return mod.IaiRuntime(
            version="3.3.0",
            doc_tag=vendor_doc_tag_3_3_0,
            study_document=study,
            open_store=open_store or (lambda _path: FakeStore()),
        )

    def _paths(self, td: str):
        root = Path(td) / "vault"
        store_root = Path(td) / "store"
        state_file = Path(td) / "state.json"
        root.mkdir()
        (store_root / "hippo").mkdir(parents=True)
        (store_root / "hippo" / "brain.sqlite3").write_bytes(b"fixture")
        return root, store_root, state_file

    def _apply_args(self, root: Path, store_root: Path, state_file: Path):
        return [
            "--vault-root",
            str(root),
            "--store-root",
            str(store_root),
            "--state-file",
            str(state_file),
            "--apply",
        ]

    def test_failed_run_forces_reverted_changed_file_to_be_restudied(self):
        with tempfile.TemporaryDirectory() as td:
            root, store_root, state_file = self._paths(td)
            old_a = b"original-a"
            old_b = b"original-b"
            (root / "a.md").write_bytes(b"edited-a")
            (root / "b.md").write_bytes(b"edited-b")
            write_success_state(state_file, root, {"a.md": old_a, "b.md": old_b})

            first_calls: list[str] = []

            def first_study(_store, **kwargs):
                rel = kwargs["source_name"]
                first_calls.append(rel)
                if rel == "b.md":
                    raise RuntimeError("injected failure")
                return {}

            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(first_study)):
                rc = mod.main(self._apply_args(root, store_root, state_file))
            self.assertEqual(rc, 1)
            self.assertEqual(first_calls, ["a.md", "b.md"])
            pending_file = mod._pending_file_for(state_file)
            self.assertTrue(pending_file.is_file())
            persisted = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(
                persisted["files"]["a.md"]["sha256"],
                hashlib.sha256(old_a).hexdigest(),
            )

            (root / "a.md").write_bytes(old_a)
            retry_calls: list[str] = []

            def retry_study(_store, **kwargs):
                retry_calls.append(kwargs["source_name"])
                return {}

            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(retry_study)):
                rc = mod.main(self._apply_args(root, store_root, state_file))
            self.assertEqual(rc, 0)
            self.assertEqual(retry_calls, ["a.md", "b.md"])
            self.assertFalse(pending_file.exists())

    def test_newly_studied_file_deleted_before_retry_is_faded(self):
        with tempfile.TemporaryDirectory() as td:
            root, store_root, state_file = self._paths(td)
            (root / "a.md").write_text("new-a", encoding="utf-8")
            (root / "b.md").write_text("new-b", encoding="utf-8")

            def first_study(_store, **kwargs):
                if kwargs["source_name"] == "b.md":
                    raise RuntimeError("injected failure")
                return {}

            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(first_study)):
                rc = mod.main(self._apply_args(root, store_root, state_file))
            self.assertEqual(rc, 1)
            self.assertFalse(state_file.exists())
            pending_file = mod._pending_file_for(state_file)
            self.assertTrue(pending_file.is_file())

            (root / "a.md").unlink()
            retry_calls: list[dict[str, object]] = []

            def retry_study(_store, **kwargs):
                retry_calls.append(dict(kwargs))
                return {}

            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(retry_study)):
                rc = mod.main(self._apply_args(root, store_root, state_file))
            self.assertEqual(rc, 0)
            self.assertEqual(retry_calls[0]["source_name"], "b.md")
            self.assertEqual(
                retry_calls[1],
                {
                    "text": "",
                    "source_name": "a.md",
                    "session_id": "vault-study",
                    "critic": None,
                },
            )
            self.assertFalse(pending_file.exists())

    def test_completed_checkpoint_with_leftover_journal_does_not_restudy(self):
        with tempfile.TemporaryDirectory() as td:
            root, store_root, state_file = self._paths(td)
            note_path = root / "a.md"
            note_path.write_text("content", encoding="utf-8")
            first_calls: list[str] = []

            def first_study(_store, **kwargs):
                first_calls.append(kwargs["source_name"])
                return {}

            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(first_study)), mock.patch.object(
                mod,
                "clear_pending_journal",
                side_effect=mod.AdapterError("pending_clear_failed:Injected"),
            ):
                rc = mod.main(self._apply_args(root, store_root, state_file))
            self.assertEqual(rc, 1)
            self.assertEqual(first_calls, ["a.md"])
            pending_file = mod._pending_file_for(state_file)
            self.assertTrue(state_file.is_file())
            self.assertTrue(pending_file.is_file())

            pending = json.loads(pending_file.read_text(encoding="utf-8"))
            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["checkpoint_id"], pending["target_checkpoint_id"])
            self.assertNotEqual(pending["base_checkpoint_id"], pending["target_checkpoint_id"])

            before_state = state_file.read_bytes()
            before_pending = pending_file.read_bytes()
            stat_before = note_path.stat()
            os.utime(
                note_path,
                ns=(stat_before.st_atime_ns, stat_before.st_mtime_ns + 1_000_000_000),
            )

            retry_calls: list[str] = []

            def should_not_study(_store, **kwargs):
                retry_calls.append(kwargs["source_name"])
                return {}

            def should_not_open(_path):
                self.fail("completed pending journal reopened the semantic store")

            with mock.patch.object(
                mod,
                "load_iai_runtime",
                return_value=self._runtime(should_not_study, open_store=should_not_open),
            ), mock.patch.object(
                mod,
                "clear_pending_journal",
                side_effect=mod.AdapterError("pending_clear_failed:InjectedAgain"),
            ):
                rc = mod.main(self._apply_args(root, store_root, state_file))
            self.assertEqual(rc, 1)
            self.assertEqual(retry_calls, [])
            self.assertEqual(state_file.read_bytes(), before_state)
            self.assertEqual(pending_file.read_bytes(), before_pending)

            with mock.patch.object(
                mod,
                "load_iai_runtime",
                return_value=self._runtime(should_not_study, open_store=should_not_open),
            ):
                rc = mod.main(self._apply_args(root, store_root, state_file))
            self.assertEqual(rc, 0)
            self.assertEqual(retry_calls, [])
            self.assertFalse(pending_file.exists())
            refreshed = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(refreshed["checkpoint_id"], state["checkpoint_id"])
            self.assertNotEqual(
                refreshed["files"]["a.md"]["mtime_ns"],
                state["files"]["a.md"]["mtime_ns"],
            )

    def test_plan_only_reconciles_active_pending_without_mutating_sidecars(self):
        with tempfile.TemporaryDirectory() as td:
            root, store_root, state_file = self._paths(td)
            old_a = b"original-a"
            old_b = b"original-b"
            (root / "a.md").write_bytes(b"edited-a")
            (root / "b.md").write_bytes(b"edited-b")
            write_success_state(state_file, root, {"a.md": old_a, "b.md": old_b})

            def fail_second(_store, **kwargs):
                if kwargs["source_name"] == "b.md":
                    raise RuntimeError("injected failure")
                return {}

            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(fail_second)):
                self.assertEqual(mod.main(self._apply_args(root, store_root, state_file)), 1)

            (root / "a.md").write_bytes(old_a)
            pending_file = mod._pending_file_for(state_file)
            before_pending = pending_file.read_bytes()
            before_state = state_file.read_bytes()
            fake_runtime = self._runtime(
                lambda *_args, **_kwargs: self.fail("plan-only called study")
            )
            stdout = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=fake_runtime), redirect_stdout(stdout):
                rc = mod.main(
                    [
                        "--vault-root",
                        str(root),
                        "--store-root",
                        str(store_root),
                        "--state-file",
                        str(state_file),
                        "--json",
                    ]
                )
            self.assertEqual(rc, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["plan"]["changed"], ["a.md", "b.md"])
            self.assertEqual(pending_file.read_bytes(), before_pending)
            self.assertEqual(state_file.read_bytes(), before_state)

    def test_second_failed_recovery_with_equal_file_maps_remains_active(self):
        """P1 regression: equal base/target file maps cannot mean completed."""
        with tempfile.TemporaryDirectory() as td:
            root, store_root, state_file = self._paths(td)
            (root / "a.md").write_text("a", encoding="utf-8")
            (root / "b.md").write_text("b", encoding="utf-8")

            first_calls: list[str] = []

            def initial_study(_store, **kwargs):
                rel = kwargs["source_name"]
                first_calls.append(rel)
                if rel == "b.md":
                    raise RuntimeError("initial failure")
                return {}

            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(initial_study)):
                self.assertEqual(mod.main(self._apply_args(root, store_root, state_file)), 1)
            self.assertEqual(first_calls, ["a.md", "b.md"])
            self.assertFalse(state_file.exists())

            (root / "a.md").unlink()
            (root / "b.md").unlink()
            second_calls: list[str] = []

            def failed_recovery(_store, **kwargs):
                rel = kwargs["source_name"]
                second_calls.append(rel)
                if rel == "b.md":
                    raise RuntimeError("recovery failure")
                return {}

            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(failed_recovery)):
                self.assertEqual(mod.main(self._apply_args(root, store_root, state_file)), 1)
            self.assertEqual(second_calls, ["a.md", "b.md"])

            pending_file = mod._pending_file_for(state_file)
            pending = json.loads(pending_file.read_text(encoding="utf-8"))
            self.assertEqual(pending["base_files_sha256"], pending["target_files_sha256"])
            self.assertNotEqual(pending["base_checkpoint_id"], pending["target_checkpoint_id"])

            final_calls: list[dict[str, object]] = []

            def final_recovery(_store, **kwargs):
                final_calls.append(dict(kwargs))
                return {}

            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(final_recovery)):
                self.assertEqual(mod.main(self._apply_args(root, store_root, state_file)), 0)
            self.assertEqual(
                [call["source_name"] for call in final_calls], ["a.md", "b.md"]
            )
            self.assertTrue(all(call.get("text") == "" for call in final_calls))
            self.assertFalse(pending_file.exists())
            persisted = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertRegex(persisted["checkpoint_id"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
