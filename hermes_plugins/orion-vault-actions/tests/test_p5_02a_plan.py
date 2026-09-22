"""Source-only approval-plan regression tests using disposable roots."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("orion_vault_actions_p502a", PLUGIN_DIR / "__init__.py")
plugin = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = plugin
SPEC.loader.exec_module(plugin)


class PlanBindingTests(unittest.TestCase):
    def setUp(self):
        plugin._PREVIEWS.clear()
        plugin._PREVIEW_TIMES.clear()
        plugin._APPROVAL_ATTEMPTS.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.inbox = self.root / "inbox"
        self.vault.mkdir()
        self.inbox.mkdir()
        self.old_vault = os.environ.get("ORION_VAULT_ROOT")
        self.old_inbox = os.environ.get("ORION_INBOX_ROOT")
        os.environ["ORION_VAULT_ROOT"] = str(self.vault)
        os.environ["ORION_INBOX_ROOT"] = str(self.inbox)

    def tearDown(self):
        for key, previous in (("ORION_VAULT_ROOT", self.old_vault),
                              ("ORION_INBOX_ROOT", self.old_inbox)):
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        self.tmp.cleanup()

    def test_identical_edits_get_fresh_rule_keys_and_exact_diff(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old")
        params = {"target_relative_path": "note.md", "new_content": "new"}
        first = json.loads(plugin.preview_edit(params))
        second = json.loads(plugin.preview_edit(params))

        self.assertNotEqual(first["plan_token"], second["plan_token"])
        self.assertNotEqual(first["plan"]["preview_nonce"], second["plan"]["preview_nonce"])
        self.assertEqual(plugin._PREVIEWS[first["plan_token"]]["_proposed_bytes"], b"new")
        self.assertEqual(plugin._PREVIEWS[second["plan_token"]]["_approval_diff"], second["diff"])

        approvals = [plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": item["plan_token"]})
                     for item in (first, second)]
        for item, approval in zip((first, second), approvals):
            self.assertEqual(approval["action"], "approve")
            self.assertIn(item["plan"]["target_canonical_path"], approval["message"])
            self.assertIn(item["diff"], approval["message"])
        self.assertNotEqual(approvals[0]["rule_key"], approvals[1]["rule_key"])
        self.assertEqual(note.read_bytes(), b"old")
        self.assertFalse(json.loads(plugin.apply_plan_placeholder(
            {"plan_token": first["plan_token"]}))["mutation_performed"])

    def test_response_observer_is_registered_without_a_mutating_handler(self):
        class Context:
            def __init__(self):
                self.tools = {}
                self.hooks = {}

            def register_tool(self, *, name, handler, **_kwargs):
                self.tools[name] = handler

            def register_hook(self, name, callback):
                self.hooks[name] = callback

        ctx = Context()
        plugin.register(ctx)
        self.assertEqual(set(ctx.hooks), {"pre_tool_call", "post_approval_response"})
        self.assertIs(ctx.tools[plugin.APPLY_TOOL], plugin.apply_plan_placeholder)

    def test_move_approval_shows_canonical_target_and_bound_source_bytes(self):
        draft = self.inbox / "draft.md"
        draft_bytes = b"---\r\norion_draft: true\r\nstatus: draft\r\n---\r\nbody"
        draft.write_bytes(draft_bytes)
        target = self.vault / "New" / "draft.md"
        preview = json.loads(plugin.preview_move_draft({
            "source_draft": "draft.md", "target_relative_path": "New/draft.md",
        }))
        directive = plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": preview["plan_token"]})
        self.assertEqual(directive["action"], "approve")
        self.assertEqual(preview["plan"]["target_canonical_path"], str(target.resolve(strict=False)))
        self.assertIn(preview["plan"]["target_canonical_path"], directive["message"])
        self.assertIn(preview["diff"], directive["message"])
        self.assertEqual(plugin._PREVIEWS[preview["plan_token"]]["_proposed_bytes"], draft_bytes)
        self.assertEqual(draft.read_bytes(), draft_bytes)
        self.assertFalse(target.exists())

    def test_missing_diff_and_hook_exception_block_without_mutation(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "new\n",
        }))
        token = preview["plan_token"]
        plugin._PREVIEWS[token].pop("_approval_diff")
        self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        plugin._PREVIEWS[token]["_approval_diff"] = preview["diff"] + "unexpected"
        self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        plugin._PREVIEWS[token]["_approval_diff"] = preview["diff"]
        plugin._PREVIEWS[token]["_proposed_bytes"] = b"different\n"
        self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        with patch.object(plugin, "_lookup_preview", side_effect=RuntimeError("cache unavailable")):
            self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        self.assertEqual(note.read_bytes(), b"old\n")

    def test_oversized_approval_payload_blocks_and_apply_still_refuses(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old\n")
        preview = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "x" * 17000,
        }))
        token = preview["plan_token"]
        self.assertEqual(plugin.pre_tool_call(plugin.APPLY_TOOL, {"plan_token": token})["action"], "block")
        result = json.loads(plugin.apply_plan_placeholder({"plan_token": token}))
        self.assertEqual(result["error"], "p5_01_mutation_not_authorized")
        self.assertEqual(note.read_bytes(), b"old\n")

    def test_internal_attempt_requires_matching_once_and_gate_result(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old\n")
        token = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "new\n",
        }))["plan_token"]

        def gate_with(choice, approved=True, *, mismatch=False):
            def request(tool_name, description, *, rule_key):
                self.assertEqual(tool_name, plugin.APPLY_TOOL)
                plugin.post_approval_response(
                    pattern_key=f"plugin_rule:{rule_key}",
                    description=description + ("x" if mismatch else ""),
                    choice=choice,
                    surface="cli",
                )
                return {"approved": approved}
            return request

        self.assertTrue(plugin._probe_fresh_once_approval(
            token, approval_request=gate_with("once"), redact=lambda text: text,
        ))
        for request in (gate_with("session"), gate_with("always"),
                        gate_with("once", approved=False), gate_with("once", mismatch=True),
                        lambda *_args, **_kw: {"approved": True}):
            self.assertFalse(plugin._probe_fresh_once_approval(
                token, approval_request=request, redact=lambda text: text,
            ))
        self.assertFalse(plugin._APPROVAL_ATTEMPTS)
        self.assertEqual(note.read_bytes(), b"old\n")

    def test_structured_once_evidence_is_non_reusable_and_exactly_bound(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old\n")
        token = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "new\n",
        }))["plan_token"]

        def gate(_tool_name, description, *, rule_key):
            plugin.post_approval_response(
                pattern_key=f"plugin_rule:{rule_key}",
                description=description,
                choice="once",
                surface="gateway",
            )
            return {"approved": True}

        evidence = plugin._fresh_once_approval_evidence(
            token, approval_request=gate, redact=lambda text: text,
        )

        self.assertTrue(evidence["approved"])
        self.assertFalse(evidence["authorization_reusable"])
        self.assertEqual(evidence["plan_token"], token)
        self.assertEqual(evidence["choice"], "once")
        self.assertEqual(evidence["surface"], "gateway")
        self.assertRegex(evidence["attempt_id"], r"^[0-9a-f]{32}$")
        self.assertRegex(
            evidence["approval_message_sha256"], r"^[0-9a-f]{64}$"
        )
        self.assertIn("Exact unified diff:", evidence["approval_message"])
        self.assertEqual(
            plugin._sha_text(evidence["approval_message"]),
            evidence["approval_message_sha256"],
        )
        self.assertNotIn("rule_key", evidence)
        self.assertNotIn("pattern_key", evidence)
        self.assertFalse(plugin._APPROVAL_ATTEMPTS)
        self.assertEqual(note.read_bytes(), b"old\n")

    def test_concurrent_attempts_are_isolated_and_late_callback_is_ignored(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old\n")
        token = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "new\n",
        }))["plan_token"]

        first_entered = threading.Event()
        release_first = threading.Event()
        first_details = {}
        outcomes = {}

        def first_gate(_tool_name, description, *, rule_key):
            first_details["description"] = description
            first_details["pattern_key"] = f"plugin_rule:{rule_key}"
            first_entered.set()
            self.assertTrue(release_first.wait(2.0))
            return {"approved": True}

        def run_first():
            outcomes["first"] = plugin._probe_fresh_once_approval(
                token, approval_request=first_gate, redact=lambda text: text,
            )

        worker = threading.Thread(target=run_first)
        worker.start()
        self.assertTrue(first_entered.wait(2.0))

        def second_gate(_tool_name, description, *, rule_key):
            second_key = f"plugin_rule:{rule_key}"
            self.assertNotEqual(second_key, first_details["pattern_key"])
            plugin.post_approval_response(
                pattern_key=second_key,
                description=description,
                choice="once",
                surface="gateway",
            )
            return {"approved": True}

        self.assertTrue(plugin._probe_fresh_once_approval(
            token, approval_request=second_gate, redact=lambda text: text,
        ))

        # A response for a different key cannot authorize the still-pending
        # first attempt even when its description is otherwise identical.
        plugin.post_approval_response(
            pattern_key="plugin_rule:orion_vault_attempt:wrong",
            description=first_details["description"],
            choice="once",
            surface="gateway",
        )
        release_first.set()
        worker.join(2.0)
        self.assertFalse(worker.is_alive())
        self.assertFalse(outcomes["first"])

        # Once the first attempt has been removed, a late matching callback is
        # inert and cannot resurrect authorization.
        plugin.post_approval_response(
            pattern_key=first_details["pattern_key"],
            description=first_details["description"],
            choice="once",
            surface="gateway",
        )
        self.assertFalse(plugin._APPROVAL_ATTEMPTS)
        self.assertEqual(note.read_bytes(), b"old\n")

    def test_attempt_limit_fails_closed_before_requesting_approval(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old\n")
        token = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "new\n",
        }))["plan_token"]
        for index in range(plugin.APPROVAL_ATTEMPT_LIMIT):
            plugin._APPROVAL_ATTEMPTS[f"held-{index}"] = {
                "description": "held", "created": 0.0, "once": False,
            }

        called = False

        def should_not_run(*_args, **_kwargs):
            nonlocal called
            called = True
            return {"approved": True}

        self.assertFalse(plugin._probe_fresh_once_approval(
            token, approval_request=should_not_run, redact=lambda text: text,
        ))
        self.assertFalse(called)
        self.assertEqual(note.read_bytes(), b"old\n")

    def test_internal_attempt_fails_closed_on_redaction_and_gate_error(self):
        note = self.vault / "note.md"
        note.write_bytes(b"old\n")
        token = json.loads(plugin.preview_edit({
            "target_relative_path": "note.md", "new_content": "new\n",
        }))["plan_token"]
        self.assertFalse(plugin._probe_fresh_once_approval(
            token, approval_request=lambda *_args, **_kw: {"approved": True},
            redact=lambda text: text.replace("new", "[REDACTED]"),
        ))
        def fail(*_args, **_kw):
            raise RuntimeError("approval unavailable")
        self.assertFalse(plugin._probe_fresh_once_approval(
            token, approval_request=fail, redact=lambda text: text,
        ))
        self.assertFalse(plugin._APPROVAL_ATTEMPTS)
        self.assertEqual(note.read_bytes(), b"old\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
