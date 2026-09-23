#!/usr/bin/env python3
"""Read-only native verification for P5-02J production recovery root.

This script imports the already-installed COMPANION Orion plugin, process-scopes
ORION_P5_PRODUCTION_RECOVERY_ROOT to the candidate directory, keeps production
mutation mode absent/disabled, and calls the plugin's native production-root
validator plus bounded recovery inventory.

It does not create, delete, chmod/ACL, write recovery records, or mutate vault
or inbox content.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


EXPECTED_TOOLS = {
    "orion_vault_preview_edit",
    "orion_vault_preview_move_draft",
    "orion_vault_recommend_destination",
    "orion_vault_apply_plan",
}
EXPECTED_HOOKS = {"pre_tool_call", "post_approval_response"}


class Context:
    def __init__(self) -> None:
        self.tools: dict[str, dict] = {}
        self.hooks: dict[str, object] = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def call_mcp(self, *_args, **_kwargs):
        raise RuntimeError("MCP calls are forbidden in P5-02J verification")


def load_installed_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    if not plugin_file.is_file():
        raise RuntimeError(f"installed plugin missing: {plugin_file}")
    spec = importlib.util.spec_from_file_location(
        "orion_p5_02j_installed_verify", plugin_file
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed plugin import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument("recovery_root", type=Path)
    args = parser.parse_args()

    plugin_dir = args.plugin_dir.resolve()
    recovery_root = args.recovery_root.resolve(strict=True)

    if not recovery_root.is_dir():
        raise RuntimeError("candidate recovery root is not a directory")

    for name in (
        "ORION_P5_MUTATION_MODE",
        "ORION_P5_PRODUCTION_RECOVERY_ROOT",
        "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
        "ORION_P5_RECOVERY_ROOT",
    ):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"unexpected pre-existing process setting: {name}")

    plugin = load_installed_plugin(plugin_dir)
    ctx = Context()
    plugin.register(ctx)

    if set(ctx.tools) != EXPECTED_TOOLS:
        raise RuntimeError("installed tool registration mismatch")
    if set(ctx.hooks) != EXPECTED_HOOKS:
        raise RuntimeError("installed hook registration mismatch")
    if ctx.tools[plugin.APPLY_TOOL]["handler"] is not plugin.apply_plan_placeholder:
        raise RuntimeError("registered apply handler is not fail-closed placeholder")
    if plugin._execute_production_plan_candidate in {
        entry["handler"] for entry in ctx.tools.values()
    }:
        raise RuntimeError("private production executor unexpectedly registered")

    old_recovery = os.environ.get(plugin.PRODUCTION_RECOVERY_ROOT_ENV)
    old_mode = os.environ.get(plugin.PRODUCTION_MUTATION_MODE_ENV)
    try:
        os.environ[plugin.PRODUCTION_RECOVERY_ROOT_ENV] = str(recovery_root)
        os.environ.pop(plugin.PRODUCTION_MUTATION_MODE_ENV, None)

        mode = plugin._production_mutation_mode()
        if (
            mode.get("valid") is not True
            or mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED
            or mode.get("mutation_allowed") is not False
        ):
            raise RuntimeError(f"unexpected production mutation mode: {mode}")

        validation = plugin._validate_production_roots()
        if validation.get("success") is not True:
            raise RuntimeError(
                "native production root validation failed: "
                + json.dumps(validation, sort_keys=True)
            )
        if validation.get("mutation_mode") != plugin.PRODUCTION_MODE_DISABLED:
            raise RuntimeError("native validation did not remain disabled")
        if validation.get("mutation_allowed") is not False:
            raise RuntimeError("native validation reported mutation_allowed")
        if Path(validation["recovery_root"]).resolve(strict=True) != recovery_root:
            raise RuntimeError("native validation recovery-root identity mismatch")

        inventory = plugin._enumerate_production_recovery_records()
        if inventory.get("success") is not True:
            raise RuntimeError(
                "native recovery inventory failed: "
                + json.dumps(inventory, sort_keys=True)
            )
        if inventory.get("record_count") != 0:
            raise RuntimeError(
                "production recovery root is not empty: "
                + json.dumps(inventory, sort_keys=True)
            )
        if inventory.get("attention_count") != 0:
            raise RuntimeError("unexpected recovery attention records")
        if inventory.get("truncated") is not False:
            raise RuntimeError("unexpected recovery inventory truncation")
        if inventory.get("mutation_allowed") is not False:
            raise RuntimeError("inventory reported mutation_allowed")

        public_apply = json.loads(
            ctx.tools[plugin.APPLY_TOOL]["handler"]({"plan_token": "0" * 64})
        )
        if (
            public_apply.get("success") is not False
            or public_apply.get("error") != "p5_01_mutation_not_authorized"
            or public_apply.get("mutation_performed") is not False
        ):
            raise RuntimeError("registered apply no longer fails closed")

        print("P5_02J_NATIVE_ROOT_VALIDATION=PASS")
        print("PRODUCTION_MUTATION_MODE=disabled")
        print("PRODUCTION_MUTATION_ALLOWED=false")
        print("P5_02J_RECOVERY_INVENTORY_COUNT=0")
        print("P5_02J_RECOVERY_ATTENTION_COUNT=0")
        print("P5_02J_RECOVERY_INVENTORY_TRUNCATED=false")
        print("P5_02J_REGISTERED_APPLY_FAIL_CLOSED=true")
        print("P5_02J_REAL_VAULT_INBOX_MUTATION=false")
        return 0
    finally:
        if old_recovery is None:
            os.environ.pop(plugin.PRODUCTION_RECOVERY_ROOT_ENV, None)
        else:
            os.environ[plugin.PRODUCTION_RECOVERY_ROOT_ENV] = old_recovery
        if old_mode is None:
            os.environ.pop(plugin.PRODUCTION_MUTATION_MODE_ENV, None)
        else:
            os.environ[plugin.PRODUCTION_MUTATION_MODE_ENV] = old_mode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02J_NATIVE_ROOT_VALIDATION=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
