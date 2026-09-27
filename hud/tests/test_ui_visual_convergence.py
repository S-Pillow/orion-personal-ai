from __future__ import annotations

import unittest
from pathlib import Path

HUD_ROOT = Path(__file__).resolve().parents[1]
INDEX = (HUD_ROOT / "static" / "index.html").read_text(encoding="utf-8")
STYLES = (HUD_ROOT / "static" / "styles.css").read_text(encoding="utf-8")
APP = (HUD_ROOT / "static" / "app.js").read_text(encoding="utf-8")


class FinalVisualConvergenceContractTests(unittest.TestCase):
    def test_companion_presence_elements_exist(self):
        for token in (
            "core-presence-label",
            "core-field",
            "orbit-outer",
            "orbit-mid",
            "orbit-inner",
            "star-a",
            "star-b",
            "star-c",
        ):
            self.assertIn(token, INDEX)

    def test_visual_pass_is_explicitly_presentation_only(self):
        self.assertIn(
            "Final visual convergence pass — companion presence and calm workspace",
            STYLES,
        )
        self.assertIn("grid-template-columns:", STYLES)
        self.assertIn("minmax(720px, 1fr)", STYLES)

    def test_conversation_is_treated_as_primary_surface(self):
        self.assertIn(".conversation-workspace {", STYLES)
        self.assertIn(".message-body {", STYLES)
        self.assertIn("font-size: 14px;", STYLES)
        self.assertIn(".composer {", STYLES)

    def test_diagnostics_are_visually_recessed_without_becoming_hidden(self):
        self.assertIn(".panel {", STYLES)
        self.assertIn("background: rgba(7, 16, 19, 0.22);", STYLES)
        self.assertNotIn(".left-rail { display: none", STYLES)
        self.assertNotIn(".right-rail { display: none", STYLES)

    def test_existing_consequential_surfaces_remain_present(self):
        for element_id in (
            "approvalPanel",
            "approvalActions",
            "actionEvidencePanel",
            "actionDiff",
            "summonPanel",
            "summonDismiss",
        ):
            self.assertIn(f'id="{element_id}"', INDEX)

    def test_core_presence_motion_tracks_existing_state_only(self):
        for state in ("READY", "THINKING", "FINALIZING", "ACTING", "WAITING", "DEGRADED", "ERROR", "OFFLINE"):
            with self.subTest(state=state):
                self.assertIn(f'data-core-state="{state}"', STYLES)
        self.assertIn("@media (prefers-reduced-motion: reduce)", STYLES)
        self.assertIn("animation: none !important;", STYLES)

    def test_review_refinement_reduces_console_density(self):
        self.assertIn("Visual convergence refinement — companion, not console", STYLES)
        self.assertIn("font-size: 15px;", STYLES)
        self.assertIn("height: min(44vh, 500px);", STYLES)
        self.assertIn("background: transparent;", STYLES)
        self.assertIn("width: 214px;", STYLES)

    def test_visual_pass_does_not_add_runtime_transport(self):
        for token in (
            "/api/orion/summon",
            "WebSocket(",
            "EventSource(",
        ):
            self.assertNotIn(token, APP)


if __name__ == "__main__":
    unittest.main(verbosity=2)
