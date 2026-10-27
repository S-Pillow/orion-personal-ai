from __future__ import annotations

import hashlib
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
    "orion_vault_markdown_ingest_recovery_hardening", MODULE_PATH
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
        "iai_version": mod.EXPECTED_IAI_VERSION,
        "successful_run_utc": "2026-10-27T05:00:00Z",
        "files": {path: state_entry(content, path) for path, content in files.items()},
    }
    state_file.write_text(json.dumps(payload), encoding="utf-8")


class FakeStore:
    def close(self) -> None:
        return None


class RecoveryHardeningTests(unittest.TestCase):
    def _paths(self, td: str):
        root = Path(td) / "vault"
        store_root = Path(td) / "store"
        state_file = Path(td) / "state.json"
        root.mkdir()
        (store_root / "hippo").mkdir(parents=True)
        (store_root / "hippo" / "brain.sqlite3").write_bytes(b"fixture")
        return root, store_root, state_file

    def _runtime(self, study, open_store=None):
        return mod.IaiRuntime(
            version="3.3.0",
            doc_tag=vendor_doc_tag_3_3_0,
            study_document=study,
            open_store=open_store or (lambda _path: FakeStore()),
        )

    def _args(self, root: Path, store_root: Path, state_file: Path, *, apply=False, json_mode=False):
        args = [
            "--vault-root",
            str(root),
            "--store-root",
            str(store_root),
            "--state-file",
            str(state_file),
        ]
        if apply:
            args.append("--apply")
        if json_mode:
            args.append("--json")
        return args

    def test_completed_pending_journal_does_not_reserve_old_doc_tag(self):
        """Codex P2 regression: completed ownership is no longer active ownership."""
        with tempfile.TemporaryDirectory() as td:
            root, store_root, state_file = self._paths(td)
            old_path = "a/b.md"
            write_success_state(state_file, root, {old_path: b"old"})
            fade_calls: list[dict[str, object]] = []

            def fade(_store, **kwargs):
                fade_calls.append(dict(kwargs))
                return {}

            pending_file = mod._pending_file_for(state_file)
            with mock.patch.object(mod, "load_iai_runtime", return_value=self._runtime(fade)), mock.patch.object(
                mod,
                "clear_pending_journal",
                side_effect=mod.AdapterError("pending_clear_failed:Injected"),
            ):
                self.assertEqual(
                    mod.main(self._args(root, store_root, state_file, apply=True)),
                    1,
                )
            self.assertEqual([call["source_name"] for call in fade_calls], [old_path])
            self.assertTrue(pending_file.is_file())
            committed = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(committed["files"], {})

            new_path = root / "a-b.md"
            new_path.write_text("replacement", encoding="utf-8")
            self.assertEqual(vendor_doc_tag_3_3_0(old_path), vendor_doc_tag_3_3_0("a-b.md"))

            stdout = io.StringIO()
            plan_runtime = self._runtime(
                lambda *_a, **_kw: self.fail("plan-only called study")
            )
            with mock.patch.object(mod, "load_iai_runtime", return_value=plan_runtime), redirect_stdout(stdout):
                rc = mod.main(
                    self._args(root, store_root, state_file, json_mode=True)
                )
            self.assertEqual(rc, 0)
            plan_result = json.loads(stdout.getvalue())
            self.assertEqual(plan_result["plan"]["new"], ["a-b.md"])

            study_calls: list[str] = []

            def study_new(_store, **kwargs):
                study_calls.append(kwargs["source_name"])
                return {}

            with mock.patch.object(
                mod, "load_iai_runtime", return_value=self._runtime(study_new)
            ):
                self.assertEqual(
                    mod.main(self._args(root, store_root, state_file, apply=True)),
                    0,
                )
            self.assertEqual(study_calls, ["a-b.md"])
            self.assertFalse(pending_file.exists())

    def test_active_pending_journal_still_reserves_doc_tag(self):
        with tempfile.TemporaryDirectory() as td:
            root, store_root, state_file = self._paths(td)
            (root / "a").mkdir()
            (root / "a" / "b.md").write_text("old-owner", encoding="utf-8")
            (root / "x.md").write_text("x", encoding="utf-8")

            def fail_second(_store, **kwargs):
                if kwargs["source_name"] == "x.md":
                    raise RuntimeError("injected")
                return {}

            with mock.patch.object(
                mod, "load_iai_runtime", return_value=self._runtime(fail_second)
            ):
                self.assertEqual(
                    mod.main(self._args(root, store_root, state_file, apply=True)),
                    1,
                )
            self.assertTrue(mod._pending_file_for(state_file).is_file())
            (root / "a" / "b.md").unlink()
            (root / "a-b.md").write_text("new-owner", encoding="utf-8")

            stdout = io.StringIO()
            with mock.patch.object(
                mod,
                "load_iai_runtime",
                return_value=self._runtime(lambda *_a, **_kw: {}),
            ), redirect_stdout(stdout):
                rc = mod.main(
                    self._args(root, store_root, state_file, json_mode=True)
                )
            self.assertEqual(rc, 1)
            result = json.loads(stdout.getvalue())
            self.assertIn("pending_doc_tag_collision", result["error"])

    def test_deleted_source_reappearing_before_fade_aborts_without_vendor_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            (root / "gone.md").write_text("back", encoding="utf-8")
            calls: list[dict[str, object]] = []
            with self.assertRaisesRegex(mod.AdapterError, "markdown_reappeared_before_fade:gone.md"):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[],
                    plan=mod.SyncPlan(new=(), changed=(), unchanged=(), deleted=("gone.md",)),
                    study_document=lambda _store, **kwargs: calls.append(dict(kwargs)) or {},
                )
            self.assertEqual(calls, [])

    def test_deleted_source_reappearing_during_fade_aborts_after_vendor_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            calls: list[dict[str, object]] = []

            def fade(_store, **kwargs):
                calls.append(dict(kwargs))
                (root / "gone.md").write_text("back", encoding="utf-8")
                return {}

            with self.assertRaisesRegex(mod.AdapterError, "markdown_reappeared_during_fade:gone.md"):
                mod.apply_plan(
                    store=object(),
                    vault_root=root,
                    notes=[],
                    plan=mod.SyncPlan(new=(), changed=(), unchanged=(), deleted=("gone.md",)),
                    study_document=fade,
                )
            self.assertEqual([call["source_name"] for call in calls], ["gone.md"])

    def test_unrelated_mid_apply_inventory_drift_prevents_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            root, store_root, state_file = self._paths(td)
            (root / "a.md").write_text("a", encoding="utf-8")

            def study_then_add_file(_store, **_kwargs):
                (root / "late.md").write_text("late", encoding="utf-8")
                return {}

            with mock.patch.object(
                mod,
                "load_iai_runtime",
                return_value=self._runtime(study_then_add_file),
            ):
                rc = mod.main(self._args(root, store_root, state_file, apply=True))
            self.assertEqual(rc, 1)
            self.assertFalse(state_file.exists())
            self.assertTrue(mod._pending_file_for(state_file).is_file())


if __name__ == "__main__":
    unittest.main()
