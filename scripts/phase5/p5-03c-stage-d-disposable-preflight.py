#!/usr/bin/env python3
"""P5-03C Stage D disposable reconnect preflight.

Read-only preparation only. This script does not create disposable roots,
request approval, invoke the private disposable executor, mutate vault/inbox,
or write Hermes SessionDB.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path


EXPECTED_BRANCH = "feature/orion-phase5-p5-03c-reconnect-hydration"
EXPECTED_HERMES_HEAD = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
EXPECTED_HERMES_API_SHA256 = (
    "7a206396aac7abe7e50fd5d346733fea85bb57160cb0a5d8a2e7feda29167c84"
)
FORBIDDEN_PERSISTED = {
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(repo: Path, *args: str) -> str:
    import subprocess
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return proc.stdout.strip()


def env_names(path: Path) -> set[str]:
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        names.add(line.split("=", 1)[0].strip())
    return names


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA_unavailable")
    hermes_root = Path(local) / "hermes" / "hermes-agent"
    profile = Path(local) / "hermes" / "profiles" / "companion"
    dotenv = profile / ".env"
    plugin_path = profile / "plugins" / "orion-vault-actions" / "__init__.py"
    api_source = hermes_root / "gateway" / "platforms" / "api_server.py"

    branch = git(repo, "branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"unexpected_branch:{branch}")
    if git(repo, "status", "--porcelain=v1"):
        raise RuntimeError("orion_worktree_not_clean")
    if git(hermes_root, "rev-parse", "HEAD") != EXPECTED_HERMES_HEAD:
        raise RuntimeError("hermes_head_drift")
    if sha256(api_source) != EXPECTED_HERMES_API_SHA256:
        raise RuntimeError("hermes_api_source_drift")

    persisted = env_names(dotenv)
    bad = sorted(FORBIDDEN_PERSISTED & persisted)
    if bad:
        raise RuntimeError("forbidden_persisted_disposable_env:" + ",".join(bad))
    if os.environ.get("ORION_P5_MUTATION_MODE"):
        raise RuntimeError("production_mutation_mode_present")

    if not plugin_path.is_file():
        raise RuntimeError("installed_orion_plugin_missing")

    spec = importlib.util.spec_from_file_location(
        "orion_p5_03c_stage_d_plugin",
        plugin_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed_plugin_import_spec_failed")
    plugin = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = plugin
    spec.loader.exec_module(plugin)

    private_executor = getattr(
        plugin,
        "_execute_disposable_plan_candidate",
        None,
    )
    if not callable(private_executor):
        raise RuntimeError("private_disposable_executor_missing")

    tools = getattr(plugin, "TOOLS", None)
    apply_handler = None
    if isinstance(tools, dict):
        apply_row = tools.get("orion_vault_apply_plan")
        if isinstance(apply_row, dict):
            apply_handler = apply_row.get("handler")

    registered_private = apply_handler is private_executor
    if registered_private:
        raise RuntimeError("private_disposable_executor_is_registered")

    print(f"P5_03C_STAGE_D_PREFLIGHT_BRANCH={json.dumps(branch)}")
    print(f"P5_03C_STAGE_D_HERMES_HEAD={json.dumps(EXPECTED_HERMES_HEAD)}")
    print(f"P5_03C_STAGE_D_HERMES_API_SHA256={json.dumps(EXPECTED_HERMES_API_SHA256)}")
    print("P5_03C_STAGE_D_PRODUCTION_MUTATION_MODE_PRESENT=false")
    print("P5_03C_STAGE_D_PERSISTED_DISPOSABLE_ENV_PRESENT=false")
    print("P5_03C_STAGE_D_PRIVATE_DISPOSABLE_EXECUTOR_PRESENT=true")
    print("P5_03C_STAGE_D_PRIVATE_EXECUTOR_REGISTERED=false")
    print("P5_03C_STAGE_D_APPROVAL_REQUESTED=false")
    print("P5_03C_STAGE_D_MUTATION_PERFORMED=false")
    print("P5_03C_STAGE_D_VAULT_READ=false")
    print("P5_03C_STAGE_D_VAULT_MUTATION=false")
    print("P5_03C_STAGE_D_PREFLIGHT=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            "P5_03C_STAGE_D_PREFLIGHT=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
