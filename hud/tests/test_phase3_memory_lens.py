from __future__ import annotations

import re
import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]

INDEX = (HUD_ROOT / "static" / "index.html").read_text(
    encoding="utf-8"
)

APP = (HUD_ROOT / "static" / "app.js").read_text(
    encoding="utf-8"
)

WORKSPACE = (
    HUD_ROOT / "static" / "workspace-state.js"
).read_text(
    encoding="utf-8"
)

STYLES = (HUD_ROOT / "static" / "styles.css").read_text(
    encoding="utf-8"
)

BRIDGE = (HUD_ROOT / "orion_hud_bridge.py").read_text(
    encoding="utf-8"
)


class Phase3MemoryLensContractTests(unittest.TestCase):
    def test_memory_workspace_is_explicit_and_conversation_stays_default(self):
        self.assertIn('data-workspace="conversation"', INDEX)
        self.assertIn('data-workspace-target="memory"', INDEX)
        self.assertIn('data-workspace-pane="memory"', INDEX)
        self.assertIn('"memory"', WORKSPACE)
        self.assertEqual(INDEX.count('data-workspace-target="memory"'), 1)
        self.assertEqual(INDEX.count('data-workspace-pane="memory"'), 1)

    def test_memory_lens_states_the_accepted_authority_and_baseline(self):
        for token in (
            "MEMORY LENS",
            "iai Memory Authority",
            "iai-pme 3.0.8",
            "encrypted local store",
            "presentation + handoff",
            "IAI AUTHORITATIVE",
        ):
            with self.subTest(token=token):
                self.assertIn(token, INDEX)

    def test_native_brain_handoff_is_a_fixed_loopback_link(self):
        exact_href = 'href="http://127.0.0.1:4477/"'
        self.assertGreaterEqual(INDEX.count(exact_href), 2)
        self.assertIn('target="_blank"', INDEX)
        self.assertIn('rel="noopener noreferrer"', INDEX)
        self.assertIn("OPEN NATIVE IAI BRAIN", INDEX)
        self.assertIn("127.0.0.1 only", INDEX)
        self.assertIn("Default port</dt><dd>4477", INDEX)

    def test_hud_does_not_claim_brain_reachability(self):
        self.assertIn("not probed by HUD", INDEX)
        self.assertIn("LINK ONLY // NO PROCESS AUTHORITY", INDEX)

        forbidden_claims = (
            "BRAIN ONLINE",
            "BRAIN CONNECTED",
            "Brain online",
            "Brain connected",
        )

        for claim in forbidden_claims:
            with self.subTest(claim=claim):
                self.assertNotIn(claim, INDEX)

    def test_memory_lens_does_not_add_process_or_backend_authority(self):
        self.assertNotIn("127.0.0.1:4477", APP)
        self.assertNotIn("/api/orion/memory", APP)
        self.assertNotIn("/api/orion/memory", BRIDGE)
        self.assertNotIn("window.open(", APP)
        self.assertNotIn("subprocess", APP)
        self.assertNotIn("child_process", APP)

    def test_workspace_controller_remains_pure(self):
        forbidden = (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "EventSource",
            "localStorage",
            "sessionStorage",
            "window.open(",
        )

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, WORKSPACE)

    def test_memory_lens_does_not_recreate_native_admin_controls(self):
        forbidden_ids = (
            "memoryCapture",
            "memorySearch",
            "memoryTeach",
            "memoryForget",
            "memoryRescue",
            "memoryPin",
        )

        for element_id in forbidden_ids:
            with self.subTest(element_id=element_id):
                self.assertNotIn('id="{}"'.format(element_id), INDEX)

        memory_section = re.search(
            r'data-workspace-pane="memory".*?</section>',
            INDEX,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(memory_section)
        self.assertNotIn("<form", memory_section.group(0))
        self.assertNotIn('method="post"', memory_section.group(0).lower())

    def test_memory_workspace_uses_existing_compact_and_responsive_shell(self):
        self.assertIn(
            '.workspace-shell[data-workspace="memory"]',
            STYLES,
        )
        self.assertIn(".memory-workspace", STYLES)
        self.assertIn(".memory-grid", STYLES)

    def test_existing_typed_and_system_surfaces_remain_present(self):
        for token in (
            'data-workspace-target="conversation"',
            'data-workspace-target="system"',
            'id="transcript"',
            'id="composer"',
            'id="sendButton"',
            'id="stopButton"',
            'id="workspaceBridge"',
            'id="workspaceHermes"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, INDEX)


if __name__ == "__main__":
    unittest.main(verbosity=2)
