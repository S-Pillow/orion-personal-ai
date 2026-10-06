from __future__ import annotations

import sys
import unittest
from pathlib import Path


HUD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUD_ROOT))

from reminder_projection import (  # noqa: E402
    ORION_REMINDER_PREFIX,
    ReminderProjectionError,
    is_orion_reminder,
    project_execution,
    project_execution_history,
    project_reminder,
    project_reminder_list,
)


class ReminderProjectionTests(unittest.TestCase):
    def native_job(self, **updates):
        job = {
            "job_id": "job_1",
            "name": ORION_REMINDER_PREFIX + "Take medication",
            "prompt_preview": "SECRET BODY MUST NOT LEAK",
            "schedule": "once in 30m",
            "next_run_at": "2026-10-05T12:00:00+00:00",
            "last_run_at": None,
            "last_status": None,
            "enabled": True,
            "state": "scheduled",
            "provider": "secret-provider-shape",
            "base_url": "https://should-not-render.invalid",
        }
        job.update(updates)
        return job

    def test_owned_marker_is_explicit(self):
        self.assertTrue(is_orion_reminder(self.native_job()))
        self.assertFalse(
            is_orion_reminder({
                "job_id": "other",
                "name": "ordinary Hermes cron job",
            })
        )

    def test_projection_omits_prompt_and_runtime_details(self):
        projected = project_reminder(self.native_job())
        self.assertEqual(projected["id"], "job_1")
        self.assertEqual(projected["title"], "Take medication")
        self.assertEqual(projected["summary"], "Take medication")

        serialized = repr(projected)
        self.assertNotIn("SECRET BODY", serialized)
        self.assertNotIn("provider", projected)
        self.assertNotIn("base_url", projected)
        self.assertNotIn("prompt_preview", projected)

    def test_execution_projection_is_bounded(self):
        projected = project_execution({
            "id": "exec_1",
            "job_id": "job_1",
            "status": "failed",
            "scheduled_at": "2026-10-05T12:00:00+00:00",
            "claimed_at": "2026-10-05T12:00:01+00:00",
            "started_at": "2026-10-05T12:00:02+00:00",
            "finished_at": "2026-10-05T12:00:03+00:00",
            "delivery_outcome": "failed",
            "error_class": "network_error",
            "error": "raw error with potentially sensitive detail",
            "pid": 1234,
            "process_id": "secret-process-id",
        })
        self.assertEqual(projected["status"], "failed")
        self.assertEqual(projected["delivery_outcome"], "failed")
        self.assertEqual(projected["error_class"], "network_error")
        self.assertNotIn("error", projected)
        self.assertNotIn("pid", projected)
        self.assertNotIn("process_id", projected)

    def test_latest_unknown_becomes_attention_unknown(self):
        projected = project_reminder(
            self.native_job(),
            latest_execution={
                "id": "exec_1",
                "job_id": "job_1",
                "status": "unknown",
                "delivery_outcome": None,
                "error_class": "interrupted",
            },
        )
        self.assertEqual(projected["attention"], "unknown")
        self.assertEqual(projected["last_run_outcome"], "unknown")
        self.assertEqual(projected["error_class"], "interrupted")

    def test_list_filters_unrelated_hermes_jobs(self):
        payload = {
            "success": True,
            "gateway_running": True,
            "jobs": [
                self.native_job(),
                {
                    "job_id": "foreign",
                    "name": "ordinary Hermes cron",
                    "schedule": "every 1h",
                    "enabled": True,
                    "state": "scheduled",
                },
            ],
        }
        result = project_reminder_list(payload)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["reminders"][0]["id"], "job_1")
        self.assertTrue(result["scheduler_active"])

    def test_history_filters_exact_job_id(self):
        result = project_execution_history(
            [
                {"id": "a", "job_id": "job_1", "status": "completed"},
                {"id": "b", "job_id": "other", "status": "failed"},
            ],
            job_id="job_1",
        )
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["runs"][0]["id"], "a")

    def test_unowned_job_cannot_be_projected(self):
        with self.assertRaises(ReminderProjectionError):
            project_reminder({
                "job_id": "other",
                "name": "foreign",
            })


if __name__ == "__main__":
    unittest.main(verbosity=2)