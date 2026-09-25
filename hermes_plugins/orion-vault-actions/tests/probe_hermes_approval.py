"""Isolated approval-gate probe for the installed Hermes Python environment.

Run explicitly with Hermes's venv Python. It patches the prompt and lifecycle
observer in process, makes no real approval request, and never reads a vault.
This proves only the gate/hook signal shape, not full plugin dispatch or UI.
"""

from __future__ import annotations

import secrets
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from hermes_cli import lifecycle
from tools import approval


class ApprovalSignalProbe(unittest.TestCase):
    def _attempt(
        self,
        choice: str,
        *,
        yolo: bool = False,
        cached: bool = False,
        observer_fails: bool = False,
        cron_auto: bool = False,
        single_query_auto: bool = False,
    ) -> tuple[bool, bool]:
        # A fresh internal key on every invocation prevents a previous grant
        # or late observer event from satisfying this attempt's receipt.
        key = "orion_probe:" + secrets.token_hex(16)
        pattern_key = "plugin_rule:" + key
        description = "Orion disposable approval probe (no filesystem action)"
        receipt = []

        def observe(hook_name, **fields):
            if observer_fails:
                raise RuntimeError("simulated observer failure")
            if (
                hook_name == "post_approval_response"
                and fields.get("pattern_key") == pattern_key
                and fields.get("description") == description
                and fields.get("choice") == "once"
                and fields.get("surface") == "cli"
            ):
                receipt.append(True)
            return []

        with ExitStack() as stack:
            patches = [
                patch.object(approval, "_YOLO_MODE_FROZEN", False),
                patch.object(approval, "is_current_session_yolo_enabled", return_value=yolo),
                patch.object(approval, "is_approved", return_value=cached),
                patch.object(approval, "get_current_session_key", return_value="orion-probe"),
                patch.object(approval, "_is_interactive_cli", return_value=not cron_auto),
                patch.object(approval, "_is_gateway_approval_context", return_value=False),
                patch.object(approval, "_is_cron_approval_context", return_value=cron_auto),
                patch.object(approval, "_get_cron_approval_mode", return_value="approve"),
                patch.object(approval, "_is_single_query_approval_context", return_value=single_query_auto),
                patch.object(approval, "_get_single_query_approval_mode", return_value="approve"),
                patch.object(approval, "approve_session"),
                patch.object(approval, "approve_permanent"),
                patch.object(approval, "save_permanent_allowlist"),
                patch.object(lifecycle, "invoke_hook", side_effect=observe),
            ]
            for item in patches:
                stack.enter_context(item)
            result = approval.request_tool_approval(
                "orion_vault_apply_plan", description, rule_key=key,
                approval_callback=lambda *_args, **_kwargs: choice,
            )
        return bool(result.get("approved")), bool(receipt)

    def test_only_fresh_once_emits_acceptable_signal(self):
        self.assertEqual(self._attempt("once"), (True, True))
        for choice, gate_approved in (
            ("session", True), ("always", True),
            ("deny", False), ("timeout", False),
        ):
            with self.subTest(choice=choice):
                self.assertEqual(self._attempt(choice), (gate_approved, False))

    def test_bypass_and_auto_approval_emit_no_fresh_once_signal(self):
        for kwargs in (
            {"yolo": True}, {"cached": True},
            {"cron_auto": True}, {"single_query_auto": True},
        ):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self._attempt("once", **kwargs), (True, False))

    def test_observer_failure_cannot_create_a_receipt(self):
        # Hermes treats observer hooks as best effort. The handler must require
        # BOTH the gate result and its own fresh per-attempt signal.
        self.assertEqual(self._attempt("once", observer_fails=True), (True, False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
