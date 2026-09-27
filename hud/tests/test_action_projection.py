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
    def test_stream_event_rejects_explicit_wrong_session(self):
        for session_id in ("session_B", " session_A ", 7):
            with self.subTest(session_id=session_id):
                self.assertIsNone(
                    project_stream_event(
                        "run.started",
                        {
                            "event": "run.started",
                            "run_id": "run_1",
                            "session_id": session_id,
                        },
                        expected_session_id="session_A",
                    )
                )

        projected = project_stream_event(
            "run.started",
            {
                "event": "run.started",
                "run_id": "run_1",
                "session_id": "session_A",
            },
            expected_session_id="session_A",
        )
        self.assertIsNotNone(projected)

        omitted = project_stream_event(
            "assistant.delta",
            {
                "event": "assistant.delta",
                "delta": "ok",
            },
            expected_session_id="session_A",
        )
        self.assertIsNotNone(omitted)

    def test_run_started_requires_raw_exact_run_id(self):
        for bad_run_id in (" run_1 ", 7, {"id": "run_1"}, ""):
            with self.subTest(run_id=bad_run_id):
                self.assertIsNone(
                    project_stream_event(
                        "run.started",
                        {
                            "event": "run.started",
                            "run_id": bad_run_id,
                        },
                    )
                )

        projected = project_stream_event(
            "run.started",
            {
                "event": "run.started",
                "run_id": "run_1",
                "session_id": "session_1",
            },
        )
        self.assertIsNotNone(projected)
        name, payload = projected
        self.assertEqual(name, "run.started")
        self.assertEqual(payload["run_id"], "run_1")

    def test_terminal_action_evidence_is_bound_to_terminal_run(self):
        result = {
            "success": True,
            "mutation_performed": True,
            "recovery_required": False,
            "recovery_id": "a" * 64,
            "action": "edit_note",
            "target_relative_path": "note.md",
        }
        projected = project_stream_event(
            "run.completed",
            {
                "event": "run.completed",
                "run_id": "run_A",
                "messages": [
                    {
                        "role": "tool",
                        "run_id": "run_B",
                        "tool_name": "orion_vault_apply_plan",
                        "content": json.dumps(result),
                    },
                    {
                        "role": "tool",
                        "run_id": "run_A",
                        "tool_name": "orion_vault_apply_plan",
                        "content": json.dumps(result),
                    },
                ],
            },
        )
        self.assertIsNotNone(projected)
        _, payload = projected
        self.assertEqual(len(payload["action_evidence"]), 1)
        self.assertEqual(
            payload["action_evidence"][0]["run_id"], "run_A"
        )

    def test_terminal_stream_events_require_raw_exact_run_id(self):
        for event_name in ("run.completed", "run.cancelled", "run.failed"):
            for bad_run_id in (" run_1 ", 7, {"id": "run_1"}, ""):
                with self.subTest(event=event_name, run_id=bad_run_id):
                    self.assertIsNone(
                        project_stream_event(
                            event_name,
                            {
                                "event": event_name,
                                "run_id": bad_run_id,
                                "messages": [],
                            },
                        )
                    )

        for bad_run_id in (" run_1 ", 7):
            with self.subTest(event="error", run_id=bad_run_id):
                self.assertIsNone(
                    project_stream_event(
                        "error",
                        {"event": "error", "run_id": bad_run_id},
                    )
                )

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

    def test_approval_command_must_survive_exact_validation(self):
        base = {
            "run_id": "run_1",
            "description": "exact approval content",
            "choices": ["once", "deny"],
        }
        for command in (
            " leading",
            "trailing ",
            "nul\x00command",
            "x" * 241,
            {},
            7,
        ):
            with self.subTest(command=repr(command)):
                projected = project_approval_request({
                    **base,
                    "command": command,
                    "tool_name": "orion_vault_apply_plan",
                })
                self.assertEqual(
                    projected["projection"]["state"],
                    "unavailable",
                )
                self.assertEqual(projected["choices"], [])

        legacy = project_approval_request({
            **base,
            "tool_name": "orion_vault_apply_plan",
        })
        self.assertEqual(
            legacy["projection"]["state"],
            "approval_requested",
        )

    def test_blank_approval_description_withholds_choices(self):
        for description in ("", " ", "\t\r\n"):
            with self.subTest(description=repr(description)):
                projected = project_approval_request({
                    "run_id": "run_1",
                    "command": "orion_vault_apply_plan",
                    "description": description,
                    "choices": ["once", "deny"],
                })
                self.assertEqual(
                    projected["projection"]["state"],
                    "unavailable",
                )
                self.assertEqual(projected["choices"], [])

    def test_incomplete_approval_content_withholds_choices(self):
        projected = project_approval_request({
            "run_id": "run_1",
            "command": "orion_vault_apply_plan",
            "choices": ["once", "deny"],
        })
        self.assertEqual(projected["choices"], [])
        self.assertEqual(projected["projection"]["state"], "unavailable")

        missing_run = project_approval_request({
            "command": "orion_vault_apply_plan",
            "description": "exact approval content",
            "choices": ["once", "deny"],
        })
        self.assertEqual(missing_run["choices"], [])
        self.assertEqual(
            missing_run["projection"]["state"], "unavailable"
        )
        self.assertEqual(
            missing_run["projection"]["reason"],
            "approval_run_id_unavailable",
        )

        for bad_run_id in (" run_1 ", 7, {"id": "run_1"}):
            with self.subTest(run_id=bad_run_id):
                projected = project_approval_request({
                    "run_id": bad_run_id,
                    "command": "orion_vault_apply_plan",
                    "description": "exact approval content",
                    "choices": ["once", "deny"],
                })
                self.assertEqual(projected["choices"], [])
                self.assertNotIn("run_id", projected)
                self.assertEqual(
                    projected["projection"]["state"],
                    "unavailable",
                )

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
                "object": "hermes.run.approval_response",
                "run_id": " run_1 ",
                "choice": "once",
                "resolved": 1,
            },
            {
                "object": "hermes.run.approval_response",
                "run_id": "run_1",
                "choice": " ONCE ",
                "resolved": 1,
            },
            {
                "object": "hermes.run.approval_response",
                "run_id": "run_1",
                "choice": "ONCE",
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

    def test_protected_tool_identity_must_be_raw_exact(self):
        success = {
            "success": True,
            "mutation_performed": True,
            "recovery_required": False,
            "recovery_id": "a" * 64,
            "action": "edit_note",
            "target_relative_path": "note.md",
        }
        for bad_name in (
            " orion_vault_apply_plan ",
            "orion_vault_apply_plan\x00",
            7,
        ):
            with self.subTest(tool_name=bad_name):
                items = project_action_evidence([{
                    "role": "tool",
                    "tool_name": bad_name,
                    "content": json.dumps(success),
                }])
                self.assertEqual(items, [])

        mapped = project_action_evidence([
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": " call_1 ",
                    "function": {"name": "orion_vault_apply_plan"},
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": json.dumps(success),
            },
        ])
        self.assertEqual(mapped, [])

        mapped = project_action_evidence([
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": " orion_vault_apply_plan "},
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": json.dumps(success),
            },
        ])
        self.assertEqual(mapped, [])

        for tool_name, name in (
            ("orion_vault_apply_plan", "other_tool"),
            ("orion_vault_apply_plan", " orion_vault_apply_plan "),
            (" orion_vault_apply_plan ", "orion_vault_apply_plan"),
        ):
            with self.subTest(tool_name=tool_name, name=name):
                items = project_action_evidence([{
                    "role": "tool",
                    "tool_name": tool_name,
                    "name": name,
                    "content": json.dumps(success),
                }])
                self.assertEqual(items, [])

        matching = project_action_evidence([{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "name": "orion_vault_apply_plan",
            "content": json.dumps(success),
        }])
        self.assertEqual(matching[0]["state"], "succeeded")

        conflicting_map = project_action_evidence([
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "other_tool"},
                }],
            },
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "orion_vault_apply_plan"},
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": json.dumps(success),
            },
        ])
        self.assertEqual(conflicting_map, [])

        duplicate_same = project_action_evidence([
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "orion_vault_apply_plan"},
                }],
            },
            {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "orion_vault_apply_plan"},
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": json.dumps(success),
            },
        ])
        self.assertEqual(duplicate_same[0]["state"], "succeeded")

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

        for raw_error in (
            "preview_contract_error",
            "preview contract error",
            {"code": "preview_contract_error"},
            7,
        ):
            contradictory = {
                "role": "tool",
                "tool_name": "orion_vault_preview_edit",
                "content": json.dumps({
                    "success": True,
                    "mode": "preview",
                    "mutation_performed": False,
                    "plan_token": "a" * 64,
                    "plan": plan,
                    "diff": diff,
                    "error": raw_error,
                }),
            }
            [projected] = project_action_evidence([contradictory])
            self.assertEqual(projected["state"], "failed")
            self.assertNotEqual(projected["state"], "preview_ready")


        for recovery_value in (True, "true", {"required": True}, 1):
            contradictory = {
                "role": "tool",
                "tool_name": "orion_vault_preview_edit",
                "content": json.dumps({
                    "success": True,
                    "mode": "preview",
                    "mutation_performed": False,
                    "plan_token": "a" * 64,
                    "plan": plan,
                    "diff": diff,
                    "recovery_required": recovery_value,
                }),
            }
            [projected] = project_action_evidence([contradictory])
            self.assertEqual(projected["state"], "unavailable")
            self.assertEqual(
                projected["reason"], "preview_recovery_conflict"
            )


        for bad_target in (
            " note.md",
            "note.md ",
            "note\x00.md",
            "x" * 1025,
        ):
            bad_plan = dict(plan)
            bad_plan["target_relative_path"] = bad_target
            contradictory = {
                "role": "tool",
                "tool_name": "orion_vault_preview_edit",
                "content": json.dumps({
                    "success": True,
                    "mode": "preview",
                    "mutation_performed": False,
                    "plan_token": "a" * 64,
                    "plan": bad_plan,
                    "diff": diff,
                }),
            }
            [projected] = project_action_evidence([contradictory])
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

        missing_recovery_flag = dict(base)
        missing_recovery_flag.pop("recovery_required")
        [missing_flag] = project_action_evidence([{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "content": json.dumps(missing_recovery_flag),
        }])
        self.assertEqual(missing_flag["state"], "unknown")
        self.assertEqual(
            missing_flag["reason"], "success_evidence_incomplete"
        )
        self.assertNotIn("recovery_required", missing_flag)

        contradictory = dict(base, error="post_write_hash_mismatch")
        [conflict] = project_action_evidence([{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "content": json.dumps(contradictory),
        }])
        self.assertEqual(conflict["state"], "unknown")
        self.assertEqual(conflict["reason"], "conflicting_action_result")


        for field, bad_value in (
            ("action", " edit_note "),
            ("target_relative_path", " note.md"),
            ("target_relative_path", "note.md "),
            ("target_relative_path", "note\x00.md"),
            ("target_relative_path", "x" * 1025),
        ):
            malformed = dict(base)
            malformed[field] = bad_value
            [projected] = project_action_evidence([{
                "role": "tool",
                "tool_name": "orion_vault_apply_plan",
                "content": json.dumps(malformed),
            }])
            self.assertEqual(projected["state"], "unknown")
            self.assertEqual(
                projected["reason"], "success_evidence_incomplete"
            )

        restore_cases = (
            (
                {
                    "success": True,
                    "mutation_performed": True,
                    "recovery_required": False,
                    "recovery_id": "a" * 64,
                    "origin_recovery_id": "b" * 64,
                    "action": "restore_edit",
                },
                "target_relative_path",
                "note.md",
            ),
            (
                {
                    "success": True,
                    "mutation_performed": True,
                    "recovery_required": False,
                    "recovery_id": "a" * 64,
                    "origin_recovery_id": "b" * 64,
                    "action": "restore_move_source",
                },
                "source_draft",
                "drafts/note.md",
            ),
        )
        for payload, required_field, required_value in restore_cases:
            with self.subTest(action=payload["action"]):
                [missing] = project_action_evidence([{
                    "role": "tool",
                    "tool_name": "orion_vault_apply_plan",
                    "content": json.dumps(payload),
                }])
                self.assertEqual(missing["state"], "unknown")
                completed = dict(payload, **{required_field: required_value})
                [complete_restore] = project_action_evidence([{
                    "role": "tool",
                    "tool_name": "orion_vault_apply_plan",
                    "content": json.dumps(completed),
                }])
                self.assertEqual(complete_restore["state"], "succeeded")

    def test_recovery_required_has_failure_precedence(self):
        for payload in (
            {
                "success": True,
                "mutation_performed": True,
                "recovery_required": True,
                "recovery_id": "a" * 64,
                "action": "edit_note",
                "target_relative_path": "note.md",
            },
            {
                "success": False,
                "mutation_performed": False,
                "recovery_required": True,
                "error": "approval_evidence_required",
                "recovery_id": "a" * 64,
            },
        ):
            with self.subTest(payload=payload):
                [projected] = project_action_evidence([{
                    "role": "tool",
                    "tool_name": "orion_vault_apply_plan",
                    "content": json.dumps(payload),
                }])
                self.assertEqual(projected["state"], "failed")
                self.assertTrue(projected["recovery_required"])
                self.assertEqual(
                    projected["reason"], "recovery_required"
                )

    def test_recovery_required_refusal_is_failure_not_refused(self):
        [projected] = project_action_evidence([{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "content": json.dumps({
                "success": False,
                "error": "approval_evidence_required",
                "mutation_performed": False,
                "recovery_required": True,
                "recovery_id": "a" * 64,
            }),
        }])
        self.assertEqual(projected["state"], "failed")
        self.assertTrue(projected["recovery_required"])

        [missing_recovery] = project_action_evidence([{
            "role": "tool",
            "tool_name": "orion_vault_apply_plan",
            "content": json.dumps({
                "success": False,
                "error": "approval_evidence_required",
                "mutation_performed": False,
            }),
        }])
        self.assertEqual(missing_recovery["state"], "failed")

    def test_hydrated_evidence_is_bound_to_requested_session(self):
        result = {
            "success": True,
            "mutation_performed": True,
            "recovery_required": False,
            "recovery_id": "a" * 64,
            "action": "edit_note",
            "target_relative_path": "note.md",
        }
        projected = project_action_evidence_payload(
            {
                "data": [
                    {
                        "role": "tool",
                        "session_id": "session_B",
                        "tool_name": "orion_vault_apply_plan",
                        "content": json.dumps(result),
                    },
                    {
                        "role": "tool",
                        "session_id": "session_A",
                        "tool_name": "orion_vault_apply_plan",
                        "content": json.dumps(result),
                    },
                ]
            },
            session_id="session_A",
        )
        self.assertEqual(len(projected["items"]), 1)
        self.assertEqual(
            projected["items"][0]["session_id"], "session_A"
        )

        malformed = project_action_evidence_payload(
            {
                "data": [{
                    "role": "tool",
                    "session_id": " session_A ",
                    "tool_name": "orion_vault_apply_plan",
                    "content": json.dumps(result),
                }]
            },
            session_id="session_A",
        )
        self.assertEqual(malformed["items"], [])

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
