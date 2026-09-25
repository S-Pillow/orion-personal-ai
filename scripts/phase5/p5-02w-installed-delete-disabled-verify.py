#!/usr/bin/env python3
"""P5-02W installed-disabled runtime verifier.

Loads the installed Orion vault plugin from the COMPANION profile after the
P5-02V 0.3.0 upgrade, verifies the protected-delete preview is registered while
production mutation remains disabled, proves public apply/pre-tool behavior
cannot enter the private executor, validates the exact accepted P5-02U recovery
inventory, and checks the live authenticated Orion toolset.

All preview content used by this verifier lives under disposable temporary
roots. No production mutation path is invoked.
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
    "orion_vault_preview_delete",
    "orion_vault_preview_edit",
    "orion_vault_preview_move_draft",
    "orion_vault_recommend_destination",
}
EXPECTED_RECOVERY = {
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f":
        ("edit_note", "committed_then_changed"),
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27":
        ("restore_edit", "committed"),
    "8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6":
        ("move_draft", "committed_then_changed"),
    "5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175":
        ("restore_move_source", "committed"),
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
        raise RuntimeError("MCP calls are forbidden in P5-02W verification")


def load_installed_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    if not plugin_file.is_file():
        raise RuntimeError(f"installed plugin missing: {plugin_file}")
    spec = importlib.util.spec_from_file_location(
        "orion_p5_02w_runtime_verify", plugin_file
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
            raise RuntimeError(
                f"ambient process setting unexpectedly present: {name}"
            )

    os.environ["HERMES_HOME"] = str(profile)
    from hermes_cli.env_loader import load_hermes_dotenv

    loaded = load_hermes_dotenv(hermes_home=profile)
    if profile / ".env" not in [Path(p).resolve() for p in loaded]:
        raise RuntimeError("Hermes loader did not report COMPANION .env as loaded")

    effective_root = (
        os.environ.get("ORION_P5_PRODUCTION_RECOVERY_ROOT") or ""
    ).strip()
    if not effective_root:
        raise RuntimeError("persisted production recovery root not ingested")
    if Path(effective_root).resolve(strict=True) != expected_root:
        raise RuntimeError("effective production recovery root mismatch")
    if (os.environ.get("ORION_P5_MUTATION_MODE") or "").strip():
        raise RuntimeError("production mutation mode unexpectedly persisted")
    for name in ("ORION_P5_ALLOW_DISPOSABLE_MUTATION", "ORION_P5_RECOVERY_ROOT"):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(
                f"disposable mutation setting unexpectedly present: {name}"
            )

    plugin = load_installed_plugin(plugin_dir)
    if plugin.PLUGIN_VERSION != "p5-02v-0.3.0":
        raise RuntimeError(
            f"installed plugin internal version mismatch: {plugin.PLUGIN_VERSION}"
        )

    ctx = Context()
    plugin.register(ctx)

    if set(ctx.tools) != EXPECTED_TOOLS:
        raise RuntimeError(
            "installed tool registration mismatch: "
            + repr(sorted(ctx.tools))
        )
    if set(ctx.hooks) != {"pre_tool_call", "post_approval_response"}:
        raise RuntimeError("installed hook registration mismatch")
    if (
        ctx.tools[plugin.APPLY_TOOL]["handler"]
        is not plugin.apply_plan_production_guarded
    ):
        raise RuntimeError("registered apply handler is not guarded wrapper")
    if (
        ctx.tools[plugin.PREVIEW_DELETE_TOOL]["handler"]
        is not plugin.preview_delete
    ):
        raise RuntimeError("registered delete-preview handler mismatch")
    if plugin._execute_production_plan_candidate in {
        entry["handler"] for entry in ctx.tools.values()
    }:
        raise RuntimeError("private production executor unexpectedly registered")

    apply_schema = ctx.tools[plugin.APPLY_TOOL]["schema"]["parameters"]
    if set(apply_schema.get("properties") or {}) != {"plan_token"}:
        raise RuntimeError("public apply schema exposes unexpected properties")
    if apply_schema.get("required") != ["plan_token"]:
        raise RuntimeError("public apply schema required list mismatch")
    if apply_schema.get("additionalProperties") is not False:
        raise RuntimeError("public apply schema does not reject extra properties")

    delete_schema = ctx.tools[plugin.PREVIEW_DELETE_TOOL]["schema"]["parameters"]
    if set(delete_schema.get("properties") or {}) != {"target_relative_path"}:
        raise RuntimeError("delete preview schema exposes unexpected properties")
    if delete_schema.get("required") != ["target_relative_path"]:
        raise RuntimeError("delete preview required list mismatch")
    if delete_schema.get("additionalProperties") is not False:
        raise RuntimeError("delete preview schema does not reject extras")

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
    if inventory.get("record_count") != 4:
        raise RuntimeError("production recovery inventory is not exactly 4")
    if inventory.get("attention_count") != 0:
        raise RuntimeError("production recovery inventory needs attention")
    if inventory.get("truncated") is not False:
        raise RuntimeError("production recovery inventory unexpectedly truncated")

    records = {}
    for row in inventory.get("records") or []:
        recovery_id = row.get("recovery_id")
        if not isinstance(recovery_id, str) or recovery_id in records:
            raise RuntimeError("recovery inventory id invalid/duplicate")
        records[recovery_id] = row
    if set(records) != set(EXPECTED_RECOVERY):
        raise RuntimeError("production recovery id set mismatch")

    for recovery_id, (expected_action, expected_classification) in (
        EXPECTED_RECOVERY.items()
    ):
        row = records[recovery_id]
        if row.get("valid") is not True or row.get("needs_attention") is not False:
            raise RuntimeError(
                f"recovery record invalid/attention: {recovery_id}"
            )
        recovery = row.get("recovery")
        receipt = row.get("receipt")
        if not isinstance(recovery, dict) or not isinstance(receipt, dict):
            raise RuntimeError(
                f"recovery/receipt inspection missing: {recovery_id}"
            )
        if recovery.get("action") != expected_action:
            raise RuntimeError(
                f"recovery action mismatch: {recovery_id}"
            )
        if recovery.get("classification") != expected_classification:
            raise RuntimeError(
                f"recovery classification mismatch: {recovery_id}"
            )
        if recovery.get("recovery_required") is not False:
            raise RuntimeError(
                f"recovery unexpectedly required: {recovery_id}"
            )
        if (
            receipt.get("receipt_state") != "committed"
            or receipt.get("receipt_finalized") is not True
            or receipt.get("receipt_reconciliation_required") is not False
        ):
            raise RuntimeError(
                f"receipt state mismatch: {recovery_id}"
            )

    old_vault = os.environ.get("ORION_VAULT_ROOT")
    old_inbox = os.environ.get("ORION_INBOX_ROOT")
    executor_called = False
    original_executor = plugin._execute_production_plan_candidate

    def forbidden_executor(*_args, **_kwargs):
        nonlocal executor_called
        executor_called = True
        raise RuntimeError("disabled public apply entered private executor")

    try:
        with tempfile.TemporaryDirectory(prefix="orion-p5-02w-") as temp_dir:
            root = Path(temp_dir)
            vault = root / "vault"
            inbox = root / "inbox"
            vault.mkdir()
            inbox.mkdir()
            note = vault / "delete-me.md"
            before = b"protected delete verifier\n"
            note.write_bytes(before)
            os.environ["ORION_VAULT_ROOT"] = str(vault)
            os.environ["ORION_INBOX_ROOT"] = str(inbox)

            preview = json.loads(plugin.preview_delete({
                "target_relative_path": "delete-me.md",
            }))
            if preview.get("success") is not True:
                raise RuntimeError("installed delete preview failed")
            if preview.get("mutation_performed") is not False:
                raise RuntimeError("installed delete preview mutated")
            if preview.get("plan", {}).get("action") != "delete_note":
                raise RuntimeError("installed delete preview action mismatch")
            if preview.get("plan", {}).get("target_sha256") != plugin._sha_bytes(
                before
            ):
                raise RuntimeError("installed delete preview hash mismatch")
            if note.read_bytes() != before:
                raise RuntimeError("installed delete preview changed fixture")

            token = preview["plan_token"]
            plugin._execute_production_plan_candidate = forbidden_executor
            approval_attempts_before = len(plugin._APPROVAL_ATTEMPTS)

            directive = plugin.pre_tool_call(
                plugin.APPLY_TOOL, {"plan_token": token}
            )
            if (
                not isinstance(directive, dict)
                or directive.get("action") != "block"
            ):
                raise RuntimeError("disabled pre-tool call did not block")
            if "rule_key" in directive:
                raise RuntimeError(
                    "disabled pre-tool call exposed approval rule key"
                )

            public_apply = json.loads(
                ctx.tools[plugin.APPLY_TOOL]["handler"](
                    {"plan_token": token}
                )
            )
            if (
                public_apply.get("success") is not False
                or public_apply.get("error")
                != "production_mutation_not_enabled"
                or public_apply.get("mutation_performed") is not False
            ):
                raise RuntimeError(
                    "guarded public apply did not refuse disabled mode"
                )
            if executor_called:
                raise RuntimeError(
                    "disabled public apply delegated to private executor"
                )
            if len(plugin._APPROVAL_ATTEMPTS) != approval_attempts_before:
                raise RuntimeError(
                    "disabled apply created approval-attempt state"
                )
            if note.read_bytes() != before:
                raise RuntimeError(
                    "disposable delete preview fixture changed unexpectedly"
                )
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
        raise RuntimeError(
            "API_SERVER_KEY unavailable for live toolset verification"
        )

    request = urllib.request.Request(
        args.gateway.rstrip("/") + "/v1/toolsets",
        method="GET",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        if int(response.status) != 200:
            raise RuntimeError(
                f"toolsets endpoint returned HTTP {response.status}"
            )
        payload = json.loads(response.read().decode("utf-8"))

    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise RuntimeError("unexpected /v1/toolsets response shape")
    matches = [
        row for row in rows
        if isinstance(row, dict) and row.get("name") == "orion_vault"
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one live orion_vault toolset, got {len(matches)}"
        )
    row = matches[0]
    if row.get("enabled") is not True or row.get("configured") is not True:
        raise RuntimeError("live orion_vault toolset is not enabled/configured")
    if set(row.get("tools") or []) != EXPECTED_TOOLS:
        raise RuntimeError("live orion_vault toolset mismatch")

    print("P5_02W_HERMES_DOTENV_LOADED=true")
    print("P5_02W_EFFECTIVE_RECOVERY_ROOT_MATCH=true")
    print("PRODUCTION_MUTATION_MODE=disabled")
    print("PRODUCTION_MUTATION_ALLOWED=false")
    print("P5_02W_NATIVE_ROOT_VALIDATION=PASS")
    print("P5_02W_RECOVERY_INVENTORY_COUNT=4")
    print("P5_02W_RECOVERY_ATTENTION_COUNT=0")
    print("P5_02W_RECOVERY_BASELINE_MATCH=true")
    print("P5_02W_REGISTERED_APPLY_HANDLER=apply_plan_production_guarded")
    print("P5_02W_PRIVATE_EXECUTOR_REGISTERED=false")
    print("P5_02W_DELETE_PREVIEW_HANDLER=preview_delete")
    print("P5_02W_APPLY_SCHEMA_PLAN_TOKEN_ONLY=true")
    print("P5_02W_DELETE_PREVIEW_SCHEMA_TARGET_ONLY=true")
    print("P5_02W_DELETE_PREVIEW_READ_ONLY=true")
    print("P5_02W_DISABLED_PRETOOL_BLOCK=true")
    print("P5_02W_DISABLED_APPLY_REFUSED=true")
    print("P5_02W_DISABLED_APPROVAL_ATTEMPT_CREATED=false")
    print("P5_02W_DISABLED_EXECUTOR_CALLED=false")
    print("P5_02W_LIVE_ORION_TOOLSET_FOUND=true")
    print("P5_02W_LIVE_ORION_TOOL_COUNT=5")
    print("P5_02W_RUNTIME_VERIFY=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02W_RUNTIME_VERIFY=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
