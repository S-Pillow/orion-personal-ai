from __future__ import annotations

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
).read_text(encoding="utf-8")
TARGET = (
    HUD_ROOT / "static" / "target-layout.css"
).read_text(encoding="utf-8")


class ReminderWorkspaceContractTests(unittest.TestCase):
    def test_reminders_are_a_real_workspace(self):
        self.assertIn(
            'data-workspace-target="reminders"',
            INDEX,
        )
        self.assertIn(
            'data-workspace-pane="reminders"',
            INDEX,
        )
        self.assertIn('"reminders"', WORKSPACE)

    def test_create_surface_is_narrow(self):
        for element_id in (
            "reminderCreateForm",
            "reminderTitleInput",
            "reminderMessageInput",
            "reminderScheduleInput",
            "reminderCreateButton",
            "reminderRefreshButton",
            "reminderList",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(
                    f'id="{element_id}"',
                    INDEX,
                )

        self.assertNotIn(
            'id="reminderScriptInput"',
            INDEX,
        )
        self.assertNotIn(
            'id="reminderProviderInput"',
            INDEX,
        )
        self.assertNotIn(
            'id="reminderWorkdirInput"',
            INDEX,
        )

    def test_frontend_uses_only_allowlisted_reminder_routes(self):
        self.assertIn(
            'const payload = await api("/api/orion/reminders", {',
            APP,
        )
        self.assertIn('cache: "no-store"', APP)
        self.assertIn('signal: controller.signal', APP)
        self.assertIn(
            'await api("/api/orion/reminders", {',
            APP,
        )
        self.assertIn(
            '/api/orion/reminders/${encodeURIComponent(reminderId)}/${action}',
            APP,
        )
        self.assertIn(
            '/api/orion/reminders/${encodeURIComponent(reminderId)}/runs',
            APP,
        )

        self.assertNotIn(
            '/api/orion/cron',
            APP,
        )

    def test_no_manual_run_control_exists(self):
        self.assertNotIn(
            'data-reminder-action="run"',
            INDEX,
        )
        self.assertNotIn(">RUN NOW<", INDEX)

    def test_cancel_requires_explicit_user_confirmation(self):
        self.assertIn(
            "window.confirm(",
            APP,
        )
        self.assertIn(
            '{ method: "DELETE" }',
            APP,
        )

    def test_reminder_rendering_uses_dom_text_projection(self):
        self.assertIn(
            "ui.reminderList.replaceChildren();",
            APP,
        )
        self.assertIn(
            "title.textContent =",
            APP,
        )
        self.assertNotIn(
            "ui.reminderList.innerHTML",
            APP,
        )

    def test_reminders_share_existing_center_geometry(self):
        self.assertIn(
            ".reminder-workspace {",
            TARGET,
        )
        self.assertIn(
            "width:var(--center-width);",
            TARGET,
        )

    def test_schedule_examples_match_accepted_hermes_parser(self):
        self.assertIn(
            'placeholder="30m or every 30m"',
            INDEX,
        )
        self.assertNotIn("tomorrow at 9am", INDEX)
        self.assertNotIn("every weekday at 8am", INDEX)

    def test_uncertain_mutations_reconcile_before_retry(self):
        self.assertIn(
            "function reminderMutationOutcomeIsUncertain(error)",
            APP,
        )
        self.assertIn(
            'error?.payload?.mutation_outcome === "uncertain"',
            APP,
        )
        self.assertIn(
            'error?.payload?.error === "reminders_unavailable"',
            APP,
        )
        self.assertIn(
            "async function reconcileUncertainReminderMutation(label)",
            APP,
        )
        self.assertIn(
            "state.reminderMutationBlocked = true;",
            APP,
        )
        self.assertIn(
            "reconciliationToken: token",
            APP,
        )
        self.assertIn(
            "generation !== state.reminderReadGeneration",
            APP,
        )
        self.assertIn(
            "controller.abort();",
            APP,
        )
        self.assertIn(
            "readSequence !== state.reminderReadSequence",
            APP,
        )
        self.assertIn(
            "state.reminderUncertaintyToken !== reconciliationToken",
            APP,
        )
        self.assertIn(
            "verify before retrying",
            APP,
        )
        self.assertIn(
            "do not retry until confirmed",
            APP,
        )
        self.assertIn(
            "state.reminderMutationBlocked",
            APP,
        )
        self.assertIn(
            '"—",',
            APP,
        )
        self.assertIn(
            "explicit Refresh required before retrying",
            APP,
        )

    def test_reconnect_refresh_reads_authoritative_reminders(self):
        start = APP.index("async function refreshStatus")
        end = APP.index("function parseSSEFrame", start)
        refresh = APP[start:end]

        self.assertIn(
            "await refreshReminders();",
            refresh,
        )
        self.assertLess(
            refresh.index("await refreshReminders();"),
            refresh.index("if (online) {"),
        )
        self.assertIn("scheduler inactive", APP)
        self.assertNotIn(
            "Hermes offline // reminder authority unavailable",
            APP,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
