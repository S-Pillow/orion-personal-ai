from __future__ import annotations

import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]

BRIDGE = (HUD_ROOT / "orion_hud_bridge.py").read_text(
    encoding="utf-8"
)
INDEX = (HUD_ROOT / "static" / "index.html").read_text(
    encoding="utf-8"
)
APP = (HUD_ROOT / "static" / "app.js").read_text(
    encoding="utf-8"
)
CORE = (HUD_ROOT / "static" / "core-state.js").read_text(
    encoding="utf-8"
)
STYLES = (HUD_ROOT / "static" / "styles.css").read_text(
    encoding="utf-8"
)


class Phase3CoreStateContractTests(unittest.TestCase):
    def test_core_module_is_explicitly_allowlisted_and_loaded(self):
        self.assertIn(
            '"/core-state.js": '
            '("core-state.js", "text/javascript; charset=utf-8")',
            BRIDGE,
        )
        self.assertIn(
            '<script type="module" src="/app.js"></script>',
            INDEX,
        )
        self.assertIn(
            'import { installCorePresence } '
            'from "./core-state.js";',
            APP,
        )

    def test_app_feeds_observed_state_into_core_presentation(self):
        self.assertIn(
            "const corePresence = installCorePresence(",
            APP,
        )
        self.assertIn(
            "corePresence.update(name);",
            APP,
        )

        for state in (
            "ACTING",
            "WAITING",
            "DEGRADED",
            "OFFLINE",
            "ERROR",
            "STOPPING",
            "THINKING",
        ):
            with self.subTest(state=state):
                self.assertIn(
                    f'setCore("{state}"',
                    APP,
                )

    def test_gaze_mapping_is_deterministic(self):
        expected = (
            'READY: "forward"',
            'LINKING: "center"',
            'THINKING: "center"',
            'FINALIZING: "center"',
            'ACTING: "right"',
            'WAITING: "right"',
            'STOPPING: "center"',
            'DEGRADED: "left"',
            'OFFLINE: "left"',
            'ERROR: "left"',
        )

        for fragment in expected:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, CORE)

    def test_core_state_and_gaze_are_testable_dom_data(self):
        self.assertIn(
            "root.dataset.coreState = state;",
            CORE,
        )
        self.assertIn(
            "root.dataset.gaze = gaze;",
            CORE,
        )
        self.assertIn(
            'data-core-state="READY"',
            INDEX,
        )
        self.assertIn(
            'data-gaze="forward"',
            INDEX,
        )

    def test_presence_motion_is_low_cost_local_presentation(self):
        for token in (
            "is-blinking",
            "saccade-left",
            "saccade-right",
            "saccade-up",
            "saccade-down",
            "randomDelay(2800, 3200)",
            "randomDelay(1700, 2100)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, CORE)

        self.assertIn(
            "@keyframes core-breathe",
            STYLES,
        )
        self.assertIn(
            "@keyframes core-halo-drift",
            STYLES,
        )

    def test_reduced_motion_disables_generated_motion(self):
        self.assertIn(
            'matchMedia("(prefers-reduced-motion: reduce)")',
            CORE,
        )
        self.assertIn(
            'root.dataset.motion = "reduced";',
            CORE,
        )
        self.assertIn(
            "@media (prefers-reduced-motion: reduce)",
            STYLES,
        )

    def test_core_module_has_no_runtime_or_data_authority(self):
        forbidden = (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "EventSource",
            "localStorage",
            "sessionStorage",
            "navigator.mediaDevices",
            "getUserMedia",
            "RTCPeerConnection",
            "Worker(",
            "SharedWorker(",
        )

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, CORE)

    def test_memory_handoff_remains_explicitly_deferred(self):
        self.assertIn(
            "IAI BRAIN // P3-03",
            INDEX,
        )
        self.assertNotIn(
            "127.0.0.1:4477",
            INDEX + APP + CORE,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
