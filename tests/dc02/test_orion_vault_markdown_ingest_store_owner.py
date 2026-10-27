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
    "orion_vault_markdown_ingest_store_owner", MODULE_PATH
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


class StoreOwnerTests(unittest.TestCase):
    def _store(self, root: Path) -> Path:
        store = root / "store"
        (store / "hippo").mkdir(parents=True)
        (store / "hippo" / "brain.sqlite3").write_bytes(b"fixture")
        return store

    def _runtime(self, study, *, open_store=None):
        return mod.IaiRuntime(
            version="3.3.0",
            doc_tag=vendor_doc_tag_3_3_0,
            study_document=study,
            open_store=open_store or (lambda _path: FakeStore()),
        )

    def _args(self, vault: Path, store: Path, state: Path, *, apply=False, json_mode=False):
        args = [
            "--vault-root",
            str(vault),
            "--store-root",
            str(store),
            "--state-file",
            str(state),
        ]
        if apply:
            args.append("--apply")
        if json_mode:
            args.append("--json")
        return args

    def test_plan_only_does_not_claim_unowned_store(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "vault"
            vault.mkdir()
            (vault / "a.md").write_text("a", encoding="utf-8")
            store = self._store(base)
            state = base / "state.json"
            owner = mod._store_owner_file_for(store)
            runtime = self._runtime(
                lambda *_a, **_kw: self.fail("plan-only called study")
            )
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime):
                self.assertEqual(mod.main(self._args(vault, store, state)), 0)
            self.assertFalse(owner.exists())
            self.assertFalse(state.exists())

    def test_successful_apply_claims_store_for_exact_vault_and_state(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "vault"
            vault.mkdir()
            (vault / "a.md").write_text("a", encoding="utf-8")
            store = self._store(base)
            state = base / "state.json"
            runtime = self._runtime(lambda *_a, **_kw: {})
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime):
                self.assertEqual(
                    mod.main(self._args(vault, store, state, apply=True)), 0
                )
            owner = json.loads(
                mod._store_owner_file_for(store).read_text(encoding="utf-8")
            )
            self.assertEqual(owner["schema_version"], mod.STORE_OWNER_SCHEMA_VERSION)
            self.assertEqual(owner["vault_root"], str(vault.resolve()))
            self.assertEqual(owner["store_root"], mod._canonical_path_text(store))
            self.assertEqual(owner["state_file"], mod._canonical_path_text(state))
            self.assertEqual(owner["iai_version"], "3.3.0")

    def test_different_vault_cannot_sequentially_reclaim_same_store(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            first_vault = base / "vault-a"
            second_vault = base / "vault-b"
            first_vault.mkdir()
            second_vault.mkdir()
            (first_vault / "a.md").write_text("a", encoding="utf-8")
            (second_vault / "a.md").write_text("b", encoding="utf-8")
            store = self._store(base)
            first_state = base / "state-a.json"
            second_state = base / "state-b.json"
            runtime = self._runtime(lambda *_a, **_kw: {})
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime):
                self.assertEqual(
                    mod.main(self._args(first_vault, store, first_state, apply=True)),
                    0,
                )

            open_calls: list[Path] = []
            second_runtime = self._runtime(
                lambda *_a, **_kw: self.fail("mismatched owner reached study"),
                open_store=lambda path: open_calls.append(path) or FakeStore(),
            )
            stdout = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=second_runtime), redirect_stdout(stdout):
                rc = mod.main(
                    self._args(
                        second_vault, store, second_state, apply=True, json_mode=True
                    )
                )
            self.assertEqual(rc, 1)
            result = json.loads(stdout.getvalue())
            self.assertIn("store_owner_vault_root_mismatch", result["error"])
            self.assertEqual(open_calls, [])
            self.assertFalse(second_state.exists())

    def test_different_state_file_cannot_reclaim_same_store(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "vault"
            vault.mkdir()
            (vault / "a.md").write_text("a", encoding="utf-8")
            store = self._store(base)
            first_state = base / "state-a.json"
            second_state = base / "state-b.json"
            runtime = self._runtime(lambda *_a, **_kw: {})
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime):
                self.assertEqual(
                    mod.main(self._args(vault, store, first_state, apply=True)), 0
                )

            stdout = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), redirect_stdout(stdout):
                rc = mod.main(
                    self._args(
                        vault, store, second_state, apply=True, json_mode=True
                    )
                )
            self.assertEqual(rc, 1)
            result = json.loads(stdout.getvalue())
            self.assertIn("store_owner_state_file_mismatch", result["error"])

    def test_store_open_failure_leaves_preopen_pending_journal_for_retry(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            vault = base / "vault"
            vault.mkdir()
            (vault / "a.md").write_text("a", encoding="utf-8")
            store = self._store(base)
            state = base / "state.json"
            pending = mod._pending_file_for(state)
            owner = mod._store_owner_file_for(store)

            def fail_open(_path):
                self.assertTrue(owner.is_file())
                self.assertTrue(pending.is_file())
                raise RuntimeError("injected open failure")

            failing = self._runtime(
                lambda *_a, **_kw: self.fail("study called after open failure"),
                open_store=fail_open,
            )
            with mock.patch.object(mod, "load_iai_runtime", return_value=failing):
                self.assertEqual(
                    mod.main(self._args(vault, store, state, apply=True)), 1
                )
            self.assertFalse(state.exists())
            self.assertTrue(owner.is_file())
            self.assertTrue(pending.is_file())
            pending_payload = json.loads(pending.read_text(encoding="utf-8"))
            self.assertEqual(
                pending_payload["store_root"], mod._canonical_path_text(store)
            )

            calls: list[str] = []

            def study(_store, **kwargs):
                calls.append(kwargs["source_name"])
                return {}

            working = self._runtime(study)
            with mock.patch.object(mod, "load_iai_runtime", return_value=working):
                self.assertEqual(
                    mod.main(self._args(vault, store, state, apply=True)), 0
                )
            self.assertEqual(calls, ["a.md"])
            self.assertTrue(state.is_file())
            self.assertFalse(pending.exists())
            self.assertTrue(owner.is_file())


if __name__ == "__main__":
    unittest.main()
