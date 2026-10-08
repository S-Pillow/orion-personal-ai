from __future__ import annotations

import json
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

from probe_reconnect_hydration import ReconnectFixture, bridge


OUT = Path("p5-03c-artifacts")
OUT.mkdir(exist_ok=True)


def install_storage(page, *, session_id="session_1", run_id="", poison=False):
    payload = {
        "session_id": session_id,
        "run_id": run_id,
        "poison": poison,
    }
    serialized = json.dumps(payload)
    page.add_init_script(
        f"""
        (() => {{
          const {{ session_id, run_id, poison }} = {serialized};
          localStorage.setItem("orion.hermesSession", session_id);
          if (run_id) {{
            sessionStorage.setItem(
              "orion.hermesRunLocator",
              JSON.stringify({{
                version: 1,
                session_id,
                run_id,
                ...(poison ? {{
                  state: "succeeded",
                  approval: "always",
                  recovery_available: true,
                }} : {{}}),
              }}),
            );
          }}
          if (poison) {{
            localStorage.setItem("orion.actionState", "succeeded");
            localStorage.setItem("orion.approval", "accepted");
            sessionStorage.setItem("orion.fakeSuccess", "true");
          }}
        }})();
        """
    )


def wait_ready(page):
    page.wait_for_function("() => Boolean(window.__orionReconnectFixture)")
    page.wait_for_timeout(250)


def snapshot(page):
    return page.evaluate("() => window.__orionReconnectFixture.snapshot()")


def new_page(browser, fixture, **storage):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    install_storage(page, **storage)
    page.goto(fixture.origin, wait_until="networkidle")
    wait_ready(page)
    return page


class ReminderRaceAdapter:
    def __init__(self):
        self._lock = threading.Lock()
        self._block_next_list = False
        self._fail_following_list = False
        self.stale_read_started = threading.Event()
        self.release_stale_read = threading.Event()
        self.stale_read_finished = threading.Event()
        self.reconciliation_failed = threading.Event()
        self.reminders = []

    def arm_stale_read(self):
        with self._lock:
            self._block_next_list = True
            self._fail_following_list = True
        self.stale_read_started.clear()
        self.release_stale_read.clear()
        self.stale_read_finished.clear()
        self.reconciliation_failed.clear()

    @staticmethod
    def _payload(reminders):
        return {
            "authority": "hermes",
            "scheduler_active": True,
            "count": len(reminders),
            "reminders": [dict(item) for item in reminders],
        }

    def list_reminders(self):
        with self._lock:
            if self._block_next_list:
                self._block_next_list = False
                role = "stale"
                snapshot = [dict(item) for item in self.reminders]
            elif self._fail_following_list:
                self._fail_following_list = False
                role = "reconciliation_failure"
                snapshot = []
            else:
                role = "normal"
                snapshot = [dict(item) for item in self.reminders]

        if role == "stale":
            self.stale_read_started.set()
            try:
                if not self.release_stale_read.wait(timeout=10):
                    raise RuntimeError("fixture stale read was not released")
                return self._payload(snapshot)
            finally:
                self.stale_read_finished.set()

        if role == "reconciliation_failure":
            self.reconciliation_failed.set()
            raise bridge.ReminderAdapterUnavailable(
                "fixture reconciliation unavailable"
            )

        return self._payload(snapshot)

    def create_reminder(self, body):
        reminder = {
            "id": "race_1",
            "title": str(body["title"]),
            "summary": str(body["title"]),
            "schedule": str(body["schedule"]),
            "next_scheduled_time": None,
            "state": "scheduled",
            "enabled": True,
            "last_run_at": None,
            "last_run_outcome": None,
            "delivery_outcome": None,
            "error_class": None,
            "attention": "none",
        }
        with self._lock:
            self.reminders = [reminder]
        raise bridge.ReminderContractError(
            "fixture post-mutation outcome uncertainty"
        )


def run_matrix() -> dict:
    fixture = ReconnectFixture()
    results = {}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)

            # RC-01 ordinary persisted conversation reload.
            fixture.set_scenario("ordinary")
            page = new_page(browser, fixture)
            first = snapshot(page)
            assert first["sessionId"] == "session_1"
            assert first["transcript"] == [
                "persisted user turn for session_1",
                "persisted assistant reply for session_1",
            ]
            page.evaluate(
                """
                () => {
                  document.querySelector("#actionStateBadge").textContent = "SUCCEEDED";
                  document.querySelector("#approvalPanel").classList.remove("hidden");
                  localStorage.setItem("orion.fakeDomTruth", "succeeded");
                }
                """
            )
            page.reload(wait_until="networkidle")
            wait_ready(page)
            reloaded = snapshot(page)
            assert reloaded["approvalVisible"] is False
            assert reloaded["actionState"] == "none"
            assert reloaded["transcript"] == first["transcript"]
            results["rc01_reload"] = reloaded
            page.close()

            # RC-02 completed protected action rebuilds from persisted result only.
            fixture.set_scenario("completed")
            page = new_page(browser, fixture)
            completed = snapshot(page)
            assert completed["actionState"] == "succeeded"
            assert completed["execution"] == "SUCCEEDED"
            assert completed["recovery"] == "UNAVAILABLE"
            page.reload(wait_until="networkidle")
            wait_ready(page)
            completed_reload = snapshot(page)
            assert completed_reload["actionState"] == "succeeded"
            assert completed_reload["recovery"] == "UNAVAILABLE"
            results["rc02_completed"] = completed_reload
            page.close()

            # RC-03 active run locator is re-queried; action truth remains unavailable.
            fixture.set_scenario("ordinary")
            page = new_page(browser, fixture, run_id="run_active")
            active = snapshot(page)
            assert active["activeRunId"] == "run_active"
            assert active["actionState"] == "unavailable"
            assert active["execution"] == "UNAVAILABLE"
            assert active["approvalVisible"] is False
            results["rc03_active_run"] = active
            page.close()

            # RC-04 prior/fake approval controls do not survive reload.
            fixture.set_scenario("ordinary")
            page = new_page(browser, fixture, poison=True)
            page.evaluate(
                """
                () => {
                  document.querySelector("#approvalPanel").classList.remove("hidden");
                  document.querySelector("#approvalTitle").textContent = "FAKE APPROVAL";
                }
                """
            )
            page.reload(wait_until="networkidle")
            wait_ready(page)
            pending = snapshot(page)
            assert pending["approvalVisible"] is False
            assert pending["actionState"] == "none"
            results["rc04_pending_approval"] = pending
            page.close()

            # RC-05 approval/success poison plus active run cannot become success.
            fixture.set_scenario("ordinary")
            page = new_page(
                browser,
                fixture,
                run_id="run_active",
                poison=True,
            )
            accepted_gap = snapshot(page)
            assert accepted_gap["activeRunId"] == "run_active"
            assert accepted_gap["approvalVisible"] is False
            assert accepted_gap["actionState"] == "unavailable"
            assert accepted_gap["execution"] != "SUCCEEDED"
            results["rc05_approval_gap"] = accepted_gap
            page.close()

            # RC-06 a fresh HUD/bridge process has no authority-bearing memory.
            restart_fixture = ReconnectFixture()
            try:
                restart_fixture.set_scenario("completed")
                page = new_page(browser, restart_fixture)
                restarted = snapshot(page)
                assert restarted["sessionId"] == "session_1"
                assert restarted["actionState"] == "succeeded"
                assert restarted["execution"] == "SUCCEEDED"
                assert restarted["approvalVisible"] is False
                results["rc06_hud_restart"] = restarted
                page.close()
            finally:
                restart_fixture.close()

            # RC-07 expired run falls back to persisted result.
            fixture.set_scenario("completed")
            page = new_page(browser, fixture, run_id="run_expired")
            expired_with_result = snapshot(page)
            assert expired_with_result["actionState"] == "succeeded"
            assert expired_with_result["execution"] == "SUCCEEDED"
            assert expired_with_result["locator"] is None
            results["rc07_expired_fallback"] = expired_with_result
            page.close()

            # Expired run with no persisted action evidence is explicit unavailable.
            fixture.set_scenario("ordinary")
            page = new_page(browser, fixture, run_id="run_expired")
            expired_empty = snapshot(page)
            assert expired_empty["actionState"] == "unavailable"
            assert expired_empty["execution"] == "UNAVAILABLE"
            assert expired_empty["locator"] is None
            results["expired_no_result"] = expired_empty
            page.close()

            # Terminal run status cannot itself prove protected action success.
            fixture.set_scenario("ordinary")
            page = new_page(browser, fixture, run_id="run_terminal")
            terminal_empty = snapshot(page)
            assert terminal_empty["actionState"] == "unavailable"
            assert terminal_empty["execution"] == "UNAVAILABLE"
            assert terminal_empty["locator"] is not None
            results["terminal_no_result"] = terminal_empty
            page.close()

            # RC-08 delayed hydration from old session is discarded.
            fixture.set_scenario("delayed_session_1")
            page = new_page(browser, fixture)
            page.evaluate(
                "() => { window.__lateHydration = window.__orionReconnectFixture.refreshEvidence(); }"
            )
            page.select_option("#sessionSelect", "session_2")
            page.dispatch_event("#sessionSelect", "change")
            page.wait_for_timeout(700)
            race = snapshot(page)
            assert race["sessionId"] == "session_2"
            assert race["actionState"] == "none"
            assert all("session_2" in row for row in race["transcript"])
            results["rc08_session_race"] = race
            page.close()

            # Selected session disappearance clears evidence and locator.
            fixture.set_scenario("session_disappeared")
            page = new_page(browser, fixture, run_id="run_active")
            disappeared = snapshot(page)
            assert disappeared["sessionId"] == ""
            assert disappeared["actionState"] == "none"
            assert disappeared["approvalVisible"] is False
            results["rc08_session_disappeared"] = disappeared
            page.close()

            # RC-09 hydration failure clears previously displayed evidence.
            fixture.set_scenario("completed")
            page = new_page(browser, fixture)
            assert snapshot(page)["actionState"] == "succeeded"
            fixture.set_scenario("hydration_failure")
            failed = page.evaluate(
                "() => window.__orionReconnectFixture.refreshEvidence()"
            )
            assert failed["actionState"] == "none"
            assert failed["execution"] == "UNKNOWN"
            results["rc09_hydration_failure"] = failed

            fixture.set_scenario("hydration_malformed")
            malformed = page.evaluate(
                "() => window.__orionReconnectFixture.refreshEvidence()"
            )
            assert malformed["actionState"] == "none"
            results["rc09_hydration_malformed"] = malformed
            page.close()

            # RC-10 poisoned browser state is only a locator hint and cannot prove success.
            fixture.set_scenario("ordinary")
            page = new_page(
                browser,
                fixture,
                run_id="run_poison",
                poison=True,
            )
            poisoned = snapshot(page)
            assert poisoned["actionState"] == "unavailable"
            assert poisoned["execution"] != "SUCCEEDED"
            assert poisoned["approvalVisible"] is False
            assert poisoned["locator"] is None
            results["rc10_poison"] = poisoned
            page.close()

            # P6-05: a stale GET that began before an uncertain mutation cannot
            # clear the retry block after the designated reconciliation fails.
            reminder_adapter = ReminderRaceAdapter()
            fixture.orion.state.reminder_adapter = reminder_adapter
            fixture.set_scenario("ordinary")
            page = new_page(browser, fixture)
            page.locator('[data-workspace-target="reminders"]').click()
            page.wait_for_function(
                "() => !document.querySelector('[data-workspace-pane=\"reminders\"]')?.hidden"
            )
            page.wait_for_function(
                "() => document.querySelector('#reminderCount')?.textContent === '0'"
            )

            reminder_adapter.arm_stale_read()
            page.locator("#reminderRefreshButton").click()
            assert reminder_adapter.stale_read_started.wait(timeout=5)

            page.locator("#reminderTitleInput").fill("Race proof")
            page.locator("#reminderMessageInput").fill("Do not duplicate this reminder")
            page.locator("#reminderScheduleInput").fill("30m")
            page.locator("#reminderCreateButton").click()

            assert reminder_adapter.reconciliation_failed.wait(timeout=5)
            page.wait_for_function(
                "() => document.querySelector('#reminderWorkspaceStatus')?.textContent.includes('not confirmed')"
            )
            assert page.locator("#reminderCreateButton").is_disabled()
            assert page.locator("#reminderCount").text_content() == "—"

            reminder_adapter.release_stale_read.set()
            assert reminder_adapter.stale_read_finished.wait(timeout=5)

            page.evaluate(
                "() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
            )
            assert page.locator("#reminderCreateButton").is_disabled()
            assert page.locator("#reminderCount").text_content() == "—"
            assert "not confirmed" in page.locator(
                "#reminderWorkspaceStatus"
            ).text_content()

            with page.expect_response(
                lambda response: (
                    response.request.method == "GET"
                    and response.url.endswith("/api/orion/reminders")
                    and response.status == 200
                )
            ):
                page.locator("#reminderRefreshButton").click()

            page.wait_for_function(
                "() => document.querySelector('#reminderCount')?.textContent === '1' "
                "&& !document.querySelector('#reminderCreateButton')?.disabled"
            )
            results["p6_05_uncertain_stale_read"] = {
                "count": page.locator("#reminderCount").text_content(),
                "create_disabled": page.locator("#reminderCreateButton").is_disabled(),
                "status": page.locator("#reminderWorkspaceStatus").text_content(),
            }
            page.close()

            browser.close()
    finally:
        fixture.close()

    (OUT / "reconnect-summary.json").write_text(
        json.dumps(results, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return results


if __name__ == "__main__":
    result = run_matrix()
    print(json.dumps(result, indent=2, sort_keys=True))
