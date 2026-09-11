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

STYLES = (HUD_ROOT / "static" / "styles.css").read_text(
    encoding="utf-8"
)

WORKSPACE = (
    HUD_ROOT / "static" / "workspace-state.js"
).read_text(
    encoding="utf-8"
)


class Phase3AdaptiveWorkspaceContractTests(unittest.TestCase):
    def test_workspace_module_is_explicitly_allowlisted(self):
        self.assertIn(
            '"/workspace-state.js": '
            '("workspace-state.js", '
            '"text/javascript; charset=utf-8")',
            BRIDGE,
        )

        self.assertIn(
            'import { installWorkspaceController } '
            'from "./workspace-state.js";',
            APP,
        )

    def test_conversation_is_default_workspace(self):
        self.assertIn(
            'data-workspace="conversation"',
            INDEX,
        )

        self.assertIn(
            'data-workspace-target="conversation"',
            INDEX,
        )

        self.assertIn(
            'data-workspace-pane="conversation"',
            INDEX,
        )

        self.assertIn(
            'data-workspace-target="system"',
            INDEX,
        )

        self.assertIn(
            'data-workspace-pane="system"',
            INDEX,
        )

        self.assertEqual(
            INDEX.count("data-workspace-target="),
            2,
        )

    def test_existing_typed_conversation_controls_remain(self):
        for token in (
            'id="transcript"',
            'id="composer"',
            'id="messageInput"',
            'id="sendButton"',
            'id="stopButton"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, INDEX)

        self.assertIn(
            "refreshStatus(true);",
            APP,
        )

    def test_system_workspace_mirrors_existing_observations(self):
        expected_ids = (
            "workspaceBridge",
            "workspaceHermes",
            "workspaceReadiness",
            "workspaceCredential",
            "workspaceLifecycle",
            "workspaceSession",
            "workspaceCoreState",
            "workspaceCapSessions",
            "workspaceCapStop",
            "workspaceCapApproval",
            "workspaceCapStream",
            "workspaceSkills",
            "workspaceJobs",
        )

        for element_id in expected_ids:
            with self.subTest(element_id=element_id):
                self.assertIn(
                    'id="{}"'.format(element_id),
                    INDEX,
                )

        self.assertIn(
            "function syncSystemWorkspace()",
            APP,
        )

    def test_status_observations_sync_before_online_branch(self):
        expected = (
            '    ui.bridgeValue.textContent = '
            'payload?.bridge?.status || "online";\n'
            '    ui.credentialValue.textContent = '
            'payload?.hermes?.credentials_available '
            '? "available" : "missing";\n'
            '    syncSystemWorkspace();\n'
            '\n'
            '    if (online) {\n'
        )

        self.assertIn(expected, APP)

    def test_workspace_state_is_deterministic_and_testable(self):
        self.assertIn(
            '"conversation"',
            WORKSPACE,
        )

        self.assertIn(
            '"system"',
            WORKSPACE,
        )

        self.assertIn(
            "root.dataset.workspace = workspace;",
            WORKSPACE,
        )

        self.assertIn(
            "root.dataset.workspaceFocus = normalized;",
            WORKSPACE,
        )

        self.assertIn(
            "pane.hidden =",
            WORKSPACE,
        )

    def test_nonconversation_workspace_compacts_core_area(self):
        self.assertIn(
            '.workspace-shell[data-workspace="system"]',
            STYLES,
        )

        self.assertIn(
            "minmax(150px, 20vh)",
            STYLES,
        )

    def test_approval_focus_does_not_duplicate_controls(self):
        self.assertEqual(
            INDEX.count('id="approvalActions"'),
            1,
        )

        self.assertIn(
            "workspaceController.setApprovalFocus(true);",
            APP,
        )

        self.assertIn(
            "workspaceController.setApprovalFocus(false);",
            APP,
        )

        self.assertIn(
            'data-workspace-focus="approval"',
            STYLES,
        )

    def test_workspace_module_has_no_runtime_or_data_authority(self):
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
                self.assertNotIn(token, WORKSPACE)

    def test_future_surfaces_are_not_falsely_advertised(self):
        self.assertNotIn(
            'data-workspace-target="memory"',
            INDEX,
        )

        self.assertNotIn(
            'data-workspace-target="vault"',
            INDEX,
        )

        self.assertNotIn(
            'data-workspace-target="tasks"',
            INDEX,
        )

        self.assertIn(
            "IAI BRAIN // P3-03",
            INDEX,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
