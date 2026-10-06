from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory


HUD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUD_ROOT))

from reminder_adapter import (  # noqa: E402
    EXPECTED_HERMES_HEAD,
    EXPECTED_HERMES_VERSION,
    REMINDER_DELIVERY_TARGET,
    ReminderAdapter,
    ReminderAdapterUnavailable,
    ReminderContractError,
    ReminderInputError,
    ReminderNotFound,
    read_hermes_project_version,
)
from reminder_projection import (  # noqa: E402
    ORION_REMINDER_PREFIX,
    ReminderProjectionError,
)


class FakeCron:
    def __init__(self):
        self.calls = []
        self.jobs = {
            "foreign": {
                "job_id": "foreign",
                "name": "Foreign Hermes job",
                "schedule": "every 1h",
                "next_run_at": "2026-10-05T13:00:00+00:00",
                "last_run_at": None,
                "last_status": None,
                "enabled": True,
                "state": "scheduled",
            }
        }
        self.counter = 0

    def __call__(self, *, action, **kwargs):
        self.calls.append((action, dict(kwargs)))

        if action == "list":
            return json.dumps({
                "success": True,
                "gateway_running": True,
                "count": len(self.jobs),
                "jobs": list(self.jobs.values()),
            })

        if action == "create":
            self.counter += 1
            job_id = f"orion_{self.counter}"
            job = {
                "job_id": job_id,
                "name": kwargs["name"],
                "prompt_preview": kwargs["prompt"][:100],
                "schedule": kwargs["schedule"],
                "deliver": kwargs["deliver"],
                "next_run_at": "2026-10-05T14:00:00+00:00",
                "last_run_at": None,
                "last_status": None,
                "enabled": True,
                "state": "scheduled",
            }
            self.jobs[job_id] = job
            return json.dumps({
                "success": True,
                "job_id": job_id,
                "job": job,
            })

        job_id = kwargs.get("job_id")
        job = self.jobs.get(job_id)
        if not job:
            return json.dumps({
                "success": False,
                "error": f"Job with ID or name '{job_id}' not found.",
            })

        if action == "pause":
            job["enabled"] = False
            job["state"] = "paused"
            return json.dumps({"success": True, "job": dict(job)})

        if action == "resume":
            job["enabled"] = True
            job["state"] = "scheduled"
            return json.dumps({"success": True, "job": dict(job)})

        if action == "remove":
            removed = self.jobs.pop(job_id)
            return json.dumps({
                "success": True,
                "removed_job": {
                    "id": job_id,
                    "name": removed["name"],
                    "schedule": removed["schedule"],
                },
            })

        raise AssertionError(f"unexpected fake action: {action}")


class ReminderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.cron = FakeCron()
        self.execution_rows = {
            "orion_1": [{
                "id": "exec_1",
                "job_id": "orion_1",
                "status": "completed",
                "scheduled_at": "2026-10-05T14:00:00+00:00",
                "claimed_at": "2026-10-05T14:00:01+00:00",
                "started_at": "2026-10-05T14:00:02+00:00",
                "finished_at": "2026-10-05T14:00:03+00:00",
                "delivery_outcome": "delivered",
                "error_class": None,
            }]
        }

        def latest(ids):
            result = {}
            for job_id in ids:
                rows = self.execution_rows.get(job_id, [])
                if rows:
                    result[job_id] = rows[0]
            return result

        def history(*, job_id=None, limit=50, **_kwargs):
            return list(self.execution_rows.get(job_id, []))[:limit]

        self.adapter = ReminderAdapter(
            cronjob_fn=self.cron,
            latest_executions_fn=latest,
            list_executions_fn=history,
            hermes_head=EXPECTED_HERMES_HEAD,
            hermes_version=EXPECTED_HERMES_VERSION,
        )

    def create(self):
        return self.adapter.create_reminder({
            "title": "Water plants",
            "message": "Please remind me to water the plants.",
            "schedule": "30m",
        })

    def test_list_hides_unrelated_hermes_jobs(self):
        result = self.adapter.list_reminders()
        self.assertEqual(result["count"], 0)

    def test_create_uses_narrow_native_shape(self):
        reminder = self.create()
        self.assertEqual(reminder["title"], "Water plants")

        action, kwargs = self.cron.calls[-1]
        self.assertEqual(action, "create")
        self.assertEqual(
            set(kwargs),
            {"name", "prompt", "schedule", "deliver"},
        )
        self.assertTrue(
            kwargs["name"].startswith(ORION_REMINDER_PREFIX)
        )
        self.assertNotIn("script", kwargs)
        self.assertNotIn("provider", kwargs)
        self.assertNotIn("base_url", kwargs)
        self.assertNotIn("workdir", kwargs)

    def test_mutations_do_not_depend_on_post_mutation_execution_lookup(self):
        def fail_latest(_ids):
            raise AssertionError(
                "mutation response must not depend on execution-history lookup"
            )

        adapter = ReminderAdapter(
            cronjob_fn=self.cron,
            latest_executions_fn=fail_latest,
            list_executions_fn=lambda **_kwargs: [],
            hermes_head=EXPECTED_HERMES_HEAD,
            hermes_version=EXPECTED_HERMES_VERSION,
        )

        created = adapter.create_reminder({
            "title": "Water plants",
            "message": "Please remind me to water the plants.",
            "schedule": "30m",
        })
        paused = adapter.pause_reminder(created["id"])
        resumed = adapter.resume_reminder(created["id"])

        self.assertEqual(created["state"], "scheduled")
        self.assertEqual(paused["state"], "paused")
        self.assertEqual(resumed["state"], "scheduled")

    def test_post_mutation_projection_failure_does_not_retry_create(self):
        with patch(
            "reminder_adapter.project_reminder",
            side_effect=ReminderProjectionError("projection drift"),
        ):
            with self.assertRaises(ReminderContractError):
                self.create()

        create_calls = [
            action
            for action, _kwargs in self.cron.calls
            if action == "create"
        ]
        self.assertEqual(create_calls, ["create"])

    def test_unknown_create_fields_fail_closed(self):
        with self.assertRaises(ReminderInputError):
            self.adapter.create_reminder({
                "title": "Unsafe",
                "message": "hello",
                "schedule": "30m",
                "script": "do-something.ps1",
            })

        self.assertFalse(
            any(action == "create" for action, _ in self.cron.calls)
        )

    def test_create_pause_resume_cancel_roundtrip(self):
        created = self.create()
        job_id = created["id"]

        paused = self.adapter.pause_reminder(job_id)
        self.assertEqual(paused["state"], "paused")
        self.assertFalse(paused["enabled"])

        resumed = self.adapter.resume_reminder(job_id)
        self.assertEqual(resumed["state"], "scheduled")
        self.assertTrue(resumed["enabled"])

        cancelled = self.adapter.cancel_reminder(job_id)
        self.assertEqual(cancelled["state"], "cancelled")

        with self.assertRaises(ReminderNotFound):
            self.adapter.get_reminder(job_id)

    def test_project_version_reader_uses_project_section(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                '[project]\n'
                'name = "hermes-agent"\n'
                'version = "0.20.6"\n'
                '\n'
                '[tool.example]\n'
                'version = "99.0.0"\n',
                encoding="utf-8",
            )

            self.assertEqual(
                read_hermes_project_version(root),
                EXPECTED_HERMES_VERSION,
            )

    def test_version_mismatch_fails_closed(self):
        with self.assertRaises(ReminderAdapterUnavailable):
            ReminderAdapter(
                cronjob_fn=self.cron,
                latest_executions_fn=lambda _ids: {},
                list_executions_fn=lambda **_kwargs: [],
                hermes_head=EXPECTED_HERMES_HEAD,
                hermes_version="0.20.5",
            )

    def test_adapter_never_invokes_run(self):
        created = self.create()
        self.adapter.pause_reminder(created["id"])
        self.adapter.resume_reminder(created["id"])
        self.adapter.cancel_reminder(created["id"])

        actions = [action for action, _ in self.cron.calls]
        self.assertNotIn("run", actions)
        self.assertNotIn("run_now", actions)
        self.assertNotIn("trigger", actions)

    def test_foreign_job_cannot_be_mutated(self):
        with self.assertRaises(ReminderNotFound):
            self.adapter.pause_reminder("foreign")

        actions = [action for action, _ in self.cron.calls]
        self.assertNotIn("pause", actions)

    def test_history_is_exactly_job_correlated(self):
        created = self.create()
        job_id = created["id"]

        result = self.adapter.reminder_runs(job_id)
        self.assertEqual(result["reminder_id"], job_id)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["runs"][0]["id"], "exec_1")
        self.assertEqual(
            result["runs"][0]["delivery_outcome"],
            "delivered",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
