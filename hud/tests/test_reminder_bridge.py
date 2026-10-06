from __future__ import annotations

import http.client
import json
import sys
import threading
import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUD_ROOT))

import orion_hud_bridge as bridge  # noqa: E402


class FakeReminderAdapter:
    def __init__(self):
        self.calls = []
        self.create_error = None
        self.reminder = {
            "id": "reminder_1",
            "title": "Water plants",
            "summary": "Water plants",
            "schedule": "30m",
            "next_scheduled_time": "2026-10-05T14:00:00+00:00",
            "state": "scheduled",
            "enabled": True,
            "last_run_at": None,
            "last_run_outcome": None,
            "delivery_outcome": None,
            "error_class": None,
            "attention": "none",
        }

    def list_reminders(self):
        self.calls.append(("list", None))
        return {
            "authority": "hermes",
            "scheduler_active": True,
            "count": 1,
            "reminders": [dict(self.reminder)],
        }

    def get_reminder(self, reminder_id):
        self.calls.append(("get", reminder_id))
        if reminder_id != self.reminder["id"]:
            raise bridge.ReminderNotFound("missing")
        return dict(self.reminder)

    def reminder_runs(self, reminder_id):
        self.calls.append(("runs", reminder_id))
        if reminder_id != self.reminder["id"]:
            raise bridge.ReminderNotFound("missing")
        return {
            "authority": "hermes",
            "reminder_id": reminder_id,
            "count": 1,
            "runs": [{
                "id": "exec_1",
                "job_id": reminder_id,
                "scheduled_at": "2026-10-05T14:00:00+00:00",
                "claimed_at": "2026-10-05T14:00:01+00:00",
                "started_at": "2026-10-05T14:00:02+00:00",
                "finished_at": "2026-10-05T14:00:03+00:00",
                "status": "completed",
                "delivery_outcome": "delivered",
                "error_class": None,
            }],
        }

    def create_reminder(self, body):
        self.calls.append(("create", dict(body)))
        if self.create_error is not None:
            raise self.create_error
        unknown = set(body) - {"title", "message", "schedule"}
        if unknown:
            raise bridge.ReminderInputError(
                "unsupported reminder field"
            )
        result = dict(self.reminder)
        result["title"] = body["title"]
        result["summary"] = body["title"]
        result["schedule"] = body["schedule"]
        return result

    def pause_reminder(self, reminder_id):
        self.calls.append(("pause", reminder_id))
        result = self.get_reminder(reminder_id)
        result["state"] = "paused"
        result["enabled"] = False
        return result

    def resume_reminder(self, reminder_id):
        self.calls.append(("resume", reminder_id))
        result = self.get_reminder(reminder_id)
        result["state"] = "scheduled"
        result["enabled"] = True
        return result

    def cancel_reminder(self, reminder_id):
        self.calls.append(("cancel", reminder_id))
        if reminder_id != self.reminder["id"]:
            raise bridge.ReminderNotFound("missing")
        return {
            "authority": "hermes",
            "id": reminder_id,
            "state": "cancelled",
        }


class ReminderBridgeFixture:
    def __init__(self):
        self.adapter = FakeReminderAdapter()
        state = bridge.BridgeState(
            target=bridge.HermesTarget("127.0.0.1", 9),
            api_key="unused-test-key",
            ui_cookie="test-cookie",
            static_root=HUD_ROOT / "static",
            reminder_adapter=self.adapter,
        )
        self.server = bridge.OrionHTTPServer(
            ("127.0.0.1", 0),
            state,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class ReminderBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ReminderBridgeFixture()
        self.conn = http.client.HTTPConnection(
            "127.0.0.1",
            self.fixture.server.server_port,
            timeout=5,
        )

    def tearDown(self):
        self.conn.close()
        self.fixture.close()

    def request(
        self,
        method,
        path,
        body=None,
        *,
        cookie=True,
        origin=True,
    ):
        payload = (
            None
            if body is None
            else json.dumps(body).encode("utf-8")
        )
        headers = {}

        if cookie:
            headers["Cookie"] = "orion_ui=test-cookie"
        if origin:
            headers["Origin"] = self.fixture.origin
        if payload is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(payload))

        self.conn.request(
            method,
            path,
            body=payload,
            headers=headers,
        )
        response = self.conn.getresponse()
        data = response.read()
        return response.status, json.loads(data)

    def test_list_is_local_adapter_not_generic_proxy(self):
        status, payload = self.request(
            "GET",
            "/api/orion/reminders",
            origin=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["authority"], "hermes")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(
            self.fixture.adapter.calls[-1],
            ("list", None),
        )

    def test_get_and_runs_are_exactly_correlated(self):
        status, payload = self.request(
            "GET",
            "/api/orion/reminders/reminder_1",
            origin=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["id"], "reminder_1")

        status, payload = self.request(
            "GET",
            "/api/orion/reminders/reminder_1/runs",
            origin=False,
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            payload["reminder_id"],
            "reminder_1",
        )

    def test_create_requires_same_origin(self):
        body = {
            "title": "Pay bill",
            "message": "Pay the electric bill",
            "schedule": "30m",
        }

        status, payload = self.request(
            "POST",
            "/api/orion/reminders",
            body,
            origin=False,
        )
        self.assertEqual(status, 403)
        self.assertEqual(
            payload["error"],
            "same_origin_required",
        )

        self.assertFalse(
            any(
                call[0] == "create"
                for call in self.fixture.adapter.calls
            )
        )

    def test_create_uses_bounded_adapter_contract(self):
        body = {
            "title": "Pay bill",
            "message": "Pay the electric bill",
            "schedule": "30m",
        }
        status, payload = self.request(
            "POST",
            "/api/orion/reminders",
            body,
        )
        self.assertEqual(status, 201)
        self.assertEqual(payload["title"], "Pay bill")
        self.assertIn(("create", body), self.fixture.adapter.calls)

    def test_unsupported_create_field_fails_closed(self):
        status, payload = self.request(
            "POST",
            "/api/orion/reminders",
            {
                "title": "Unsafe",
                "message": "hello",
                "schedule": "30m",
                "script": "run-me.ps1",
            },
        )
        self.assertEqual(status, 400)
        self.assertEqual(
            payload["error"],
            "invalid_reminder_request",
        )
        self.assertNotIn("mutation_outcome", payload)

    def test_mutation_5xx_marks_outcome_uncertain(self):
        self.fixture.adapter.create_error = bridge.ReminderContractError(
            "post-mutation projection drift"
        )
        status, payload = self.request(
            "POST",
            "/api/orion/reminders",
            {
                "title": "Pay bill",
                "message": "Pay the electric bill",
                "schedule": "30m",
            },
        )

        self.assertEqual(status, 502)
        self.assertEqual(
            payload["mutation_outcome"],
            "uncertain",
        )

    def test_unavailable_adapter_is_definitive_before_mutation(self):
        self.fixture.server.state.reminder_adapter = None
        status, payload = self.request(
            "POST",
            "/api/orion/reminders",
            {
                "title": "Pay bill",
                "message": "Pay the electric bill",
                "schedule": "30m",
            },
        )

        self.assertEqual(status, 503)
        self.assertEqual(payload["error"], "reminders_unavailable")
        self.assertNotIn("mutation_outcome", payload)

    def test_pause_resume_require_empty_json_body(self):
        status, payload = self.request(
            "POST",
            "/api/orion/reminders/reminder_1/pause",
            {"unexpected": True},
        )
        self.assertEqual(status, 400)
        self.assertEqual(
            payload["error"],
            "reminder_action_body_must_be_empty",
        )

        status, payload = self.request(
            "POST",
            "/api/orion/reminders/reminder_1/pause",
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], "paused")

        status, payload = self.request(
            "POST",
            "/api/orion/reminders/reminder_1/resume",
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], "scheduled")

    def test_delete_is_same_origin_and_bodyless(self):
        status, payload = self.request(
            "DELETE",
            "/api/orion/reminders/reminder_1",
            origin=False,
        )
        self.assertEqual(status, 403)
        self.assertEqual(
            payload["error"],
            "same_origin_required",
        )

        status, payload = self.request(
            "DELETE",
            "/api/orion/reminders/reminder_1",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], "cancelled")

    def test_invalid_id_never_reaches_adapter(self):
        before = list(self.fixture.adapter.calls)

        status, payload = self.request(
            "POST",
            "/api/orion/reminders/%2e%2e/pause",
            {},
        )
        self.assertEqual(status, 400)
        self.assertEqual(
            payload["error"],
            "invalid_reminder_id",
        )
        self.assertEqual(
            self.fixture.adapter.calls,
            before,
        )

    def test_foreign_or_missing_reminder_is_404(self):
        status, payload = self.request(
            "GET",
            "/api/orion/reminders/not_owned",
            origin=False,
        )
        self.assertEqual(status, 404)
        self.assertEqual(
            payload["error"],
            "reminder_not_found",
        )

    def test_missing_adapter_fails_closed(self):
        self.fixture.server.state.reminder_adapter = None

        status, payload = self.request(
            "GET",
            "/api/orion/reminders",
            origin=False,
        )
        self.assertEqual(status, 503)
        self.assertEqual(
            payload["error"],
            "reminders_unavailable",
        )

    def test_unlisted_reminder_operation_stays_blocked(self):
        before = list(self.fixture.adapter.calls)

        status, payload = self.request(
            "POST",
            "/api/orion/reminders/reminder_1/run",
            {},
        )
        self.assertEqual(status, 404)
        self.assertEqual(
            payload["error"],
            "operation_not_allowlisted",
        )
        self.assertEqual(
            self.fixture.adapter.calls,
            before,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)