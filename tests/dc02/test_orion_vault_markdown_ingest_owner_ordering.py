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
    "orion_vault_markdown_ingest_owner_ordering", MODULE_PATH
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


class OwnerOrderingTests(unittest.TestCase):
    def _fixture(self, td: str, *, with_note: bool = True):
        base = Path(td)
        vault = base / "vault"
        store = base / "store"
        state = base / "state.json"
        vault.mkdir()
        if with_note:
            (vault / "a.md").write_text(
                "long enough source content", encoding="utf-8"
            )
        (store / "hippo").mkdir(parents=True)
        (store / "hippo" / "brain.sqlite3").write_bytes(b"fixture")
        return base, vault, store, state

    def _runtime(self, *, open_store=None, study=None):
        return mod.IaiRuntime(
            version="3.3.0",
            doc_tag=vendor_doc_tag_3_3_0,
            study_document=study or (lambda *_a, **_kw: {}),
            open_store=open_store or (lambda _path: FakeStore()),
        )

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

    def test_mutating_first_apply_writes_pending_before_owner_and_store_open(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store, state = self._fixture(td)
            pending = mod._pending_file_for(state)
            owner = mod._store_owner_file_for(store)
            open_calls: list[Path] = []
            runtime = self._runtime(
                open_store=lambda path: open_calls.append(path) or FakeStore(),
                study=lambda *_a, **_kw: self.fail("study reached after owner failure"),
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), mock.patch.object(
                mod,
                "write_store_owner_atomic",
                side_effect=mod.AdapterError("store_owner_write_failed:Injected"),
            ), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))

            self.assertEqual(rc, 1)
            self.assertIn("store_owner_write_failed:Injected", json.loads(output.getvalue())["error"])
            self.assertTrue(pending.is_file())
            self.assertFalse(owner.exists())
            self.assertFalse(state.exists())
            self.assertEqual(open_calls, [])

    def test_no_mutation_first_apply_commits_state_before_owner_claim(self):
        with tempfile.TemporaryDirectory() as td:
            _base, vault, store, state = self._fixture(td, with_note=False)
            owner = mod._store_owner_file_for(store)
            pending = mod._pending_file_for(state)
            runtime = self._runtime(
                open_store=lambda _path: self.fail("empty apply opened store")
            )
            output = io.StringIO()
            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime), mock.patch.object(
                mod,
                "write_store_owner_atomic",
                side_effect=mod.AdapterError("store_owner_write_failed:Injected"),
            ), redirect_stdout(output):
                rc = mod.main(self._args(vault, store, state))

            self.assertEqual(rc, 1)
            self.assertTrue(state.is_file())
            self.assertFalse(owner.exists())
            self.assertFalse(pending.exists())

            with mock.patch.object(mod, "load_iai_runtime", return_value=runtime):
                retry_output = io.StringIO()
                with redirect_stdout(retry_output):
                    retry_rc = mod.main(self._args(vault, store, state))
            self.assertEqual(retry_rc, 0, retry_output.getvalue())
            self.assertTrue(owner.is_file())
            self.assertTrue(state.is_file())
            self.assertFalse(pending.exists())


if __name__ == "__main__":
    unittest.main()
