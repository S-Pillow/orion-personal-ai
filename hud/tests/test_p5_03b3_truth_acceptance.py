from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HUD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUD_ROOT))

from action_projection import (
    project_action_evidence,
    project_approval_request,
    project_approval_response,
    project_run_status,
    project_stream_event,
)


def tool_result(payload: dict, *, run_id: str = "run_1") -> dict:
    return {
        "role": "tool",
        "run_id": run_id,
        "tool_name": "orion_vault_apply_plan",
        "tool_call_id": "call_1",
        "content": json.dumps(payload),
    }


class P503B3TruthAcceptanceTests(unittest.TestCase):
    def test_approval_acceptance_is_decision_only_and_secret_free(self):
        projected = project_approval_response(
            "run_1",
            "once",
            {
                "object": "hermes.run.approval_response",
                "run_id": "run_1",
                "choice": "once",
                "resolved": 1,
                "secret": "DO-NOT-LEAK",
            },
        )
        self.assertIsNotNone(projected)
        self.assertEqual(
            projected["projection"]["state"],
            "approval_accepted",
        )
        self.assertFalse(projected["execution_proven"])
        self.assertNotIn("DO-NOT-LEAK", json.dumps(projected))

    def test_approval_denial_never_claims_execution(self):
        projected = project_approval_response(
            "run_1",
            "deny",
            {
                "object": "hermes.run.approval_response",
                "run_id": "run_1",
                "choice": "deny",
                "resolved": 1,
            },
        )
        self.assertIsNotNone(projected)
        self.assertEqual(
            projected["projection"]["state"],
            "approval_denied",
        )
        self.assertFalse(projected["execution_proven"])

    def test_authoritative_result_matrix_distinguishes_terminal_truth(self):
        rows = [
            tool_result({
                "success": True,
                "mutation_performed": True,
                "recovery_required": False,
                "recovery_id": "a" * 64,
                "action": "edit_note",
                "target_relative_path": "notes/success.md",
            }),
            tool_result({
                "success": False,
                "mutation_performed": False,
                "recovery_required": False,
                "error": "production_mutation_not_enabled",
            }),
            tool_result({
                "success": False,
                "mutation_performed": False,
                "recovery_required": False,
                "error": "stale_original_hash",
            }),
            tool_result({
                "success": False,
                "mutation_performed": True,
                "recovery_required": True,
                "recovery_id": "b" * 64,
                "error": "source_changed_before_delete",
                "action": "move_draft",
            }),
        ]
        projected = project_action_evidence(rows)
        self.assertEqual(
            [item["state"] for item in projected],
            ["succeeded", "refused", "stale_plan", "failed"],
        )
        self.assertFalse(projected[0]["recovery_required"])
        self.assertFalse(projected[1]["mutation_performed"])
        self.assertFalse(projected[2]["mutation_performed"])
        self.assertTrue(projected[3]["recovery_required"])

    def test_partial_success_shape_cannot_be_upgraded_to_success(self):
        partials = (
            {
                "success": True,
                "mutation_performed": True,
                "recovery_required": False,
                "action": "edit_note",
                "target_relative_path": "notes/a.md",
            },
            {
                "success": True,
                "mutation_performed": True,
                "recovery_required": False,
                "recovery_id": "a" * 64,
                "action": "edit_note",
            },
            {
                "success": True,
                "mutation_performed": True,
                "recovery_required": False,
                "recovery_id": "a" * 64,
                "action": "unknown_action",
                "target_relative_path": "notes/a.md",
            },
        )
        for payload in partials:
            with self.subTest(payload=payload):
                [projected] = project_action_evidence(
                    [tool_result(payload)]
                )
                self.assertNotEqual(projected["state"], "succeeded")

    def test_reordered_tool_mapping_still_uses_authoritative_identity(self):
        failure = {
            "success": False,
            "mutation_performed": False,
            "recovery_required": True,
            "recovery_id": "c" * 64,
            "error": "approval_evidence_required",
        }
        messages = [
            {
                "role": "tool",
                "run_id": "run_1",
                "tool_call_id": "call_late_map",
                "content": json.dumps(failure),
            },
            {
                "role": "assistant",
                "run_id": "run_1",
                "tool_calls": [{
                    "id": "call_late_map",
                    "function": {"name": "orion_vault_apply_plan"},
                }],
            },
        ]
        projected = project_action_evidence(
            messages,
            expected_run_id="run_1",
        )
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["state"], "failed")
        self.assertTrue(projected[0]["recovery_required"])

    def test_generic_tool_completed_never_overrides_plugin_failure(self):
        name, lifecycle = project_stream_event(
            "tool.completed",
            {
                "event": "tool.completed",
                "run_id": "run_1",
                "tool_name": "orion_vault_apply_plan",
                "preview": "Tool completed",
                "result": {
                    "success": True,
                    "mutation_performed": True,
                    "secret": "DO-NOT-LEAK",
                },
            },
        )
        self.assertEqual(name, "tool.completed")
        self.assertNotIn("action_evidence", lifecycle)
        self.assertNotIn("result", lifecycle)
        self.assertNotIn("DO-NOT-LEAK", json.dumps(lifecycle))

        name, terminal = project_stream_event(
            "run.completed",
            {
                "event": "run.completed",
                "run_id": "run_1",
                "messages": [tool_result({
                    "success": False,
                    "mutation_performed": False,
                    "recovery_required": True,
                    "recovery_id": "d" * 64,
                    "error": "approval_evidence_required",
                })],
            },
        )
        self.assertEqual(name, "run.completed")
        self.assertEqual(
            terminal["action_evidence"][0]["state"],
            "failed",
        )
        self.assertTrue(
            terminal["action_evidence"][0]["recovery_required"]
        )

    def test_secret_exclusion_applies_to_approval_result_and_run_status(self):
        approval = project_approval_request({
            "event": "approval.request",
            "run_id": "run_1",
            "command": "orion_vault_apply_plan",
            "description": "Target: C:/vault/note.md\n--- old\n+++ new",
            "choices": ["once", "deny"],
            "pattern_key": "plugin_rule:DO-NOT-LEAK",
            "rule_key": "DO-NOT-LEAK",
            "args": {"new_content": "DO-NOT-LEAK"},
            "api_key": "DO-NOT-LEAK",
        })
        action = project_action_evidence([tool_result({
            "success": True,
            "mutation_performed": True,
            "recovery_required": False,
            "recovery_id": "e" * 64,
            "action": "edit_note",
            "target_relative_path": "note.md",
            "recovery_dir": "C:/private/DO-NOT-LEAK",
            "api_key": "DO-NOT-LEAK",
        })])
        status = project_run_status({
            "run_id": "run_1",
            "status": "failed",
            "error": "stack bearer DO-NOT-LEAK",
            "private": {"token": "DO-NOT-LEAK"},
        })

        serialized = json.dumps({
            "approval": approval,
            "action": action,
            "status": status,
        })
        self.assertNotIn("DO-NOT-LEAK", serialized)
        self.assertNotIn("pattern_key", serialized)
        self.assertNotIn("recovery_dir", serialized)

    def test_terminal_run_filters_reordered_foreign_run_evidence(self):
        success = {
            "success": True,
            "mutation_performed": True,
            "recovery_required": False,
            "recovery_id": "f" * 64,
            "action": "edit_note",
            "target_relative_path": "note.md",
        }
        name, projected = project_stream_event(
            "run.completed",
            {
                "event": "run.completed",
                "run_id": "run_A",
                "messages": [
                    tool_result(success, run_id="run_B"),
                    tool_result({
                        "success": False,
                        "mutation_performed": False,
                        "recovery_required": False,
                        "error": "stale_original_hash",
                    }, run_id="run_A"),
                ],
            },
        )
        self.assertEqual(name, "run.completed")
        self.assertEqual(len(projected["action_evidence"]), 1)
        self.assertEqual(
            projected["action_evidence"][0]["state"],
            "stale_plan",
        )
        self.assertEqual(
            projected["action_evidence"][0]["run_id"],
            "run_A",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
