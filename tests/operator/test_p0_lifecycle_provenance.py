from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "scripts" / "operator" / "packages" / "2.7.4-candidate2"
MODULE = PKG / "hermes_provenance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("candidate2_hermes_provenance", MODULE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_git(repo: Path, *args: str):
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "Orion Test")
    env.setdefault("GIT_AUTHOR_EMAIL", "orion-test@example.invalid")
    env.setdefault("GIT_COMMITTER_NAME", "Orion Test")
    env.setdefault("GIT_COMMITTER_EMAIL", "orion-test@example.invalid")
    cp = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if cp.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {cp.stderr}")
    return cp.stdout.strip()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProvenanceFixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="orion-p0-prov-")
        self.root = Path(self.tmp.name)
        run_git(self.root, "init")
        (self.root / "tracked.txt").write_text("base\n", encoding="utf-8")
        run_git(self.root, "add", "tracked.txt")
        run_git(self.root, "commit", "-m", "base")
        self.pin = run_git(self.root, "rev-parse", "HEAD")

        (self.root / "tracked.txt").write_text("modified\n", encoding="utf-8")
        (self.root / "new.txt").write_text("new\n", encoding="utf-8")

        self.sidecar_rel = "sidecar.json"
        self.sidecar = self.root / self.sidecar_rel
        self.sidecar.write_text(
            json.dumps(
                {
                    "patch_id": "fixture",
                    "accepted_hermes_commit": self.pin,
                    "target": str(self.root / "tracked.txt"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        self.overlay = {
            "tracked.txt": {"status": " M", "sha256": sha(self.root / "tracked.txt")},
            "new.txt": {"status": "??", "sha256": sha(self.root / "new.txt")},
            self.sidecar_rel: {"status": "??", "sha256": sha(self.sidecar)},
        }
        self.sidecars = {
            self.sidecar_rel: {
                "fields": {
                    "patch_id": "fixture",
                    "accepted_hermes_commit": self.pin,
                },
                "paths": {"target": "tracked.txt"},
            }
        }

    def close(self):
        self.tmp.cleanup()


class TestHermesProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def setUp(self):
        self.fx = ProvenanceFixture()

    def tearDown(self):
        self.fx.close()

    def verify(self):
        return self.mod.verify_hermes_provenance(
            self.fx.root,
            self.fx.pin,
            overlay=self.fx.overlay,
            sidecars=self.fx.sidecars,
        )

    def test_exact_overlay_passes(self):
        self.assertEqual(self.verify(), (True, "OK"))

    def test_wrong_head_fails(self):
        self.assertEqual(
            self.mod.verify_hermes_provenance(
                self.fx.root,
                "0" * 40,
                overlay=self.fx.overlay,
                sidecars=self.fx.sidecars,
            ),
            (False, "HERMES_PIN_MISMATCH"),
        )

    def test_extra_untracked_file_fails(self):
        (self.fx.root / "extra.txt").write_text("x\n", encoding="utf-8")
        self.assertEqual(self.verify(), (False, "HERMES_OVERLAY_STATUS_MISMATCH"))

    def test_missing_overlay_file_fails(self):
        (self.fx.root / "new.txt").unlink()
        self.assertEqual(self.verify(), (False, "HERMES_OVERLAY_STATUS_MISMATCH"))

    def test_modified_hash_fails(self):
        (self.fx.root / "new.txt").write_text("changed\n", encoding="utf-8")
        self.assertEqual(self.verify(), (False, "HERMES_OVERLAY_HASH_MISMATCH"))

    def test_staging_state_change_fails(self):
        run_git(self.fx.root, "add", "tracked.txt")
        self.assertEqual(self.verify(), (False, "HERMES_OVERLAY_STATUS_MISMATCH"))

    def test_sidecar_semantic_change_fails(self):
        obj = json.loads(self.fx.sidecar.read_text(encoding="utf-8"))
        obj["patch_id"] = "wrong"
        self.fx.sidecar.write_text(json.dumps(obj) + "\n", encoding="utf-8")
        self.fx.overlay[self.fx.sidecar_rel]["sha256"] = sha(self.fx.sidecar)
        self.assertEqual(self.verify(), (False, "HERMES_OVERLAY_SIDECAR_MISMATCH"))

    def test_clean_upstream_only_fails(self):
        run_git(self.fx.root, "reset", "--hard", "HEAD")
        for p in (self.fx.root / "new.txt", self.fx.sidecar):
            if p.exists():
                p.unlink()
        self.assertEqual(self.verify(), (False, "HERMES_OVERLAY_STATUS_MISMATCH"))


class TestCandidate2Integration(unittest.TestCase):
    def test_version(self):
        text = (PKG / "protocol.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "2.7.4-candidate2"', text)
        self.assertNotIn('VERSION = "2.7.4-candidate1"', text)

    def test_orion_uses_exact_provenance_gate(self):
        text = (PKG / "orion.py").read_text(encoding="utf-8")
        self.assertNotIn("HERMES_CHECKOUT_NOT_CLEAN", text)
        self.assertIn("verify_hermes_provenance", text)
        self.assertIn("provenance_ok", text)
        self.assertIn("provenance_code", text)

    def test_start_stop_wrappers_route_through_invoke(self):
        for name, action in (
            ("Start-Orion.ps1", "start"),
            ("Stop-Orion.ps1", "stop"),
        ):
            text = (PKG / name).read_text(encoding="utf-8")
            self.assertIn("param([string]$ConfigPath)", text)
            self.assertIn("IsNullOrWhiteSpace($ConfigPath)", text)
            self.assertIn("$PSScriptRoot", text)
            self.assertIn("Invoke-Orion.ps1", text)
            self.assertIn(f"-Action {action}", text)
            self.assertNotIn(
                "param([string]$ConfigPath = (Join-Path $PSScriptRoot",
                text,
            )

    def test_stop_wrapper_does_not_create_parallel_shutdown_path(self):
        text = (PKG / "Stop-Orion.ps1").read_text(encoding="utf-8")
        self.assertNotIn("gateway stop", text)
        self.assertNotIn("Stop-Process", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
