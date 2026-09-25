#!/usr/bin/env python3
"""P5-02O installed-but-disabled runtime verifier.

Loads the installed Orion vault plugin from the COMPANION profile, verifies the
P5-02N guarded apply registration while production mutation remains disabled,
proves disabled apply/pre-tool behavior cannot enter the private production
executor or create approval-attempt state, validates the persisted production
recovery root, and checks the live authenticated Orion toolset.

The only note content used by this verifier lives under a disposable temporary
directory. It never invokes a mutating production path.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path


EXPECTED_TOOLS = {
    "orion_vault_apply_plan",
    "orion_vault_preview_edit",
    "orion_vault_preview_move_draft",
    "orion_vault_recommend_destination",
}


class Context:
    def __init__(self) -> None:
        self.tools: dict[str, dict] = {}
        self.hooks: dict[str, object] = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def call_mcp(self, *_args, **_kwargs):
        raise RuntimeError("MCP calls are forbidden in P5-02O verification")


def load_installed_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    if not plugin_file.is_file():
        raise RuntimeError(f"installed plugin missing: {plugin_file}")
    spec = importlib.util.spec_from_file_location(
        "orion_p5_02o_runtime_verify", plugin_file
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed plugin import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    parser.add_argument("plugin_dir", type=Path)
    parser.add_argument("expected_recovery_root", type=Path)
    parser.add_argument("--gateway", default="http://127.0.0.1:8642")
    args = parser.parse_args()

    profile = args.profile.resolve(strict=True)
    plugin_dir = args.plugin_dir.resolve(strict=True)
    expected_root = args.expected_recovery_root.resolve(strict=True)

    phase5_names = (
        "ORION_P5_PRODUCTION_RECOVERY_ROOT",
        "ORION_P5_MUTATION_MODE",
        "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
        "ORION_P5_RECOVERY_ROOT",
    )
    for name in phase5_names:
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"ambient process setting unexpectedly present: {name}")

    os.environ["HERMES_HOME"] = str(profile)
    from hermes_cli.env_loader import load_hermes_dotenv

    loaded = load_hermes_dotenv(hermes_home=profile)
    if profile / ".env" not in [Path(p).resolve() for p in loaded]:
        raise RuntimeError("Hermes loader did not report COMPANION .env as loaded")

    effective_root = (os.environ.get("ORION_P5_PRODUCTION_RECOVERY_ROOT") or "").strip()
    if not effective_root:
        raise RuntimeError("persisted production recovery root not ingested")
    if Path(effective_root).resolve(strict=True) != expected_root:
        raise RuntimeError("effective production recovery root mismatch")
    if (os.environ.get("ORION_P5_MUTATION_MODE") or "").strip():
        raise RuntimeError("production mutation mode unexpectedly persisted")
    for name in ("ORION_P5_ALLOW_DISPOSABLE_MUTATION", "ORION_P5_RECOVERY_ROOT"):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"disposable mutation setting unexpectedly present: {name}")

    plugin = load_installed_plugin(plugin_dir)
    ctx = Context()
    plugin.register(ctx)

    if set(ctx.tools) != EXPECTED_TOOLS:
        raise RuntimeError("installed tool registration mismatch")
    if set(ctx.hooks) != {"pre_tool_call", "post_approval_response"}:
        raise RuntimeError("installed hook registration mismatch")
    if ctx.tools[plugin.APPLY_TOOL]["handler"] is not plugin.apply_plan_production_guarded:
        raise RuntimeError("registered apply handler is not guarded P5-02N wrapper")
    if plugin._execute_production_plan_candidate in {
        entry["handler"] for entry in ctx.tools.values()
    }:
        raise RuntimeError("private production executor unexpectedly registered")

    schema = ctx.tools[plugin.APPLY_TOOL]["schema"]["parameters"]
    if set(schema.get("properties") or {}) != {"plan_token"}:
        raise RuntimeError("public apply schema exposes unexpected properties")
    if schema.get("required") != ["plan_token"]:
        raise RuntimeError("public apply schema required list mismatch")
    if schema.get("additionalProperties") is not False:
        raise RuntimeError("public apply schema does not reject extra properties")

    mode = plugin._production_mutation_mode()
    if (
        mode.get("valid") is not True
        or mode.get("mode") != plugin.PRODUCTION_MODE_DISABLED
        or mode.get("mutation_allowed") is not False
    ):
        raise RuntimeError(f"unexpected production mutation mode: {mode}")

    roots = plugin._validate_production_roots()
    if roots.get("success") is not True:
        raise RuntimeError(
            "native production root validation failed: "
            + json.dumps(roots, sort_keys=True)
        )
    if Path(roots["recovery_root"]).resolve(strict=True) != expected_root:
        raise RuntimeError("native validator recovery-root mismatch")
    if roots.get("mutation_allowed") is not False:
        raise RuntimeError("native validator reported mutation allowed")

    inventory = plugin._enumerate_production_recovery_records()
    if inventory.get("success") is not True:
        raise RuntimeError(
            "native recovery inventory failed: "
            + json.dumps(inventory, sort_keys=True)
        )
    if inventory.get("record_count") != 0:
        raise RuntimeError("production recovery inventory is not empty")
    if inventory.get("attention_count") != 0:
        raise RuntimeError("production recovery inventory needs attention")
    if inventory.get("truncated") is not False:
        raise RuntimeError("production recovery inventory unexpectedly truncated")

    old_vault = os.environ.get("ORION_VAULT_ROOT")
    old_inbox = os.environ.get("ORION_INBOX_ROOT")
    executor_called = False

    def forbidden_executor(*_args, **_kwargs):
        nonlocal executor_called
        executor_called = True
        raise RuntimeError("disabled public apply entered private executor")

    original_executor = plugin._execute_production_plan_candidate
    try:
        with tempfile.TemporaryDirectory(prefix="orion-p5-02o-") as temp_dir:
            root = Path(temp_dir)
            vault = root / "vault"
            inbox = root / "inbox"
            vault.mkdir()
            inbox.mkdir()
            note = vault / "note.md"
            before = b"before\n"
            note.write_bytes(before)
            os.environ["ORION_VAULT_ROOT"] = str(vault)
            os.environ["ORION_INBOX_ROOT"] = str(inbox)

            preview = json.loads(
                plugin.preview_edit(
                    {
                        "target_relative_path": "note.md",
                        "new_content": "after\n",
                    }
                )
            )
            if preview.get("success") is not True:
                raise RuntimeError("disposable installed preview failed")
            token = preview["plan_token"]

            plugin._execute_production_plan_candidate = forbidden_executor
            approval_attempts_before = len(plugin._APPROVAL_ATTEMPTS)

            directive = plugin.pre_tool_call(
                plugin.APPLY_TOOL, {"plan_token": token}
            )
            if not isinstance(directive, dict) or directive.get("action") != "block":
                raise RuntimeError("disabled pre-tool call did not block")
            if "rule_key" in directive:
                raise RuntimeError("disabled pre-tool call exposed approval rule key")

            public_apply = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"]({"plan_token": token})
            )
            if (
                public_apply.get("success") is not False
                or public_apply.get("error") != "production_mutation_not_enabled"
                or public_apply.get("mutation_performed") is not False
            ):
                raise RuntimeError("guarded public apply did not refuse disabled mode")
            if executor_called:
                raise RuntimeError("disabled public apply delegated to private executor")
            if len(plugin._APPROVAL_ATTEMPTS) != approval_attempts_before:
                raise RuntimeError("disabled apply created approval-attempt state")
            if note.read_bytes() != before:
                raise RuntimeError("disposable preview fixture changed unexpectedly")
    finally:
        plugin._execute_production_plan_candidate = original_executor
        if old_vault is None:
            os.environ.pop("ORION_VAULT_ROOT", None)
        else:
            os.environ["ORION_VAULT_ROOT"] = old_vault
        if old_inbox is None:
            os.environ.pop("ORION_INBOX_ROOT", None)
        else:
            os.environ["ORION_INBOX_ROOT"] = old_inbox

    api_key = (os.environ.get("API_SERVER_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("API_SERVER_KEY unavailable for live toolset verification")

    request = urllib.request.Request(
        args.gateway.rstrip("/") + "/v1/toolsets",
        method="GET",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        if int(response.status) != 200:
            raise RuntimeError(f"toolsets endpoint returned HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))

    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise RuntimeError("unexpected /v1/toolsets response shape")
    matches = [
        row for row in rows
        if isinstance(row, dict) and row.get("name") == "orion_vault"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one live orion_vault toolset, got {len(matches)}")
    row = matches[0]
    if row.get("enabled") is not True or row.get("configured") is not True:
        raise RuntimeError("live orion_vault toolset is not enabled/configured")
    if set(row.get("tools") or []) != EXPECTED_TOOLS:
        raise RuntimeError("live orion_vault toolset mismatch")

    print("P5_02O_HERMES_DOTENV_LOADED=true")
    print("P5_02O_EFFECTIVE_RECOVERY_ROOT_MATCH=true")
    print("PRODUCTION_MUTATION_MODE=disabled")
    print("PRODUCTION_MUTATION_ALLOWED=false")
    print("P5_02O_NATIVE_ROOT_VALIDATION=PASS")
    print("P5_02O_RECOVERY_INVENTORY_COUNT=0")
    print("P5_02O_RECOVERY_ATTENTION_COUNT=0")
    print("P5_02O_REGISTERED_APPLY_HANDLER=apply_plan_production_guarded")
    print("P5_02O_PRIVATE_EXECUTOR_REGISTERED=false")
    print("P5_02O_APPLY_SCHEMA_PLAN_TOKEN_ONLY=true")
    print("P5_02O_DISABLED_PRETOOL_BLOCK=true")
    print("P5_02O_DISABLED_APPLY_REFUSED=true")
    print("P5_02O_DISABLED_APPROVAL_ATTEMPT_CREATED=false")
    print("P5_02O_DISABLED_EXECUTOR_CALLED=false")
    print("P5_02O_LIVE_ORION_TOOLSET_FOUND=true")
    print("P5_02O_LIVE_ORION_TOOL_COUNT=4")
    print("P5_02O_RUNTIME_VERIFY=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02O_RUNTIME_VERIFY=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
