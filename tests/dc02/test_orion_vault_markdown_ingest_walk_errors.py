from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dc02"
    / "orion_vault_markdown_ingest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "orion_vault_markdown_ingest_walk_error_tests",
    MODULE_PATH,
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class WalkEnumerationFailureTests(unittest.TestCase):
    def test_walk_enumeration_error_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "vault"
            root.mkdir()
            blocked = root / "blocked"

            def fake_walk(
                _root,
                *,
                topdown=True,
                onerror=None,
                followlinks=False,
            ):
                self.assertTrue(topdown)
                self.assertFalse(followlinks)
                self.assertIsNotNone(onerror)
                exc = PermissionError("denied")
                exc.filename = str(blocked)
                onerror(exc)
                yield str(root), [], []

            with mock.patch.object(mod.os, "walk", side_effect=fake_walk):
                with self.assertRaisesRegex(
                    mod.AdapterError,
                    r"vault_walk_failed:.*blocked.*PermissionError",
                ):
                    mod.scan_markdown_vault(root)


if __name__ == "__main__":
    unittest.main()
