#!/usr/bin/env python3
"""P5-02L read-only runtime-ingestion verifier.

Runs under the accepted Hermes Python while the COMPANION gateway is live.
It uses Hermes's own dotenv loader for the COMPANION profile, verifies the
effective production recovery-root setting and disabled mutation mode, checks
native production-root/inventory readiness, proves public apply remains
fail-closed, and queries the live gateway's authenticated /v1/toolsets endpoint.

No environment contents or API key values are printed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
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
        raise RuntimeError("MCP calls are forbidden in P5-02L verification")


def load_installed_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    if not plugin_file.is_file():
        raise RuntimeError(f"installed plugin missing: {plugin_file}")
    spec = importlib.util.spec_from_file_location(
        "orion_p5_02l_runtime_verify", plugin_file
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

    # The operator shell must not pre-seed Phase 5 settings. This proves the
    # effective value observed below is supplied by Hermes profile loading.
    for name in (
        "ORION_P5_PRODUCTION_RECOVERY_ROOT",
        "ORION_P5_MUTATION_MODE",
        "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
        "ORION_P5_RECOVERY_ROOT",
    ):
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
        raise RuntimeError("production mutation mode unexpectedly present")
    for name in ("ORION_P5_ALLOW_DISPOSABLE_MUTATION", "ORION_P5_RECOVERY_ROOT"):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"disposable mutation setting unexpectedly present: {name}")

    plugin = load_installed_plugin(plugin_dir)
    ctx = Context()
    plugin.register(ctx)

    if set(ctx.tools) != EXPECTED_TOOLS:
        raise RuntimeError("installed tool registration mismatch")
    if ctx.tools[plugin.APPLY_TOOL]["handler"] is not plugin.apply_plan_placeholder:
        raise RuntimeError("registered apply handler is not fail-closed placeholder")
    if plugin._execute_production_plan_candidate in {
        entry["handler"] for entry in ctx.tools.values()
    }:
        raise RuntimeError("private production executor unexpectedly registered")

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

    public_apply = json.loads(
        ctx.tools[plugin.APPLY_TOOL]["handler"]({"plan_token": "0" * 64})
    )
    if (
        public_apply.get("success") is not False
        or public_apply.get("error") != "p5_01_mutation_not_authorized"
        or public_apply.get("mutation_performed") is not False
    ):
        raise RuntimeError("registered apply no longer fails closed")

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

    matches = [row for row in rows if isinstance(row, dict) and row.get("name") == "orion_vault"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one live orion_vault toolset, got {len(matches)}")
    row = matches[0]
    if row.get("enabled") is not True or row.get("configured") is not True:
        raise RuntimeError("live orion_vault toolset is not enabled/configured")

    tools = set(row.get("tools") or [])
    if tools != EXPECTED_TOOLS:
        raise RuntimeError(f"live orion_vault toolset mismatch: {sorted(tools)}")

    print("P5_02L_HERMES_DOTENV_LOADED=true")
    print("P5_02L_EFFECTIVE_RECOVERY_ROOT_MATCH=true")
    print("PRODUCTION_MUTATION_MODE=disabled")
    print("PRODUCTION_MUTATION_ALLOWED=false")
    print("P5_02L_NATIVE_ROOT_VALIDATION=PASS")
    print("P5_02L_RECOVERY_INVENTORY_COUNT=0")
    print("P5_02L_RECOVERY_ATTENTION_COUNT=0")
    print("P5_02L_REGISTERED_APPLY_FAIL_CLOSED=true")
    print("P5_02L_LIVE_ORION_TOOLSET_FOUND=true")
    print("P5_02L_LIVE_ORION_TOOL_COUNT=4")
    print("P5_02L_RUNTIME_INGESTION=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02L_RUNTIME_INGESTION=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
