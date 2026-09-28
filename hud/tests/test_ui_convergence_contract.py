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
        self.assertIn("--hero-height: clamp(410px, 50vh, 560px);", self.target)
        self.assertIn(".hero-scene {", self.target)
        self.assertIn(".core-mask {", self.target)
        self.assertIn("clip-path: polygon(", self.target)

    def test_secondary_diagnostics_are_environment_regions(self):
        self.assertIn(".context-sidebar {", self.target)
        self.assertIn(".activity-sidebar {", self.target)
        self.assertIn("position: absolute;", self.target)
        self.assertIn("linear-gradient(90deg", self.target)
        self.assertNotIn("grid-template-columns: minmax(230px, 285px)", self.css + self.target)

    def test_approval_visually_outranks_lower_priority_context(self):
        self.assertIn("body.approval-active .approval-panel", self.target)
        self.assertIn("body.approval-active .memory-lens", self.target)
        self.assertIn("body.approval-active .action-evidence-panel", self.target)


if __name__ == "__main__":
    unittest.main()
