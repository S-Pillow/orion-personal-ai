from __future__ import annotations

import unittest
from pathlib import Path

HUD_ROOT = Path(__file__).resolve().parents[1]
STATIC = HUD_ROOT / "static"


class UIConvergenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (STATIC / "index.html").read_text(encoding="utf-8")
        cls.css = (STATIC / "styles.css").read_text(encoding="utf-8")
        cls.target = (STATIC / "target-layout.css").read_text(encoding="utf-8")

    def test_shell_identity_is_companion_first(self):
        self.assertIn("Orion // Personal AI Companion", self.html)
        self.assertIn("YOUR THINKING PARTNER", self.html)
        self.assertNotIn("PRIVATE COMPANION // OBSERVATORY", self.html)

    def test_existing_authority_and_action_surfaces_are_preserved(self):
        for element_id in (
            'id="workspaceShell"',
            'id="coreStage"',
            'id="transcript"',
            'id="approvalPanel"',
            'id="approvalActions"',
            'id="actionEvidencePanel"',
            'id="actionDiff"',
            'id="sessionSelect"',
        ):
            self.assertIn(element_id, self.html)

    def test_visual_layer_explicitly_marks_presentation_only_scope(self):
        self.assertIn(
            "UI convergence — companion-first presentation layer",
            self.css,
        )
        self.assertIn(
            "Runtime/session/approval/action truth remains unchanged",
            self.target,
        )

    def test_core_is_visually_promoted(self):
        self.assertIn("--hero-height: clamp(340px, 42vh, 368px);", self.target)
        self.assertIn(".hero-scene {", self.target)
        self.assertIn('class="core-visual live-core"', self.html)
        self.assertIn('class="core-eye-aperture"', self.html)
        self.assertIn('class="core-eye-lid core-eye-lid-top"', self.html)
        self.assertIn(".core-stage.blink-closing .core-eye-lid-top", self.target)

    def test_visible_core_eyes_are_addressable_inline_svg(self):
        hero = (STATIC / "orion-hero.svg").read_text(encoding="utf-8")
        self.assertNotIn("core-eye", hero)
        self.assertIn('class="core-eye-aperture"', self.html)
        self.assertIn('class="core-eye-content core-eye-content-left"', self.html)
        self.assertIn('class="core-eye-content core-eye-content-right"', self.html)
        self.assertIn('[data-gaze="left"]', self.target)
        self.assertIn("blink-closing", self.target)

    def test_secondary_diagnostics_are_environment_regions(self):
        self.assertIn(".context-sidebar {", self.target)
        self.assertIn(".activity-sidebar {", self.target)
        self.assertIn("position: absolute;", self.target)
        self.assertIn("linear-gradient(90deg", self.target)
        self.assertNotIn("grid-template-columns: minmax(230px, 285px)", self.css + self.target)

    def test_conversation_consumes_remaining_stage_height(self):
        self.assertIn(
            "grid-template-rows: var(--hero-height) minmax(0, 1fr);",
            self.target,
        )
        self.assertIn("grid-row: 2;", self.target)
        self.assertIn(
            "grid-template-rows: minmax(0,1fr) 78px;",
            self.target,
        )
        self.assertIn(".composer {", self.target)

    def test_approval_visually_outranks_lower_priority_context(self):
        self.assertIn("body.approval-active .approval-panel", self.target)
        self.assertNotIn(
            "body.approval-active .activity-sidebar {\n  width:",
            self.target,
        )
        self.assertIn("body.approval-active .action-evidence-panel", self.target)


if __name__ == "__main__":
    unittest.main()
