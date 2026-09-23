#!/usr/bin/env python3
"""P5-02P deterministic registered-dispatch approval probe.

This is a NON-PRODUCTION proof. It exercises Hermes's real
model_tools.handle_function_call() -> pre_tool_call -> registry.dispatch path
for the installed orion_vault_apply_plan tool, but replaces the plugin's
private production executor in-memory with an approval-only probe.

The probe uses disposable temporary vault/inbox/recovery roots and never calls
the real production executor. A human should choose ONCE at the Hermes prompt.
Any other choice fails closed and still performs no protected filesystem
mutation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


APPLY_TOOL = "orion_vault_apply_plan"
PREVIEW_TOOL = "orion_vault_preview_edit"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()

    profile = args.profile.resolve(strict=True)

    for name in (
        "ORION_P5_PRODUCTION_RECOVERY_ROOT",
        "ORION_P5_MUTATION_MODE",
        "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
        "ORION_P5_RECOVERY_ROOT",
    ):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"ambient Phase 5 setting unexpectedly present: {name}")

    os.environ["HERMES_HOME"] = str(profile)

    from hermes_cli.plugins import discover_plugins
    from model_tools import handle_function_call
    from tools.approval import (
        reset_hermes_interactive_context,
        set_hermes_interactive_context,
    )
    from tools.registry import registry

    discover_plugins()

    apply_entry = registry.get_entry(APPLY_TOOL)
    preview_entry = registry.get_entry(PREVIEW_TOOL)
    if apply_entry is None or preview_entry is None:
        raise RuntimeError("installed Orion vault tools were not discovered")
    if apply_entry.handler.__name__ != "apply_plan_production_guarded":
        raise RuntimeError(
            "registered apply handler is not apply_plan_production_guarded"
        )

    plugin = sys.modules.get(apply_entry.handler.__module__)
    if plugin is None:
        raise RuntimeError("installed Orion plugin module is unavailable")
    if apply_entry.handler is not plugin.apply_plan_production_guarded:
        raise RuntimeError("registry handler identity mismatch")
    if registry.get_entry(APPLY_TOOL).handler is plugin._execute_production_plan_candidate:
        raise RuntimeError("private production executor unexpectedly registered")

    original_executor = plugin._execute_production_plan_candidate
    original_env = {
        name: os.environ.get(name)
        for name in (
            "ORION_VAULT_ROOT",
            "ORION_INBOX_ROOT",
            "ORION_P5_PRODUCTION_RECOVERY_ROOT",
            "ORION_P5_MUTATION_MODE",
        )
    }
    interactive_token = None
    probe_executor_calls = 0

    try:
        with tempfile.TemporaryDirectory(prefix="orion-p5-02p-dispatch-") as td:
            root = Path(td)
            vault = root / "vault"
            inbox = root / "inbox"
            recovery = root / "recovery"
            vault.mkdir()
            inbox.mkdir()
            recovery.mkdir()
            note = vault / "probe.md"
            before = b"dispatch-probe-before\n"
            note.write_bytes(before)

            os.environ["ORION_VAULT_ROOT"] = str(vault)
            os.environ["ORION_INBOX_ROOT"] = str(inbox)
            os.environ["ORION_P5_PRODUCTION_RECOVERY_ROOT"] = str(recovery)
            os.environ["ORION_P5_MUTATION_MODE"] = "mutation_enabled"

            preview = json.loads(
                plugin.preview_edit(
                    {
                        "target_relative_path": "probe.md",
                        "new_content": "dispatch-probe-after\n",
                    }
                )
            )
            if preview.get("success") is not True:
                raise RuntimeError("disposable approval-probe preview failed")
            token = preview["plan_token"]

            def approval_only_executor(plan_token: str, **kwargs):
                nonlocal probe_executor_calls
                probe_executor_calls += 1
                if kwargs:
                    raise RuntimeError(
                        "public wrapper forwarded unexpected private kwargs"
                    )
                if plan_token != token:
                    raise RuntimeError("public wrapper delegated wrong plan token")
                evidence = plugin._fresh_once_approval_evidence(plan_token)
                if evidence.get("approved") is not True:
                    return plugin._candidate_result(
                        success=False,
                        error=evidence.get("error", "approval_probe_failed"),
                        mutation_performed=False,
                        recovery_required=False,
                        probe_only=True,
                    )
                return plugin._candidate_result(
                    success=True,
                    mutation_performed=False,
                    recovery_required=False,
                    probe_only=True,
                    approval_choice=evidence.get("choice"),
                    approval_surface=evidence.get("surface"),
                    authorization_reusable=evidence.get("authorization_reusable"),
                )

            plugin._execute_production_plan_candidate = approval_only_executor
            interactive_token = set_hermes_interactive_context(True)

            print("P5_02P_DISPATCH_PROBE_PROMPT_EXPECTED=true")
            print("P5_02P_DISPATCH_PROBE_CHOOSE_ONCE_ONLY=true", flush=True)

            raw_result = handle_function_call(
                APPLY_TOOL,
                {"plan_token": token},
                task_id="p5-02p-dispatch-probe",
                session_id="p5-02p-dispatch-probe",
                tool_call_id="p5-02p-dispatch-probe-call",
                turn_id="p5-02p-dispatch-probe-turn",
                user_task="P5-02P deterministic approval-only dispatch probe",
                enabled_tools=[APPLY_TOOL],
                enabled_toolsets=["orion_vault"],
            )

            try:
                result = json.loads(raw_result)
            except Exception as exc:
                raise RuntimeError(
                    f"registered dispatch returned non-JSON result: {raw_result!r}"
                ) from exc

            if result.get("success") is not True:
                raise RuntimeError(
                    "fresh human ONCE was not observed by the registered path: "
                    + json.dumps(result, sort_keys=True)
                )
            if result.get("probe_only") is not True:
                raise RuntimeError("approval-only executor result marker missing")
            if result.get("mutation_performed") is not False:
                raise RuntimeError("approval-only probe reported mutation")
            if result.get("approval_choice") != "once":
                raise RuntimeError("approval-only probe did not observe choice=once")
            if result.get("approval_surface") != "cli":
                raise RuntimeError("approval-only probe did not use CLI surface")
            if result.get("authorization_reusable") is not False:
                raise RuntimeError("approval evidence unexpectedly reusable")
            if probe_executor_calls != 1:
                raise RuntimeError(
                    f"expected one private probe delegation, got {probe_executor_calls}"
                )
            if note.read_bytes() != before:
                raise RuntimeError("disposable note changed during approval-only probe")
            if list(recovery.iterdir()):
                raise RuntimeError("approval-only probe created recovery content")

            print("P5_02P_DETERMINISTIC_REGISTERED_DISPATCH=PASS")
            print("P5_02P_REGISTERED_HANDLER=apply_plan_production_guarded")
            print("P5_02P_PRE_TOOL_CALL_PATH_EXERCISED=true")
            print("P5_02P_PRIVATE_PRODUCTION_EXECUTOR_CALLED=false")
            print("P5_02P_APPROVAL_ONLY_PROBE_DELEGATIONS=1")
            print("P5_02P_FRESH_HUMAN_ONCE_OBSERVED=true")
            print("P5_02P_APPROVAL_SURFACE=cli")
            print("P5_02P_AUTHORIZATION_REUSABLE=false")
            print("P5_02P_PRODUCTION_FILESYSTEM_MUTATION=false")
            print("P5_02P_DISPOSABLE_NOTE_UNCHANGED=true")
            print("P5_02P_DISPOSABLE_RECOVERY_EMPTY=true")
            return 0

    finally:
        plugin._execute_production_plan_candidate = original_executor
        if interactive_token is not None:
            reset_hermes_interactive_context(interactive_token)
        for name, old in original_env.items():
            if old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02P_DETERMINISTIC_REGISTERED_DISPATCH=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
