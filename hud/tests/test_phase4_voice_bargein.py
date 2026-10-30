from __future__ import annotations

import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]


class Phase4VoiceEarlyBargeInRegressionTests(unittest.TestCase):
    def test_interruption_waits_for_run_identity_and_cannot_cancel_next_turn(self):
        source = (HUD_ROOT / "static" / "phase4-voice.js").read_text(encoding="utf-8")

        self.assertIn("let pendingRunInterruption = false", source)
        self.assertIn("function tryIssuePendingRunInterruption()", source)
        self.assertIn("if (!pendingRunInterruption || stopButton.disabled) return false", source)
        self.assertIn("pendingRunInterruption = false", source)
        self.assertIn("if (!stopButton.disabled) stopButton.click()", source)

        self.assertIn("const priorRunBusy = sendButton.disabled || !stopButton.disabled", source)
        self.assertIn("pendingRunInterruption = priorRunBusy", source)
        self.assertIn("tryIssuePendingRunInterruption()", source)

        self.assertIn("const stopObserver = new MutationObserver", source)
        self.assertIn(
            'stopObserver.observe(stopButton, { attributes: true, attributeFilter: ["disabled"] })',
            source,
        )

        self.assertIn(
            "if (pendingRunInterruption && !sendButton.disabled && stopButton.disabled)",
            source,
        )
        self.assertIn("pendingRunInterruption = false", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
