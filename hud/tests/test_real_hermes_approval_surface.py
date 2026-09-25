"""Static/source checks for the real-Hermes no-write HUD approval probe."""
from pathlib import Path
import unittest

from probe_real_hermes_approval_surface import ALLOWED_CHOICES, hud_approval_event


class RealHermesApprovalSurfaceProbeTests(unittest.TestCase):
    def test_hud_projection_exposes_only_once_and_deny(self):
        event = hud_approval_event("run-1", {
            "command": "<orion_vault_apply_plan> (plugin approval rule)",
            "description": "exact diff",
            "pattern_key": "plugin_rule:private",
            "allow_session": True,
            "allow_permanent": True,
        })
        self.assertEqual(event["run_id"], "run-1")
        self.assertEqual(event["choices"], ["once", "deny"])
        self.assertFalse(event["allow_session"])
        self.assertFalse(event["allow_permanent"])
        self.assertEqual(ALLOWED_CHOICES, frozenset({"once", "deny"}))

    def test_probe_never_calls_disposable_or_registered_mutator(self):
        source = Path(__file__).with_name(
            "probe_real_hermes_approval_surface.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_execute_disposable_plan_candidate(", source)
        self.assertNotIn("apply_plan_placeholder(", source)
        self.assertIn("_probe_fresh_once_approval(", source)
        self.assertIn("resolve_gateway_approval(", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
