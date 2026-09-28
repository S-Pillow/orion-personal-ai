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
        self.assertIn("?fixture=review", PROBE)
        self.assertIn("?fixture=summon", PROBE)
        self.assertIn("?fixture=approval", PROBE)
        self.assertIn("?fixture=summon-approval", PROBE)
        self.assertIn('app_text += "\\n" + FIXTURE_SNIPPET + "\\n"', PROBE)

    def test_fixture_can_auto_load_seeded_review_session(self):
        self.assertIn('__fixtureMode === "review"', PROBE)
        self.assertIn("async function __fixtureSelectSession()", PROBE)
        self.assertIn('state.sessionId = "session_1";', PROBE)
        self.assertIn("await loadMessages();", PROBE)

    def test_fixture_avoids_duplicate_session_bootstrap_for_summon_approval(self):
        self.assertIn('if (__fixtureMode === "summon")', PROBE)
        self.assertIn('if (__fixtureMode === "review")', PROBE)
        self.assertNotIn(
            '__fixtureMode === "review"\n  || __fixtureMode === "summon"\n  || __fixtureMode === "summon-approval"',
            PROBE,
        )

    def test_fixture_can_auto_drive_real_submit_path_for_approval_overlap(self):
        self.assertIn('__fixtureMode === "approval" || __fixtureMode === "summon-approval"', PROBE)
        self.assertIn('state.sessionId = "session_1";', PROBE)
        self.assertIn('"Prepare the next Orion interface proposal from the reviewed notes. "', PROBE)
        self.assertIn('"Show me the exact change before anything is written."', PROBE)
        self.assertIn('"Preparing proposal"', PROBE)
        self.assertIn("ui.composer.requestSubmit();", PROBE)

    def test_review_fixture_resets_transcript_to_reference_start(self):
        self.assertIn("ui.transcript.scrollTop = 0;", PROBE)

    def test_fixture_clock_and_motion_are_deterministic(self):
        self.assertIn('dataset.fixtureClock = "22:24"', PROBE)
        self.assertIn("corePresence.destroy();", PROBE)
        self.assertIn('dataset.motion = "reduced"', PROBE)
        self.assertIn("?fixture=offline", PROBE)
        self.assertIn("?fixture=motion", PROBE)
        self.assertIn("?fixture=core-review", PROBE)

    def test_motion_fixture_keeps_live_presence_controller(self):
        self.assertIn('if (__fixtureMode !== "motion")', PROBE)
        self.assertIn('__fixtureMode === "motion"', PROBE)
        self.assertIn('setCore("THINKING"', PROBE)

    def test_core_review_fixture_exposes_actual_renderer_controls(self):
        self.assertIn('__fixtureMode === "core-review"', PROBE)
        self.assertIn("window.__orionCoreFixture", PROBE)
        self.assertIn('corePresence.setGaze("forward")', PROBE)
        self.assertIn("corePresence.blink()", PROBE)
        self.assertIn('setCore("WAITING"', PROBE)
        self.assertIn('setCore("OFFLINE"', PROBE)
        self.assertIn('id = "coreReviewControls"', PROBE)

    def test_fixture_content_is_explicitly_presentation_only(self):
        self.assertIn("presentation-only fixture content", PROBE)
        self.assertIn("<b>literal markup</b>", PROBE)


if __name__ == "__main__":
    unittest.main()
