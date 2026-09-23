#!/usr/bin/env python3
"""P5-02P-B read-only production canary readiness verifier.

This script never enables mutation, never invokes the apply tool, and never
writes vault/inbox/recovery content. It loads the installed Orion plugin under
the COMPANION profile, validates the accepted production roots and empty
recovery inventory, then creates an in-memory edit preview for the dedicated
canary and proves the target bytes remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path


TARGET_RELATIVE_PATH = "_Orion-P5-Canary.md"
BEFORE_BYTES = (
    b"# Orion Phase 5 Canary\n"
    b"state: before\n"
    b"gate: first-production-edit\n"
)
AFTER_TEXT = (
    "# Orion Phase 5 Canary\n"
    "state: after\n"
    "gate: first-production-edit\n"
)
EXPECTED_BEFORE_SHA256 = "ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c"
EXPECTED_AFTER_SHA256 = "86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19"
EXPECTED_DIFF_SHA256 = "6642d44372449d01e1ec3f5d325bd2b372f52cc58610293bcccf0e4e4ec996e8"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_installed_plugin(plugin_dir: Path):
    plugin_file = plugin_dir / "__init__.py"
    if not plugin_file.is_file():
        raise RuntimeError(f"installed plugin missing: {plugin_file}")
    spec = importlib.util.spec_from_file_location(
        "orion_p5_02p_readiness", plugin_file
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
    args = parser.parse_args()

    profile = args.profile.resolve(strict=True)
    plugin_dir = args.plugin_dir.resolve(strict=True)
    expected_recovery_root = args.expected_recovery_root.resolve(strict=True)

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

    if (os.environ.get("ORION_P5_MUTATION_MODE") or "").strip():
        raise RuntimeError("production mutation mode unexpectedly persisted")
    for name in ("ORION_P5_ALLOW_DISPOSABLE_MUTATION", "ORION_P5_RECOVERY_ROOT"):
        if (os.environ.get(name) or "").strip():
            raise RuntimeError(f"disposable mutation setting unexpectedly present: {name}")

    plugin = load_installed_plugin(plugin_dir)

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
    if roots.get("mutation_allowed") is not False:
        raise RuntimeError("native validator reported mutation allowed")

    recovery_root = Path(roots["recovery_root"]).resolve(strict=True)
    if recovery_root != expected_recovery_root:
        raise RuntimeError("native validator recovery-root mismatch")

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

    vault_root = Path(roots["vault_root"]).resolve(strict=True)
    target = (vault_root / TARGET_RELATIVE_PATH)
    if not target.is_file():
        raise RuntimeError("canary target is missing")
    if plugin._path_has_reparse_component(target):
        raise RuntimeError("canary target has a reparse component")

    canonical_target = target.resolve(strict=True)
    try:
        canonical_target.relative_to(vault_root)
    except ValueError as exc:
        raise RuntimeError("canary escaped accepted vault root") from exc

    before_actual = target.read_bytes()
    if before_actual != BEFORE_BYTES:
        raise RuntimeError(
            "canary bytes differ from the frozen P5-02P before fixture"
        )
    before_sha = sha256(before_actual)
    if before_sha != EXPECTED_BEFORE_SHA256:
        raise RuntimeError("canary before hash differs from frozen contract")

    file_identity = plugin._windows_path_file_identity(target)

    preview = json.loads(
        plugin.preview_edit(
            {
                "target_relative_path": TARGET_RELATIVE_PATH,
                "new_content": AFTER_TEXT,
            }
        )
    )
    if preview.get("success") is not True:
        raise RuntimeError(
            "production canary preview failed: "
            + json.dumps(preview, sort_keys=True)
        )
    if preview.get("mutation_performed") is not False:
        raise RuntimeError("preview unexpectedly reported mutation")

    plan = preview.get("plan") or {}
    if plan.get("action") != "edit_note":
        raise RuntimeError("preview action is not edit_note")
    if plan.get("target_canonical_path") != str(canonical_target):
        raise RuntimeError("preview canonical target mismatch")
    if plan.get("original_sha256") != before_sha:
        raise RuntimeError("preview before hash mismatch")

    expected_after_sha = sha256(AFTER_TEXT.encode("utf-8"))
    if expected_after_sha != EXPECTED_AFTER_SHA256:
        raise RuntimeError("local proposed bytes differ from frozen after hash")
    if plan.get("proposed_sha256") != EXPECTED_AFTER_SHA256:
        raise RuntimeError("preview after hash mismatch")
    if plan.get("target_file_id") != file_identity:
        raise RuntimeError("preview Windows file identity mismatch")

    diff_text = preview.get("diff")
    if not isinstance(diff_text, str) or not diff_text:
        raise RuntimeError("preview exact diff missing")
    diff_sha = sha256(diff_text.encode("utf-8"))
    if diff_sha != EXPECTED_DIFF_SHA256:
        raise RuntimeError("preview diff differs from frozen exact diff")
    if plan.get("diff_sha256") != EXPECTED_DIFF_SHA256:
        raise RuntimeError("preview diff hash mismatch")

    if target.read_bytes() != before_actual:
        raise RuntimeError("canary bytes changed during side-effect-free preview")
    if plugin._windows_path_file_identity(target) != file_identity:
        raise RuntimeError("canary file identity changed during preview")

    print("P5_02P_READINESS=PASS")
    print("P5_02P_MUTATION_MODE=disabled")
    print("P5_02P_MUTATION_ALLOWED=false")
    print("P5_02P_RECOVERY_INVENTORY_COUNT=0")
    print("P5_02P_RECOVERY_ATTENTION_COUNT=0")
    print(f"P5_02P_CANARY_RELATIVE_PATH={TARGET_RELATIVE_PATH}")
    print(f"P5_02P_CANARY_CANONICAL_PATH={canonical_target}")
    print(f"P5_02P_CANARY_FILE_ID={file_identity}")
    print(f"P5_02P_CANARY_BEFORE_SHA256={before_sha}")
    print(f"P5_02P_CANARY_AFTER_SHA256={EXPECTED_AFTER_SHA256}")
    print(f"P5_02P_CANARY_DIFF_SHA256={EXPECTED_DIFF_SHA256}")
    print("P5_02P_PREVIEW_MUTATION=false")
    print("P5_02P_CANARY_UNCHANGED=true")
    print("P5_02P_EXACT_DIFF_BEGIN")
    print(diff_text, end="" if diff_text.endswith("\n") else "\n")
    print("P5_02P_EXACT_DIFF_END")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            f"P5_02P_READINESS=FAIL; ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
