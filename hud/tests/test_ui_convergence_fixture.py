from __future__ import annotations

import unittest
from pathlib import Path

HUD_ROOT = Path(__file__).resolve().parents[1]
PROBE = (HUD_ROOT / "tests" / "probe_ui_convergence.py").read_text(
    encoding="utf-8",
)


class UIConvergenceFixtureContractTests(unittest.TestCase):
    def test_fixture_uses_temporary_static_copy(self):
        self.assertIn("TemporaryDirectory", PROBE)
        self.assertIn("shutil.copytree(HUD_ROOT / \"static\"", PROBE)
        self.assertIn("self._tmp.cleanup()", PROBE)

    def test_fixture_does_not_add_production_transport(self):
        self.assertNotIn("/api/orion/summon", PROBE)
        self.assertIn("?fixture=summon", PROBE)
        self.assertIn("?fixture=summon-approval", PROBE)
        self.assertIn("void summonController;", PROBE)

    def test_fixture_can_auto_drive_real_submit_path_for_approval_overlap(self):
        self.assertIn('__fixtureMode === "summon-approval"', PROBE)
        self.assertIn('state.sessionId = "session_1";', PROBE)
        self.assertIn('ui.messageInput.value = "probe";', PROBE)
        self.assertIn("ui.composer.requestSubmit();", PROBE)

    def test_fixture_content_is_explicitly_presentation_only(self):
        self.assertIn("presentation-only fixture content", PROBE)
        self.assertIn("<b>literal markup</b>", PROBE)


if __name__ == "__main__":
    unittest.main()
