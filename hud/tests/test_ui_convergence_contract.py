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

    def test_shell_identity_is_companion_first(self):
        self.assertIn("Orion // Personal AI Companion", self.html)
        self.assertIn("PRIVATE AI COMPANION", self.html)
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
            self.css,
        )

    def test_core_is_visually_promoted(self):
        self.assertIn("minmax(270px, 42vh)", self.css)
        self.assertIn("width: 194px;", self.css)
        self.assertIn("width: 360px;", self.css)

    def test_secondary_diagnostics_are_demoted(self):
        self.assertIn(".peripheral-panel,", self.css)
        self.assertIn(".secondary-panel {", self.css)
        self.assertIn("opacity: 0.66;", self.css)

    def test_narrow_approval_precedes_contextual_evidence(self):
        self.assertIn(".right-rail .approval-panel {\n    order: 0;", self.css)
        self.assertIn(".right-rail .action-evidence-panel {\n    order: 1;", self.css)


if __name__ == "__main__":
    unittest.main()
