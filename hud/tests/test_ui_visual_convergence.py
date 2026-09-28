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
        main_start = INDEX.index("<main ")
        topbar = INDEX[topbar_start:main_start]
        self.assertIn("workspace-switcher", topbar)
        self.assertIn(">CONVERSATION</button>", topbar)
        self.assertIn(">SYSTEM</button>", topbar)
        self.assertIn(">MEMORY</button>", topbar)

    def test_core_is_scene_not_css_ring_field(self):
        self.assertIn("scene-environment", INDEX)
        self.assertIn("hero-thoughts-left", INDEX)
        self.assertIn("hero-thoughts-right", INDEX)
        self.assertIn("LISTENING. THINKING. WITH YOU.", INDEX)
        self.assertNotIn("core-field", INDEX)

    def test_conversation_is_foreground_surface(self):
        self.assertIn(".conversation-workspace", TARGET)
        self.assertIn("backdrop-filter: blur(12px);", TARGET)
        self.assertIn("--center-width: min(920px", TARGET)
        self.assertIn('class="workspace-pane foreground-workspace"', INDEX)
        self.assertIn('class="composer-actions"', INDEX)
        self.assertIn("grid-template-columns: 44px minmax(0,1fr) auto;", TARGET)

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
        self.assertIn('data-core-state="READY"', INDEX)
        for state in (
            "THINKING",
            "ACTING",
            "WAITING",
            "DEGRADED",
            "ERROR",
            "OFFLINE",
        ):
            with self.subTest(state=state):
                self.assertIn(f'data-core-state="{state}"', TARGET)
        self.assertIn("@media (prefers-reduced-motion: reduce)", TARGET)

    def test_conversation_and_rails_have_product_hierarchy(self):
        for token in (
            "message-avatar",
            "message-time",
            "message-header",
            "companion-context",
            "approvalCommand",
        ):
            self.assertIn(token, INDEX + APP)
        self.assertIn("--center-width: min(920px", TARGET)
        self.assertIn("--left-region: clamp(238px, 15.1vw, 260px);", TARGET)
        self.assertIn("--right-region: clamp(360px, 24.2vw, 410px);", TARGET)

    def test_structural_layout_has_one_authoritative_definition(self):
        self.assertNotIn(
            "grid-template-columns: minmax(230px, 285px) minmax(480px, 1fr) minmax(250px, 320px);",
            STYLES,
        )
        self.assertNotIn("grid-template-columns: 1fr 86px 86px;", STYLES + TARGET)
        self.assertIn("--left-region: clamp(238px, 15.1vw, 260px);", TARGET)
        self.assertIn("--right-region: clamp(360px, 24.2vw, 410px);", TARGET)
        self.assertIn(".center-stage {", TARGET)
        self.assertIn("position: absolute;", TARGET)
        self.assertNotIn("grid-template-columns:\n    var(--rail-left-width)", TARGET)

    def test_composer_run_controls_are_state_explicit(self):
        self.assertIn('class="composer-actions"', INDEX)
        self.assertIn('id="stopButton"', INDEX)
        self.assertIn("hidden", INDEX[INDEX.index('id="stopButton"'):INDEX.index('id="stopButton"') + 220])
        self.assertIn('ui.composer.dataset.runState = running ? "running" : "idle";', APP)
        self.assertIn("ui.stopButton.hidden = !running;", APP)
        self.assertIn("ui.sendButton.hidden = running;", APP)
        self.assertIn(":focus-visible", TARGET)

    def test_cinematic_core_is_addressable_and_environment_has_no_baked_face(self):
        self.assertIn('id="coreState"', INDEX)
        core = INDEX[INDEX.index('class="core-visual live-core"'):INDEX.index('class="core-presence-label"')]
        self.assertNotIn('id="coreState"', core)
        self.assertIn('class="core-eye core-eye-left"', core)
        self.assertIn('class="core-eye core-eye-right"', core)
        self.assertIn('class="core-halo core-halo-outer"', core)
        self.assertNotIn("core-eye", HERO)
        self.assertIn(".core-stage.is-blinking .core-eye-group", TARGET)
        self.assertIn('.core-stage[data-core-state="OFFLINE"] .core-visual', TARGET)

    def test_speaker_marks_replace_placeholder_initials(self):
        self.assertIn('avatar.textContent = "";', APP)
        self.assertIn('avatar.dataset.speaker = isUser ? "user" : "orion";', APP)
        self.assertIn('.message-avatar[data-speaker="user"]::before', TARGET)
        self.assertIn('.message-avatar[data-speaker="orion"]::before', TARGET)
        self.assertIn("grid-template-columns: 46px minmax(0,1fr);", TARGET)

    def test_core_is_contained_and_foreground_matches_reference_geometry(self):
        self.assertIn("--hero-height: clamp(340px, 42vh, 368px);", TARGET)
        self.assertIn("--center-width: min(920px", TARGET)
        self.assertIn("width: 300px;", TARGET)
        self.assertIn("grid-template-rows: minmax(0,1fr) 78px;", TARGET)

    def test_vertical_composition_fills_desktop_stage(self):
        self.assertIn(
            "grid-template-rows: var(--hero-height) minmax(0, 1fr);",
            TARGET,
        )
        self.assertIn("height: 100%;", TARGET)
        self.assertIn("overflow-y: auto;", TARGET)
        self.assertIn('viewBox="0 0 1600 900"', HERO)

    def test_left_atmosphere_is_integrated_background_layer(self):
        self.assertIn("height: 35%;", TARGET)
        self.assertIn("mask-image: linear-gradient(180deg", TARGET)
        self.assertIn("align-items: flex-end;", TARGET)
        self.assertNotIn("padding: 22px 20px 250px;", TARGET)

    def test_center_axis_drives_hero_identity_and_workspace(self):
        self.assertIn("--center-shift:", TARGET)
        self.assertIn("left: calc(50% + var(--center-shift));", TARGET)
        self.assertIn("left: calc(50% + var(--center-shift));", TARGET)

    def test_approval_focus_and_summon_are_visually_prioritized(self):
        self.assertIn('document.body.classList.add("approval-active");', APP)
        self.assertIn('document.body.classList.remove("approval-active");', APP)
        self.assertIn("body.approval-active .approval-panel", TARGET)
        self.assertIn("width: min(760px, calc(var(--center-width) - 60px));", TARGET)
        self.assertIn("max-height: 360px;", TARGET)

    def test_header_detailed_provenance_is_demoted_not_deleted(self):
        for element_id in ("originStatus", "sourceStatus", "memoryUseStatus", "authorityStatus"):
            self.assertIn(f'id="{element_id}"', INDEX)
        self.assertIn(
            ".provenance-status .provenance-chip:not(.authority-chip)",
            TARGET,
        )

    def test_environment_first_shell_replaces_three_column_dashboard(self):
        self.assertIn('data-presentation-shell="environment-first"', INDEX)
        self.assertIn("environment-region", INDEX)
        self.assertIn("center-experience", INDEX)
        self.assertIn("focus-surface", INDEX)
        self.assertIn(".hud-grid {\n  position: relative;", TARGET)
        self.assertIn(".rail {\n  position: absolute;", TARGET)
        self.assertNotIn(
            "grid-template-columns: 260px minmax(760px, 1fr) 330px;",
            STYLES + TARGET,
        )

    def test_visual_pass_does_not_add_runtime_transport(self):
        for token in (
            "/api/orion/summon",
            "WebSocket(",
            "EventSource(",
        ):
            self.assertNotIn(token, APP)


if __name__ == "__main__":
    unittest.main(verbosity=2)
