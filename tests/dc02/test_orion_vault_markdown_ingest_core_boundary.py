from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DC02_DIR = ROOT / "scripts" / "dc02"
CORE_PATH = DC02_DIR / "orion_vault_markdown_ingest_core.py"
LEGACY_SOURCE_PATH = DC02_DIR / "orion_vault_markdown_ingest_core.source"
PUBLIC_PATH = DC02_DIR / "orion_vault_markdown_ingest.py"


class CoreEntrypointBoundaryTests(unittest.TestCase):
    def test_core_file_refuses_direct_cli_execution(self):
        result = subprocess.run(
            [sys.executable, str(CORE_PATH), "--apply"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn(
            "internal_core_entrypoint_disabled_use_orion_vault_markdown_ingest.py",
            result.stderr,
        )

    def test_imported_core_main_is_also_fail_closed(self):
        spec = importlib.util.spec_from_file_location("dc02_core_boundary_test", CORE_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = module.main(["--apply"])
        self.assertEqual(rc, 2)
        self.assertIn(
            "internal_core_entrypoint_disabled_use_orion_vault_markdown_ingest.py",
            stderr.getvalue(),
        )

    def test_legacy_executable_source_sidecar_is_absent(self):
        self.assertFalse(
            LEGACY_SOURCE_PATH.exists(),
            "legacy executable core source sidecar must not be shipped",
        )

    def test_core_contains_no_transaction_main_or_dynamic_source_loader(self):
        core_text = CORE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("store = runtime.open_store(store_root)", core_text)
        self.assertNotIn("exec(compile(", core_text)
        self.assertNotIn("orion_vault_markdown_ingest_core.source", core_text)
        self.assertNotIn("target_checkpoint_id = secrets.token_hex(32)", core_text)
        self.assertIn("internal_core_entrypoint_disabled", core_text)

    def test_public_coordinator_is_the_only_transaction_cli(self):
        public_text = PUBLIC_PATH.read_text(encoding="utf-8")
        self.assertIn("store = runtime.open_store(store_root)", public_text)
        self.assertIn('if __name__ == "__main__":', public_text)
        pending_index = public_text.index("write_pending_atomic(")
        store_open_index = public_text.index("store = runtime.open_store(store_root)")
        self.assertLess(pending_index, store_open_index)

        transaction_python_files = []
        for path in DC02_DIR.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "store = runtime.open_store(store_root)" in text:
                transaction_python_files.append(path.name)
        self.assertEqual(transaction_python_files, [PUBLIC_PATH.name])


if __name__ == "__main__":
    unittest.main()
