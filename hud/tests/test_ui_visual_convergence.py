from __future__ import annotations

import unittest
from pathlib import Path

HUD_ROOT = Path(__file__).resolve().parents[1]
INDEX = (HUD_ROOT / "static" / "index.html").read_text(encoding="utf-8")
STYLES = (HUD_ROOT / "static" / "styles.css").read_text(encoding="utf-8")
TARGET = (HUD_ROOT / "static" / "target-layout.css").read_text(encoding="utf-8")
HERO = (HUD_ROOT / "static" / "orion-hero.svg").read_text(encoding="utf-8")
APP = (HUD_ROOT / "static" / "app.js").read_text(encoding="utf-8")


class FinalVisualConvergenceContractTests(unittest.TestCase):
    def test_owner_target_assets_are_loaded(self):
        self.assertIn('href="/target-layout.css"', INDEX)
        self.assertIn('src="/orion-hero.svg"', INDEX)
        self.assertIn("Orion owner-target layout", TARGET)
        self.assertIn("<svg", HERO)

    def test_layout_matches_target_zones(self):
        for token in (
            "context-sidebar",
            "hero-scene",
            "conversation-workspace",
            "activity-sidebar",
            "memory-lens",
        ):
            self.assertIn(token, INDEX)

    def test_top_navigation_is_integrated_into_chrome(self):
        topbar_start = INDEX.index('<header class="topbar">')
        main_start = INDEX.index('<main class="hud-grid">')
        topbar = INDEX[topbar_start:main_start]
        self.assertIn("workspace-switcher", topbar)
        self.assertIn(">CONVERSATION</button>", topbar)
        self.assertIn(">SYSTEM</button>", topbar)
        self.assertIn(">MEMORY</button>", topbar)

    def test_core_is_scene_not_css_ring_field(self):
        self.assertIn("hero-scene-art", INDEX)
        self.assertIn("hero-thoughts-left", INDEX)
        self.assertIn("hero-thoughts-right", INDEX)
        self.assertIn("LISTENING. THINKING. WITH YOU.", INDEX)
        self.assertNotIn("core-field", INDEX)

    def test_conversation_is_foreground_surface(self):
        self.assertIn(".conversation-workspace", TARGET)
        self.assertIn("backdrop-filter: blur(18px);", TARGET)
        self.assertIn("margin: -38px 32px 14px;", TARGET)
        self.assertIn(".composer", TARGET)

    def test_context_and_activity_rails_are_editorial(self):
        self.assertIn(".context-sidebar", TARGET)
        self.assertIn(".activity-sidebar", TARGET)
        self.assertIn(".context-section", TARGET)
        self.assertIn(".operational-section", TARGET)
        self.assertIn(".operational-card", TARGET)

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

    def test_live_core_state_and_reduced_motion_remain_supported(self):
        for state in (
            "READY",
            "THINKING",
            "FINALIZING",
            "ACTING",
            "WAITING",
            "DEGRADED",
            "ERROR",
            "OFFLINE",
        ):
            with self.subTest(state=state):
                self.assertIn(f'data-core-state="{state}"', STYLES)
        self.assertIn("@media (prefers-reduced-motion: reduce)", STYLES)

    def test_visual_pass_does_not_add_runtime_transport(self):
        for token in (
            "/api/orion/summon",
            "WebSocket(",
            "EventSource(",
        ):
            self.assertNotIn(token, APP)


if __name__ == "__main__":
    unittest.main(verbosity=2)
