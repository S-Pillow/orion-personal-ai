from __future__ import annotations

import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]

BRIDGE = (HUD_ROOT / "orion_hud_bridge.py").read_text(
    encoding="utf-8"
)

APP = (HUD_ROOT / "static" / "app.js").read_text(
    encoding="utf-8"
)

INDEX = (HUD_ROOT / "static" / "index.html").read_text(
    encoding="utf-8"
)

STYLES = (HUD_ROOT / "static" / "styles.css").read_text(
    encoding="utf-8"
)

PROVENANCE = (
    HUD_ROOT / "static" / "provenance-state.js"
).read_text(
    encoding="utf-8"
)


class Phase3ProvenanceAuthorityContractTests(unittest.TestCase):
    def test_pure_module_is_explicitly_allowlisted(self):
        self.assertIn(
            '"/provenance-state.js": '
            '("provenance-state.js", '
            '"text/javascript; charset=utf-8")',
            BRIDGE,
        )

        self.assertIn(
            'from "./provenance-state.js";',
            APP,
        )

    def test_no_new_provenance_backend_route_exists(self):
        for token in (
            "/api/orion/provenance",
            "/api/model/options",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, BRIDGE)
                self.assertNotIn(token, APP)
                self.assertNotIn(token, PROVENANCE)

    def test_classifier_has_no_runtime_or_data_authority(self):
        forbidden = (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "EventSource",
            "localStorage",
            "sessionStorage",
            "navigator.",
            "Worker(",
            "SharedWorker(",
            "RTCPeerConnection",
            "getUserMedia",
        )

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, PROVENANCE)

    def test_default_response_origin_is_unobserved(self):
        self.assertIn(
            'origin: "UNOBSERVED"',
            PROVENANCE,
        )

        self.assertIn(
            'evidenceClass: "UNOBSERVED"',
            PROVENANCE,
        )

    def test_source_and_memory_use_default_to_unobserved(self):
        self.assertIn(
            'source: ""',
            PROVENANCE,
        )

        self.assertIn(
            'memoryUse: ""',
            PROVENANCE,
        )

        self.assertIn(
            'source: base.source || ""',
            PROVENANCE,
        )

        self.assertIn(
            'memoryUse: base.memoryUse || ""',
            PROVENANCE,
        )

        self.assertIn(
            "SOURCE &#183; UNOBSERVED",
            INDEX,
        )

        self.assertIn(
            "MEMORY USE &#183; UNOBSERVED",
            INDEX,
        )

    def test_observed_provider_model_do_not_imply_locality(self):
        body = PROVENANCE.split(
            "export function observeCompletionRuntime",
            1,
        )[1].split(
            "export function classifyAuthority",
            1,
        )[0]

        self.assertIn(
            'origin: "UNOBSERVED"',
            body,
        )

        self.assertNotIn(
            '"LOCAL"',
            body,
        )

        self.assertNotIn(
            '"CLOUD',
            body,
        )

        self.assertIn(
            'evidenceClass: "OBSERVED_RUNTIME"',
            body,
        )

    def test_run_started_is_not_final_runtime_evidence(self):
        block = APP.split(
            'case "run.started":',
            1,
        )[1].split(
            'case "message.started":',
            1,
        )[0]

        self.assertIn(
            "createProvenanceState()",
            block,
        )

        self.assertNotIn(
            "observeCompletionRuntime",
            block,
        )

    def test_completion_events_accept_supported_runtime_metadata(self):
        assistant_block = APP.split(
            'case "assistant.completed":',
            1,
        )[1].split(
            'case "run.completed":',
            1,
        )[0]

        run_block = APP.split(
            'case "run.completed":',
            1,
        )[1].split(
            'case "run.cancelled":',
            1,
        )[0]

        self.assertIn(
            "observeCompletionRuntime",
            assistant_block,
        )

        self.assertIn(
            "data?.runtime",
            assistant_block,
        )

        self.assertIn(
            "observeCompletionRuntime",
            run_block,
        )

        self.assertIn(
            "data?.runtime",
            run_block,
        )

    def test_descriptive_authority_states_are_bounded(self):
        for state in (
            "OBSERVE",
            "ASSIST",
            "ACT WITH APPROVAL",
        ):
            with self.subTest(state=state):
                self.assertIn(
                    '"{}"'.format(state),
                    PROVENANCE,
                )

        self.assertNotIn(
            '"AUTHORIZED"',
            PROVENANCE,
        )

    def test_top_edge_and_system_detail_are_present(self):
        for element_id in (
            "originStatus",
            "sourceStatus",
            "memoryUseStatus",
            "authorityStatus",
            "workspaceOrigin",
            "workspaceProvider",
            "workspaceModel",
            "workspaceProvenanceEvidence",
            "workspaceSource",
            "workspaceMemoryUse",
            "workspaceAuthority",
            "workspaceBaseline",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(
                    'id="{}"'.format(element_id),
                    INDEX,
                )

        self.assertIn(
            "data-provenance-origin",
            STYLES,
        )

        self.assertIn(
            "data-authority-state",
            STYLES,
        )

    def test_accepted_baseline_is_visually_distinct_from_turn_evidence(self):
        self.assertIn(
            "qwen3.5-hermes:9b / Ollama / LOCAL",
            INDEX,
        )

        self.assertIn(
            "Accepted baseline is configuration evidence only",
            INDEX,
        )

        self.assertIn(
            "per-turn response-origin proof",
            INDEX,
        )

    def test_p3_04_does_not_add_a_workspace(self):
        self.assertEqual(
            INDEX.count("data-workspace-target="),
            3,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
