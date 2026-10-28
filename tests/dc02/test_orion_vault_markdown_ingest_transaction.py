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

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest.py"
SPEC = importlib.util.spec_from_file_location("dc02_public_test", PUBLIC)
pub = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = pub
SPEC.loader.exec_module(pub)
core = pub.core


def tag(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


class FakeStore:
    def __init__(self, events: list[str] | None = None):
        self.events = events if events is not None else []
    def close(self):
        self.events.append("close")


def native_study(events: list[tuple], *, fail_on: str | None = None):
    def study(_store, **kwargs):
        source = kwargs["source_name"]
        if "path" in kwargs and kwargs.get("path") is not None:
            path = Path(kwargs["path"])
            events.append(("study", source, path, path.read_bytes()))
            if fail_on == source:
                raise RuntimeError("injected")
            return {
                "chunks_total": 1,
                "inserted": 1,
                "reinforced": 0,
                "skipped": 0,
                "recall_tested": 1,
                "recall_verified": 1,
            }
        events.append(("fade", source))
        if fail_on == source:
            raise RuntimeError("injected")
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


class TransactionTests(unittest.TestCase):
    def _fixture(self, td: str):
        base = Path(td)
        vault = base / "vault"
        store = base / "store"
        vault.mkdir()
        (store / "hippo").mkdir(parents=True)
        (store / "hippo" / "brain.sqlite3").write_bytes(b"fixture-db")
        return vault, store, core.metadata_paths(store)

    def _runtime(self, study, open_store):
        return core.IaiRuntime("3.3.0", tag, study, open_store)

    def _args(self, vault: Path, store: Path):
        return ["--vault-root", str(vault), "--store-root", str(store), "--apply", "--json"]

    def test_pending_and_owner_exist_before_store_open_and_study_uses_stage(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            live = vault / "note.md"
            live.write_text("original admitted content", encoding="utf-8")
            events: list[tuple] = []

            def open_store(_root):
                self.assertTrue(paths.pending.is_file())
                self.assertTrue(paths.owner.is_file())
                events.append(("open",))
                return FakeStore()

            runtime = self._runtime(native_study(events), open_store)
            out = io.StringIO()
            with mock.patch.object(core, "load_iai_runtime", return_value=runtime), redirect_stdout(out):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 0, out.getvalue())
            study_event = next(e for e in events if e[0] == "study")
            staged_path = study_event[2]
            self.assertNotEqual(staged_path, live)
            self.assertNotEqual(staged_path.parent, vault)
            self.assertEqual(study_event[3], b"original admitted content")
            self.assertTrue(paths.state.is_file())
            self.assertFalse(paths.pending.exists())

    def test_live_edit_after_freeze_does_not_invalidate_applied_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            live = vault / "note.md"
            live.write_text("snapshot version one", encoding="utf-8")
            events: list[tuple] = []
            runtime = self._runtime(native_study(events), lambda _root: FakeStore())
            original_stage = core.stage_plan_sources

            def stage_then_edit(vault_root, store_root, notes, plan):
                staged = original_stage(vault_root, store, notes, plan)
                live.write_text("new live version after freeze", encoding="utf-8")
                return staged

            out = io.StringIO()
            with (
                mock.patch.object(core, "load_iai_runtime", return_value=runtime),
                mock.patch.object(core, "stage_plan_sources", side_effect=stage_then_edit),
                redirect_stdout(out),
            ):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 0, out.getvalue())
            studied = next(e for e in events if e[0] == "study")
            self.assertEqual(studied[3], b"snapshot version one")
            state = core.load_state(paths.state, vault, store)
            self.assertEqual(
                state["files"]["note.md"]["sha256"],
                core.hashlib.sha256(b"snapshot version one").hexdigest(),
            )
            current = core.scan_markdown_vault(vault)
            plan = core.build_plan(current, state)
            self.assertEqual(plan.changed, ("note.md",))

    @unittest.skipIf(sys.platform.startswith("win"), "literal backslash source is POSIX-only fixture")
    def test_invalid_portable_source_fails_before_recovery_owner_or_store_open(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            (vault / ("a" + chr(92) + "b.md")).write_text("invalid portable source content", encoding="utf-8")
            opened: list[Path] = []
            runtime = self._runtime(native_study([]), lambda root: opened.append(root) or FakeStore())
            out = io.StringIO()
            with mock.patch.object(core, "load_iai_runtime", return_value=runtime), redirect_stdout(out):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 1)
            self.assertIn("source_name_invalid", out.getvalue())
            self.assertEqual(opened, [])
            self.assertFalse(paths.state.exists())
            self.assertFalse(paths.pending.exists())
            self.assertFalse(paths.owner.exists())

    def test_store_open_failure_leaves_active_recovery_and_retry_restudies(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            (vault / "note.md").write_text("recoverable admitted content", encoding="utf-8")
            first = self._runtime(native_study([]), lambda _root: (_ for _ in ()).throw(RuntimeError("boom")))
            with mock.patch.object(core, "load_iai_runtime", return_value=first), redirect_stdout(io.StringIO()):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 1)
            self.assertTrue(paths.pending.is_file())
            self.assertTrue(paths.owner.is_file())
            self.assertFalse(paths.state.exists())

            events: list[tuple] = []
            second = self._runtime(native_study(events), lambda _root: FakeStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=second), redirect_stdout(io.StringIO()):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 0)
            self.assertEqual([e[0] for e in events], ["study"])
            self.assertFalse(paths.pending.exists())
            self.assertTrue(paths.state.is_file())

    def test_completed_pending_cleanup_never_replays_semantic_work(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            (vault / "note.md").write_text("cleanup failure content", encoding="utf-8")
            first_events: list[tuple] = []
            runtime = self._runtime(native_study(first_events), lambda _root: FakeStore())

            def fail_clear(_path):
                raise core.AdapterError("pending_clear_failed:Injected")

            with (
                mock.patch.object(core, "load_iai_runtime", return_value=runtime),
                mock.patch.object(core, "clear_pending", side_effect=fail_clear),
                redirect_stdout(io.StringIO()),
            ):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 1)
            self.assertTrue(paths.state.is_file())
            self.assertTrue(paths.pending.is_file())
            self.assertEqual([e[0] for e in first_events], ["study"])

            replay_events: list[tuple] = []
            retry = self._runtime(native_study(replay_events), lambda _root: self.fail("store must not open"))
            with mock.patch.object(core, "load_iai_runtime", return_value=retry), redirect_stdout(io.StringIO()):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 0)
            self.assertEqual(replay_events, [])
            self.assertFalse(paths.pending.exists())

    def test_failed_mid_apply_reconciles_already_mutated_source_even_after_revert(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            a = vault / "a.md"; b = vault / "b.md"
            a.write_text("base a content long enough", encoding="utf-8")
            b.write_text("base b content long enough", encoding="utf-8")
            seed_events: list[tuple] = []
            seed = self._runtime(native_study(seed_events), lambda _root: FakeStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=seed), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 0)

            a.write_text("changed a content long enough", encoding="utf-8")
            b.write_text("changed b content long enough", encoding="utf-8")
            fail_events: list[tuple] = []
            failing = self._runtime(native_study(fail_events, fail_on="b.md"), lambda _root: FakeStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=failing), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 1)
            self.assertTrue(paths.pending.exists())
            self.assertEqual([e[1] for e in fail_events if e[0] == "study"], ["a.md", "b.md"])

            a.write_text("base a content long enough", encoding="utf-8")
            b.write_text("base b content long enough", encoding="utf-8")
            retry_events: list[tuple] = []
            retry = self._runtime(native_study(retry_events), lambda _root: FakeStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=retry), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 0)
            self.assertEqual([e[1] for e in retry_events if e[0] == "study"], ["a.md", "b.md"])

    def test_new_then_deleted_recovery_fades_with_pending_owned_tag(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            note = vault / "new.md"
            note.write_text("new source studied before crash", encoding="utf-8")
            first_events: list[tuple] = []

            class CloseFailStore(FakeStore):
                def close(self):
                    raise RuntimeError("close crash")

            first = self._runtime(native_study(first_events), lambda _root: CloseFailStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=first), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 1)
            self.assertEqual([e[0] for e in first_events], ["study"])
            self.assertTrue(paths.pending.exists())
            self.assertFalse(paths.state.exists())

            note.unlink()
            second_events: list[tuple] = []
            failing_fade = self._runtime(native_study(second_events, fail_on="new.md"), lambda _root: FakeStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=failing_fade), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 1)
            self.assertEqual([e[0] for e in second_events], ["fade"])
            raw = json.loads(paths.pending.read_text(encoding="utf-8"))
            self.assertEqual(raw["base_files_sha256"], raw["target_files_sha256"])
            self.assertNotEqual(raw["base_checkpoint_id"], raw["target_checkpoint_id"])

            third_events: list[tuple] = []
            third = self._runtime(native_study(third_events), lambda _root: FakeStore())
            with mock.patch.object(core, "load_iai_runtime", return_value=third), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 0)
            self.assertEqual([e[0] for e in third_events], ["fade"])
            self.assertFalse(paths.pending.exists())
            state = core.load_state(paths.state, vault, store)
            self.assertEqual(state["files"], {})

    def test_hardlinked_lock_and_semantic_db_are_rejected_without_alias_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            sentinel = Path(td) / "sentinel.bin"
            sentinel.write_bytes(b"SENTINEL")
            paths.root.mkdir(parents=True, exist_ok=True)
            try:
                os.link(sentinel, paths.lock)
            except OSError as exc:
                self.skipTest(f"hardlinks unavailable: {exc}")
            with self.assertRaisesRegex(core.AdapterError, "apply_lock_has_multiple_links"):
                core.acquire_apply_lock(paths.lock)
            self.assertEqual(sentinel.read_bytes(), b"SENTINEL")
            paths.lock.unlink()

            db = store / "hippo" / "brain.sqlite3"
            db.unlink()
            os.link(sentinel, db)
            with self.assertRaisesRegex(core.AdapterError, "semantic_db_has_multiple_links"):
                core.validate_store(vault, store, require_db=True)
            self.assertEqual(sentinel.read_bytes(), b"SENTINEL")

    def test_plan_only_does_not_create_metadata_namespace(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            (vault / "note.md").write_text("plan only content", encoding="utf-8")
            runtime = self._runtime(native_study([]), lambda _root: self.fail("plan must not open store"))
            args = ["--vault-root", str(vault), "--store-root", str(store), "--json"]
            with mock.patch.object(core, "load_iai_runtime", return_value=runtime), redirect_stdout(io.StringIO()):
                rc = pub.main(args)
            self.assertEqual(rc, 0)
            self.assertFalse(paths.root.exists())

    def test_no_mutation_apply_does_not_open_semantic_store(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            runtime = self._runtime(native_study([]), lambda _root: self.fail("no-op apply must not open store"))
            with mock.patch.object(core, "load_iai_runtime", return_value=runtime), redirect_stdout(io.StringIO()):
                self.assertEqual(pub.main(self._args(vault, store)), 0)
            self.assertTrue(paths.state.exists())
            self.assertTrue(paths.owner.exists())
            self.assertFalse(paths.pending.exists())

    def test_owned_store_missing_state_and_pending_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            vault, store, paths = self._fixture(td)
            paths.root.mkdir(parents=True, exist_ok=True)
            core._atomic_write(paths.owner, core.owner_payload(vault, store), "owner")
            runtime = self._runtime(native_study([]), lambda _root: self.fail("must not open store"))
            out = io.StringIO()
            with mock.patch.object(core, "load_iai_runtime", return_value=runtime), redirect_stdout(out):
                rc = pub.main(self._args(vault, store))
            self.assertEqual(rc, 1)
            self.assertIn("owned_store_missing_state_and_pending", out.getvalue())

    def test_custom_state_file_option_is_not_part_of_surface(self):
        with mock.patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit):
                core.parse_args(["--state-file", "elsewhere.json"])

    def test_lock_serializes_processes(self):
        with tempfile.TemporaryDirectory() as td:
            lock_path = Path(td) / "store" / "orion" / "vault-markdown-ingest.apply.lock"
            code = r'''
import importlib.util, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("lock_child", Path(sys.argv[1]))
mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
lock = mod.acquire_apply_lock(Path(sys.argv[2]))
print("READY", flush=True)
time.sleep(5)
lock.close()
'''
            child = subprocess.Popen(
                [sys.executable, "-c", code, str(core.__file__), str(lock_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(child.stdout.readline().strip(), "READY")
                with self.assertRaisesRegex(core.AdapterError, "apply_lock_unavailable"):
                    core.acquire_apply_lock(lock_path)
            finally:
                child.terminate()
                child.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
