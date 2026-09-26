from __future__ import annotations

import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]
APP_JS = (HUD_ROOT / "static" / "app.js").read_text(encoding="utf-8")
STYLES = (HUD_ROOT / "static" / "styles.css").read_text(encoding="utf-8")
INDEX_HTML = (HUD_ROOT / "static" / "index.html").read_text(encoding="utf-8")


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

    def test_action_projection_separates_approval_from_execution(self):
        self.assertIn(
            "Approval accepted by Hermes // awaiting execution evidence",
            APP_JS,
        )
        self.assertIn(
            "approval accepted; protected execution outcome unavailable",
            APP_JS,
        )
        self.assertNotIn(
            "Approval recorded:",
            APP_JS,
        )

    def test_completed_action_hydration_uses_server_projection(self):
        self.assertIn(
            "/action-evidence",
            APP_JS,
        )
        self.assertIn(
            "presentActionProjection(latest, { hydrated: true })",
            APP_JS,
        )
        self.assertIn(
            "data?.action_evidence",
            APP_JS,
        )

    def test_run_failure_clears_stale_approval_visual(self):
        self.assertIn(
            'case "run.failed":',
            APP_JS,
        )
        self.assertIn(
            'hideApproval();',
            APP_JS,
        )
        self.assertIn(
            "protected action truth preserved separately",
            APP_JS,
        )

    def test_empty_or_failed_hydration_clears_prior_action_projection(self):
        self.assertIn(
            'clearActionProjection("No protected action evidence in selected session")',
            APP_JS,
        )
        self.assertIn(
            'clearActionProjection("Action evidence unavailable for selected session")',
            APP_JS,
        )
        self.assertIn("clearActionProjection();", APP_JS)
        self.assertIn(
            "const requestedSessionId = state.sessionId;",
            APP_JS,
        )
        self.assertIn(
            "if (state.sessionId !== requestedSessionId) return;",
            APP_JS,
        )
        self.assertIn(
            "if (state.sessionId === requestedSessionId)",
            APP_JS,
        )

    def test_approval_decision_requires_event_run_id(self):
        self.assertIn(
            "const runId = event?.run_id;",
            APP_JS,
        )
        self.assertNotIn(
            "event?.run_id || state.activeRunId",
            APP_JS,
        )

    def test_health_refresh_preserves_only_durable_hydrated_projection(self):
        self.assertIn(
            'state.actionProjection?.durability === "completed_record"',
            APP_JS,
        )
        self.assertIn(
            "{ hydrated: true },",
            APP_JS,
        )


    def test_action_evidence_workspace_is_contextual_and_structured(self):
        for marker in (
            'id="actionEvidencePanel"',
            'class="panel action-evidence-panel hidden"',
            'id="actionStateBadge"',
            'id="actionDiff"',
            'id="actionEvidenceList"',
            'id="actionTechnicalList"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, INDEX_HTML)
        self.assertIn("function renderActionWorkspace(projection)", APP_JS)
        self.assertIn("renderActionWorkspace(null);", APP_JS)
        self.assertIn("ui.actionEvidencePanel.classList.add(\"hidden\")", APP_JS)

    def test_action_workspace_keeps_approval_distinct_from_execution(self):
        self.assertIn(
            "Hermes approval is not execution evidence.",
            INDEX_HTML,
        )
        self.assertIn(
            'execution: "UNPROVEN"',
            APP_JS,
        )
        self.assertIn(
            "Protected execution remains unproven.",
            APP_JS,
        )

    def test_action_workspace_renders_exact_diff_and_allowlisted_technical_fields(self):
        self.assertIn(
            'ui.actionDiff.textContent = diff;',
            APP_JS,
        )
        self.assertIn(
            "const ACTION_TECHNICAL_FIELDS = [",
            APP_JS,
        )
        self.assertIn(
            "technicalEvidenceRows(projection)",
            APP_JS,
        )
        self.assertIn("white-space: pre;", STYLES)
        self.assertNotIn("JSON.stringify(projection", APP_JS)

    def test_action_workspace_recent_evidence_is_presentation_only(self):
        self.assertIn(
            "state.actionEvidence.slice(-5).reverse()",
            APP_JS,
        )
        self.assertIn(
            'item.className = "action-evidence-item";',
            APP_JS,
        )
        self.assertNotIn(
            "actionEvidenceList.addEventListener",
            APP_JS,
        )


    def test_approval_event_must_match_active_streamed_run(self):
        self.assertIn("runId !== state.activeRunId", APP_JS)
        self.assertIn(
            "Approval run mismatch // decision controls withheld",
            APP_JS,
        )
        self.assertNotIn(
            "if (runId && !state.activeRunId)",
            APP_JS,
        )

    def test_disappearing_selected_session_clears_action_evidence(self):
        anchor = 'else if (previous) {'
        start = APP_JS.index(anchor)
        self.assertGreaterEqual(start, 0)
        block = APP_JS[start:start + 420]
        self.assertIn('state.sessionId = "";', block)
        self.assertIn("clearActionProjection();", block)
        self.assertIn("hideApproval();", block)

    def test_pending_approval_precedes_evidence_and_scrolls_controls_into_view(self):
        approval_at = INDEX_HTML.index('id="approvalPanel"')
        evidence_at = INDEX_HTML.index('id="actionEvidencePanel"')
        self.assertGreaterEqual(approval_at, 0)
        self.assertGreaterEqual(evidence_at, 0)
        self.assertLess(approval_at, evidence_at)
        self.assertIn(
            'ui.approvalPanel.scrollIntoView({',
            APP_JS,
        )

    def test_late_approval_receipt_is_discarded_after_terminal_state(self):
        self.assertIn("state.approvalEvent !== event", APP_JS)
        self.assertIn("state.activeRunId !== runId", APP_JS)

    def test_terminal_run_events_require_active_run_match(self):
        self.assertIn('case "run.completed": {', APP_JS)
        self.assertIn('case "run.cancelled":', APP_JS)
        self.assertIn('case "run.failed":', APP_JS)
        self.assertGreaterEqual(
            APP_JS.count("runId !== state.activeRunId"),
            4,
        )

    def test_startup_loads_persisted_session_history_once(self):
        self.assertIn(
            "async function refreshStatus(loadCurrentSession = false)",
            APP_JS,
        )
        self.assertIn(
            "refreshSessions({ loadCurrent: loadCurrentSession })",
            APP_JS,
        )
        self.assertIn(
            "refreshStatus(true);",
            APP_JS,
        )
        self.assertIn(
            "setInterval(refreshStatus, 15000);",
            APP_JS,
        )
        self.assertNotIn(
            "setInterval(() => refreshStatus(true)",
            APP_JS,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
