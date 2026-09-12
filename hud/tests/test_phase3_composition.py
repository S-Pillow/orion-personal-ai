from __future__ import annotations

import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]

INDEX = (HUD_ROOT / "static" / "index.html").read_text(
    encoding="utf-8"
)

STYLES = (HUD_ROOT / "static" / "styles.css").read_text(
    encoding="utf-8"
)


class Phase3CompositionContractTests(unittest.TestCase):
    def test_exact_workspace_set_remains(self):
        self.assertEqual(INDEX.count("data-workspace-target="), 3)
        self.assertEqual(INDEX.count("data-workspace-pane="), 3)

        for value in ("conversation", "system", "memory"):
            self.assertIn(
                'data-workspace-target="{}"'.format(value),
                INDEX,
            )
            self.assertIn(
                'data-workspace-pane="{}"'.format(value),
                INDEX,
            )

    def test_conversation_remains_default(self):
        self.assertIn('data-workspace="conversation"', INDEX)

    def test_functional_controls_remain(self):
        for element_id in (
            "sessionSelect",
            "newSession",
            "iaiBrainLink",
            "coreStage",
            "transcript",
            "composer",
            "messageInput",
            "sendButton",
            "stopButton",
            "activity",
            "approvalPanel",
            "originStatus",
            "sourceStatus",
            "memoryUseStatus",
            "authorityStatus",
        ):
            self.assertIn('id="{}"'.format(element_id), INDEX)

    def test_top_edge_separates_link_and_provenance(self):
        self.assertIn(
            'class="top-status-group infrastructure-status"',
            INDEX,
        )
        self.assertIn(
            'class="top-status-group provenance-status"',
            INDEX,
        )

    def test_footer_names_transport_not_response_origin(self):
        self.assertIn("LOOPBACK TRANSPORT", INDEX)
        self.assertNotIn("LOCAL LOOPBACK", INDEX)
        self.assertIn("ORIGIN &#183; UNOBSERVED", INDEX)

    def test_center_and_core_are_visually_prioritized(self):
        self.assertIn("P3-05A composition convergence", STYLES)
        self.assertIn("minmax(560px, 1fr)", STYLES)
        self.assertIn("minmax(230px, 38vh)", STYLES)
        self.assertIn("max-width: min(82%, 760px);", STYLES)
        self.assertIn("width: 160px;", STYLES)

    def test_future_phase_controls_are_not_advertised(self):
        for token in (
            'data-workspace-target="vault"',
            'data-workspace-target="tasks"',
            'data-workspace-target="research"',
            'data-workspace-target="create"',
        ):
            self.assertNotIn(token, INDEX)

    def test_secondary_panels_do_not_dim_interactive_content(self):
        self.assertNotIn("opacity: 0.72;", STYLES)
        self.assertNotIn(".peripheral-panel:hover", STYLES)
        self.assertNotIn(".secondary-panel:hover", STYLES)

    def test_reduced_motion_contract_remains(self):
        self.assertIn(
            "@media (prefers-reduced-motion: reduce)",
            STYLES,
        )
        self.assertIn(
            "animation-duration: 0.001ms !important;",
            STYLES,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
