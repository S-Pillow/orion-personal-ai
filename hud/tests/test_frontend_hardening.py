from __future__ import annotations

import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]
APP_JS = (HUD_ROOT / "static" / "app.js").read_text(encoding="utf-8")
STYLES = (HUD_ROOT / "static" / "styles.css").read_text(encoding="utf-8")


class FrontendHardeningContractTests(unittest.TestCase):
    def test_persisted_transcript_suppresses_empty_display_records(self):
        self.assertIn(
            '.map((m) => ({ role: m.role, text: messageText(m) }))',
            APP_JS,
        )
        self.assertIn(
            '.filter((m) => m.text.trim().length > 0)',
            APP_JS,
        )
        self.assertIn(
            'appendMessage(message.role, message.text)',
            APP_JS,
        )

    def test_stream_does_not_eagerly_create_blank_assistant_card(self):
        self.assertNotIn(
            'const assistantBody = appendMessage("assistant", "");',
            APP_JS,
        )
        self.assertIn(
            'const assistant = { body: null };',
            APP_JS,
        )
        self.assertIn(
            'function ensureAssistantBody(holder)',
            APP_JS,
        )
        self.assertIn(
            'const assistantBody = ensureAssistantBody(assistant);',
            APP_JS,
        )

    def test_online_non_ok_readiness_has_explicit_degraded_state(self):
        self.assertIn(
            'const degraded = online && detailedStatus !== "ok";',
            APP_JS,
        )
        self.assertIn(
            'label = "HERMES DEGRADED";',
            APP_JS,
        )
        self.assertIn(
            'setCore("DEGRADED"',
            APP_JS,
        )

    def test_degraded_status_has_warning_presentation(self):
        self.assertIn(
            ".status-chip.degraded",
            STYLES,
        )
        self.assertIn(
            "color: var(--warn);",
            STYLES,
        )

    def test_existing_truthful_terminal_states_remain_present(self):
        for state in (
            "OFFLINE",
            "ERROR",
            "STOPPING",
            "WAITING",
            "ACTING",
        ):
            with self.subTest(state=state):
                self.assertIn(
                    f'setCore("{state}"',
                    APP_JS,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
