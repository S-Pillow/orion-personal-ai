from __future__ import annotations

import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]

BRIDGE = (HUD_ROOT / "orion_hud_bridge.py").read_text(encoding="utf-8")
INDEX = (HUD_ROOT / "static" / "index.html").read_text(encoding="utf-8")
APP = (HUD_ROOT / "static" / "app.js").read_text(encoding="utf-8")
STYLES = (HUD_ROOT / "static" / "styles.css").read_text(encoding="utf-8")
WORKSPACE = (HUD_ROOT / "static" / "workspace-state.js").read_text(encoding="utf-8")
SUMMON = (HUD_ROOT / "static" / "summon-state.js").read_text(encoding="utf-8")


class Phase3SummonShellContractTests(unittest.TestCase):
    def test_summon_module_is_static_allowlisted_and_installed(self):
        self.assertIn(
            '"/summon-state.js": ("summon-state.js", "text/javascript; charset=utf-8")',
            BRIDGE,
        )
        self.assertIn(
            'import { installSummonController } from "./summon-state.js";',
            APP,
        )
        self.assertIn("const summonController = installSummonController({", APP)

    def test_summon_is_presentation_overlay_not_fourth_workspace(self):
        self.assertEqual(INDEX.count("data-workspace-target="), 3)
        self.assertEqual(INDEX.count("data-workspace-pane="), 3)
        self.assertIn('id="summonPanel"', INDEX)
        self.assertNotIn('data-workspace-target="summon"', INDEX)
        self.assertNotIn('data-workspace-pane="summon"', INDEX)
        self.assertIn('data-workspace-focus="summon"', STYLES)

    def test_shell_has_accessible_bounded_visible_controls(self):
        for element_id in (
            "summonPanel",
            "summonTitle",
            "summonKind",
            "summonSource",
            "summonBody",
            "summonLink",
            "summonDismiss",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', INDEX)

        self.assertIn('role="region"', INDEX)
        self.assertIn('aria-labelledby="summonTitle"', INDEX)
        self.assertIn('aria-label="Dismiss summoned content"', INDEX)
        self.assertIn('rel="noopener noreferrer"', INDEX)

    def test_summon_renderer_has_no_network_storage_or_html_authority(self):
        forbidden = (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "EventSource",
            "localStorage",
            "sessionStorage",
            "navigator.",
            "innerHTML",
            "insertAdjacentHTML",
            "eval(",
            "Function(",
            "document.cookie",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, SUMMON)

        self.assertIn("textContent", SUMMON)
        self.assertIn('"text"', SUMMON)
        self.assertIn('"evidence"', SUMMON)
        self.assertIn('"link"', SUMMON)
        self.assertNotIn('"iframe"', SUMMON)

    def test_link_protocol_is_explicitly_bounded(self):
        self.assertIn('url.protocol !== "http:"', SUMMON)
        self.assertIn('url.protocol !== "https:"', SUMMON)
        self.assertIn('"summon_link_scheme_rejected"', SUMMON)

    def test_workspace_focus_prioritizes_approval_over_summon(self):
        self.assertIn('focus === "summon"', WORKSPACE)
        self.assertIn("let approvalFocus = false;", WORKSPACE)
        self.assertIn("let summonFocus = false;", WORKSPACE)
        self.assertIn('approvalFocus\n        ? "approval"', WORKSPACE)
        self.assertIn('summonFocus\n          ? "summon"', WORKSPACE)
        self.assertIn("setSummonFocus,", WORKSPACE)

    def test_summon_focus_changes_presentation_not_operational_core_state(self):
        self.assertIn('coreStage.dataset.presentationFocus =', SUMMON)
        self.assertIn(
            '.core-stage[data-presentation-focus="summon"]',
            STYLES,
        )
        self.assertNotIn("data-core-state", SUMMON)
        self.assertNotIn("setCore(", SUMMON)

    def test_no_agent_transport_is_added_in_p3_05b(self):
        self.assertIn(
            "No agent/browser transport is\n// granted here",
            APP,
        )
        self.assertNotIn("/api/orion/summon", BRIDGE)
        self.assertNotIn("approval.request", SUMMON)


if __name__ == "__main__":
    unittest.main(verbosity=2)
