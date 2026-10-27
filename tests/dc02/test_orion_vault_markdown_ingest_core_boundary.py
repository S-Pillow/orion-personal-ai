from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest_core.py"
PUBLIC_PATH = ROOT / "scripts" / "dc02" / "orion_vault_markdown_ingest.py"


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

    def test_public_coordinator_remains_the_only_python_cli(self):
        core_text = CORE_PATH.read_text(encoding="utf-8")
        public_text = PUBLIC_PATH.read_text(encoding="utf-8")
        self.assertIn("internal_core_entrypoint_disabled", core_text)
        self.assertNotIn("runtime.open_store(store_root)", core_text)
        self.assertIn("runtime.open_store(store_root)", public_text)
        self.assertIn('if __name__ == "__main__":', public_text)


if __name__ == "__main__":
    unittest.main()
