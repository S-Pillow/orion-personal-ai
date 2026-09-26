from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

HUD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUD_ROOT))

from action_projection import (
    project_action_evidence,
    project_action_evidence_payload,
    project_approval_request,
    project_approval_response,
    project_run_status,
    project_stream_event,
    project_transcript_payload,
)


class ActionProjectionTests(unittest.TestCase):
    def test_approval_request_is_allowlist_first_and_exact(self):
        description = (
            "Target: C:\\vault\\note.md\n"
            "--- old\n+++ new\n-old\n+new"
        )
        projected = project_approval_request({
            "event": "approval.request",
            "run_id": "run_1",
            "session_id": "session_1",
            "command": "orion_vault_apply_plan",
            "description": description,
            "choices": ["once", "deny"],
            "pattern_key": "plugin_rule:secret",
            "rule_key": "secret",
            "args": {"new_content": "private"},
            "api_key": "secret",
        })
        self.assertEqual(projected["description"], description)
        self.assertEqual(projected["choices"], ["once", "deny"])
        self.assertEqual(
            projected["projection"]["state"], "approval_requested"
        )
        rendered = json.dumps(projected)
        for forbidden in (
            "pattern_key",
            "rule_key",
            "new_content",
            "api_key",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_incomplete_approval_content_withholds_choices(self):
        projected = project_approval_request({
            "run_id": "run_1",
            "command": "orion_vault_apply_plan",
            "choices": ["once", "deny"],
        })
        self.assertEqual(projected["choices"], [])
        self.assertEqual(projected["projection"]["state"], "unavailable")

    def test_approval_response_is_decision_not_execution(self):
        projected = project_approval_response(
            "run_1",
            "once",
            {
                "object": "hermes.run.approval_response",
                "run_id": "run_1",
                "choice": "once",
                "resolved": 1,
                "secret": "must-not-leak",
            },
        )
        self.assertIsNotNone(projected)
        self.assertEqual(
            projected["projection"]["state"], "approval_accepted"
        )
        self.assertFalse(projected["execution_proven"])
        self.assertNotIn("secret", json.dumps(projected))

    def test_approval_response_rejects_incomplete_or_mismatched_receipts(self):
        invalid = (
            {"resolved": 1},
            {
                "object": "hermes.run.approval_response",
                "choice": "once",
                "resolved": 1,
            },
            {
                "object": "hermes.run.approval_response",
                "run_id": "run_1",
                "resolved": 1,
            },
            {
                "object": "hermes.run.approval_response",
                "run_id": "run_1",
                "choice": "deny",
                "resolved": 1,
            },
            {
                "object": "wrong.object",
                "run_id": "run_1",
                "choice": "once",
                "resolved": 1,
            },
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertIsNone(
                    project_approval_response("run_1", "once", payload)
                )

    def test_action_result_precedence_success_stale_and_partial_move(self):
        success = {
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "tool_call_id": "call_success",
            "content": json.dumps({
                "success": True,
                "mutation_performed": True,
                "recovery_required": False,
                "recovery_id": "a" * 64,
                "action": "edit_note",
                "target_relative_path": "notes/a.md",
                "recovery_dir": "C:/private/recovery",
            }),
        }
        stale = {
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "tool_call_id": "call_stale",
            "content": json.dumps({
                "success": False,
                "mutation_performed": False,
                "recovery_required": False,
                "error": "stale_original_hash",
                "action": "edit_note",
            }),
        }
        partial = {
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "tool_call_id": "call_partial",
            "content": json.dumps({
                "success": False,
                "mutation_performed": True,
                "recovery_required": True,
                "error": "source_changed_before_delete",
                "action": "move_draft",
                "recovery_dir": "C:/private/recovery",
            }),
        }
        items = project_action_evidence([success, stale, partial])
        self.assertEqual(
            [item["state"] for item in items],
            ["succeeded", "stale_plan", "failed"],
        )
        self.assertTrue(items[2]["recovery_required"])
        rendered = json.dumps(items)
        self.assertNotIn("recovery_dir", rendered)
        self.assertNotIn("C:/private", rendered)

    def test_refusal_is_not_failure_or_success(self):
        [item] = project_action_evidence([{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "content": json.dumps({
                "success": False,
                "mutation_performed": False,
                "recovery_required": False,
                "error": "production_mutation_not_enabled",
            }),
        }])
        self.assertEqual(item["state"], "refused")
        self.assertFalse(item["mutation_performed"])

    def test_preview_ready_requires_exact_plan_and_diff_evidence(self):
        diff = "--- old\n+++ new\n-old\n+new\n"
        plan = {
            "action": "edit_note",
            "target_relative_path": "note.md",
            "target_canonical_path": "C:/vault/note.md",
            "original_sha256": "1" * 64,
            "proposed_sha256": "2" * 64,
            "diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        }
        complete = {
            "role": "tool",
            "tool_name": "orion_vault_preview_edit",
            "content": json.dumps({
                "success": True,
                "mode": "preview",
                "mutation_performed": False,
                "plan_token": "a" * 64,
                "plan": plan,
                "diff": diff,
            }),
        }
        [projected] = project_action_evidence([complete])
        self.assertEqual(projected["state"], "preview_ready")
        self.assertEqual(projected["diff"], diff)

        incomplete = {
            "role": "tool",
            "tool_name": "orion_vault_preview_edit",
            "content": json.dumps({
                "success": True,
                "mode": "preview",
                "mutation_performed": False,
                "plan_token": "a" * 64,
            }),
        }
        [projected] = project_action_evidence([incomplete])
        self.assertEqual(projected["state"], "unavailable")
        self.assertEqual(
            projected["reason"], "preview_evidence_incomplete"
        )

    def test_success_requires_complete_action_contract_and_no_error(self):
        base = {
            "success": True,
            "mutation_performed": True,
            "recovery_required": False,
            "recovery_id": "a" * 64,
            "action": "edit_note",
            "target_relative_path": "note.md",
        }
        [complete] = project_action_evidence([{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "content": json.dumps(base),
        }])
        self.assertEqual(complete["state"], "succeeded")

        missing_target = dict(base)
        missing_target.pop("target_relative_path")
        [incomplete] = project_action_evidence([{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "content": json.dumps(missing_target),
        }])
        self.assertEqual(incomplete["state"], "unknown")
        self.assertEqual(
            incomplete["reason"], "success_evidence_incomplete"
        )

        contradictory = dict(base, error="post_write_hash_mismatch")
        [conflict] = project_action_evidence([{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "content": json.dumps(contradictory),
        }])
        self.assertEqual(conflict["state"], "unknown")
        self.assertEqual(conflict["reason"], "conflicting_action_result")

    def test_preview_hydration_never_recreates_actionability(self):
        diff = "--- old\n+++ new"
        payload = {
            "data": [{
                "role": "tool",
                "tool_name": "orion_vault_preview_edit",
                "content": json.dumps({
                    "success": True,
                    "mode": "preview",
                    "mutation_performed": False,
                    "plan_token": "b" * 64,
                    "diff": diff,
                    "plan": {
                        "action": "edit_note",
                        "target_relative_path": "note.md",
                        "target_canonical_path": "C:/vault/note.md",
                        "original_sha256": "1" * 64,
                        "proposed_sha256": "2" * 64,
                        "diff_sha256": hashlib.sha256(
                            diff.encode("utf-8")
                        ).hexdigest(),
                        "preview_nonce": "do-not-leak",
                    },
                    "proposed_bytes": "do-not-leak",
                }),
            }],
        }
        projected = project_action_evidence_payload(
            payload, session_id="session_1"
        )
        [item] = projected["items"]
        self.assertEqual(item["state"], "unavailable")
        self.assertEqual(item["historical_state"], "preview_ready")
        self.assertEqual(item["current_actionability"], "unavailable")
        rendered = json.dumps(projected)
        self.assertNotIn("preview_nonce", rendered)
        self.assertNotIn("proposed_bytes", rendered)

    def test_transcript_projection_drops_tool_rows_and_non_text_parts(self):
        payload = {
            "data": [
                {"id": "1", "role": "user", "content": "hello"},
                {
                    "id": "2",
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "safe reply"},
                        {"type": "image", "data": "base64-secret"},
                    ],
                    "tool_calls": [{"arguments": {"secret": "x"}}],
                },
                {
                    "id": "3",
                    "role": "tool",
                    "tool_name": "orion_vault_apply_plan",
                    "content": '{"secret":"x"}',
                },
            ],
        }
        projected = project_transcript_payload(payload)
        self.assertEqual(
            [row["role"] for row in projected["data"]],
            ["user", "assistant"],
        )
        rendered = json.dumps(projected)
        self.assertNotIn("base64-secret", rendered)
        self.assertNotIn("tool_calls", rendered)
        self.assertNotIn('"secret"', rendered)

    def test_run_status_does_not_export_raw_error(self):
        projected = project_run_status({
            "run_id": "run_1",
            "status": "failed",
            "session_id": "session_1",
            "error": "stack trace bearer SECRET",
            "private": {"token": "SECRET"},
        })
        self.assertEqual(projected["status"], "failed")
        self.assertTrue(projected["run_error_observed"])
        self.assertNotIn("SECRET", json.dumps(projected))

    def test_run_completed_reconciles_action_result_without_raw_messages(self):
        messages = [{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "content": json.dumps({
                "success": False,
                "mutation_performed": False,
                "recovery_required": False,
                "error": "stale_original_hash",
            }),
        }]
        name, projected = project_stream_event(
            "run.completed",
            {
                "run_id": "run_1",
                "messages": messages,
                "usage": {"private": "not-needed"},
            },
        )
        self.assertEqual(name, "run.completed")
        self.assertNotIn("messages", projected)
        self.assertNotIn("usage", projected)
        self.assertEqual(
            projected["action_evidence"][0]["state"], "stale_plan"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
