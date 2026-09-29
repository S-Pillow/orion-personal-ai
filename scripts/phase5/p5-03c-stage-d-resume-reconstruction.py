#!/usr/bin/env python3
"""Resume P5-03C Stage D from a preserved disposable fixture.

This is read-only with respect to the preserved fixture. It performs no new
approval and no mutation. It validates the committed disposable recovery and
receipt, validates the current disposable target postcondition, then builds the
same browser-safe completion envelope the production executor would have
returned from those independently proven fields. That bounded envelope is
placed only into an isolated fake-Hermes persisted session and reconstructed
through two fresh real Orion bridge processes.

This resume path exists because the older private disposable executor omits
'action' and 'recovery_id' from its success return even though those values are
durably committed in the fixture's manifest/receipt. The production executor
returns both fields. P5-03A correctly treated the incomplete private return as
'unknown'; this script does not weaken that threshold.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path


EXPECTED_BRANCH = "feature/orion-phase5-p5-03c-reconnect-hydration"
RECOVERY_ID_RE = re.compile(r"^[0-9a-f]{64}$")


def git_text(repo: Path, *args: str) -> str:
    import subprocess
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(
            "git_failed:" + (proc.stderr or proc.stdout).strip()[:400]
        )
    return proc.stdout.strip()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@contextmanager
def env_scope(values: dict[str, str | None]):
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_spec_unavailable:{path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        required=True,
        type=Path,
        help="Preserved P5-03C Stage D disposable fixture directory.",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    if git_text(repo, "branch", "--show-current") != EXPECTED_BRANCH:
        raise RuntimeError("unexpected_orion_branch")
    if git_text(repo, "status", "--porcelain=v1"):
        raise RuntimeError("orion_worktree_not_clean")

    fixture = args.fixture.resolve()
    if not fixture.is_dir():
        raise RuntimeError(f"preserved_fixture_missing:{fixture}")

    vault = fixture / "vault"
    inbox = fixture / "inbox"
    recovery_root = fixture / "recovery"
    if not all(path.is_dir() for path in (vault, inbox, recovery_root)):
        raise RuntimeError("preserved_fixture_roots_incomplete")

    # Guard against accidentally pointing this resume step at the live roots.
    live_vault = Path(r"C:\Personal\Me")
    live_inbox = Path(r"C:\Personal\Orion-Inbox")
    for candidate in (vault.resolve(), inbox.resolve(), recovery_root.resolve()):
        for protected in (live_vault.resolve(), live_inbox.resolve()):
            if candidate == protected:
                raise RuntimeError("preserved_fixture_overlaps_live_root")

    recovery_ids = sorted(
        child.name
        for child in recovery_root.iterdir()
        if child.is_dir() and RECOVERY_ID_RE.fullmatch(child.name)
    )
    if len(recovery_ids) != 1:
        raise RuntimeError(
            f"expected_exactly_one_recovery_record:{len(recovery_ids)}"
        )
    recovery_id = recovery_ids[0]
    recovery_dir = recovery_root / recovery_id
    manifest_path = recovery_dir / "manifest.json"
    receipt_path = recovery_dir / "receipt.json"
    if not manifest_path.is_file() or not receipt_path.is_file():
        raise RuntimeError("committed_evidence_files_missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    if manifest.get("state") != "committed":
        raise RuntimeError("manifest_not_committed")
    if receipt.get("state") != "committed":
        raise RuntimeError("receipt_not_committed")
    if receipt.get("final_classification") != "committed":
        raise RuntimeError("receipt_final_classification_not_committed")
    if receipt.get("recovery_id") != recovery_id:
        raise RuntimeError("receipt_recovery_id_mismatch")
    if receipt.get("plan_token") != recovery_id:
        raise RuntimeError("receipt_plan_token_mismatch")
    if receipt.get("approval", {}).get("choice") != "once":
        raise RuntimeError("receipt_approval_not_once")
    if receipt.get("approval", {}).get("authorization_reusable") is not False:
        raise RuntimeError("receipt_authorization_reusable")

    action = manifest.get("action")
    target_relative = manifest.get("target_relative_path")
    after_sha = manifest.get("after_sha256")
    if action != "edit_note":
        raise RuntimeError(f"unexpected_action:{action}")
    if not isinstance(target_relative, str) or not target_relative:
        raise RuntimeError("target_relative_path_missing")
    if not isinstance(after_sha, str) or not RECOVERY_ID_RE.fullmatch(after_sha):
        raise RuntimeError("committed_after_sha256_invalid")

    target = (vault / target_relative).resolve()
    try:
        target.relative_to(vault.resolve())
    except ValueError as exc:
        raise RuntimeError("committed_target_escaped_disposable_vault") from exc
    if not target.is_file():
        raise RuntimeError("committed_target_missing")
    if sha256_path(target) != after_sha:
        raise RuntimeError("committed_target_postcondition_mismatch")

    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA_unavailable")
    plugin_dir = (
        Path(local)
        / "hermes"
        / "profiles"
        / "companion"
        / "plugins"
        / "orion-vault-actions"
    )
    plugin = load_module(
        plugin_dir / "__init__.py",
        "orion_p5_03c_stage_d_resume_plugin",
    )
    if "require_fresh_approval" not in inspect.signature(
        plugin._execute_disposable_plan_candidate
    ).parameters:
        raise RuntimeError("installed_plugin_fresh_approval_seam_missing")

    with env_scope({
        "ORION_VAULT_ROOT": str(vault),
        "ORION_INBOX_ROOT": str(inbox),
        plugin.RECOVERY_ROOT_ENV: str(recovery_root),
        plugin.DISPOSABLE_MUTATION_FLAG: "1",
        plugin.PRODUCTION_MUTATION_MODE_ENV: None,
        plugin.PRODUCTION_RECOVERY_ROOT_ENV: None,
    }):
        recovery_inspected = plugin._inspect_disposable_recovery_candidate(
            recovery_id
        )
        receipt_inspected = plugin._inspect_disposable_receipt_candidate(
            recovery_id
        )

    if (
        recovery_inspected.get("success") is not True
        or recovery_inspected.get("classification") != "committed"
        or recovery_inspected.get("recovery_required") is not False
    ):
        raise RuntimeError(
            "durable_recovery_inspection_failed:"
            + json.dumps(recovery_inspected, sort_keys=True)
        )
    if (
        receipt_inspected.get("success") is not True
        or receipt_inspected.get("correlation_valid") is not True
        or receipt_inspected.get("receipt_state") != "committed"
        or receipt_inspected.get("authorization_reusable") is not False
        or receipt_inspected.get("recovery_id") != recovery_id
        or receipt_inspected.get("action") != action
    ):
        raise RuntimeError(
            "durable_receipt_inspection_failed:"
            + json.dumps(receipt_inspected, sort_keys=True)
        )

    # Production executor returns exactly these consequential fields after the
    # same postcondition and committed receipt/recovery checks. No private path
    # or authorization material enters this envelope.
    completion_result = {
        "success": True,
        "mutation_performed": True,
        "recovery_required": False,
        "recovery_id": recovery_id,
        "action": action,
        "target_relative_path": target_relative,
        "after_sha256": after_sha,
    }

    stage_d = load_module(
        repo / "scripts" / "phase5"
        / "p5-03c-stage-d-disposable-reconnect.py",
        "orion_p5_03c_stage_d_reconstruction",
    )
    hud_root = repo / "hud"
    if str(hud_root) not in sys.path:
        sys.path.insert(0, str(hud_root))
    import orion_hud_bridge as bridge

    first, second = stage_d.qualify_reconstruction(
        bridge,
        plugin,
        completion_result,
    )
    if first != second:
        raise RuntimeError("fresh_hud_reconstruction_mismatch")
    if first.get("state") != "succeeded":
        raise RuntimeError(
            f"reconstructed_state_not_succeeded:{first.get('state')}"
        )
    if first.get("durability") != "completed_record":
        raise RuntimeError("reconstructed_durability_not_completed_record")
    if first.get("recovery_state") != "unavailable":
        raise RuntimeError("reconstructed_recovery_state_not_unavailable")

    serialized = json.dumps(first, sort_keys=True)
    for forbidden in (
        str(recovery_dir),
        "approval_message",
        "approval_attempt_id",
        "recovery_dir",
    ):
        if forbidden and forbidden in serialized:
            raise RuntimeError("private_or_authorization_evidence_egress")

    print(f"P5_03C_STAGE_D_RESUME_FIXTURE={fixture}")
    print(f"P5_03C_STAGE_D_RECOVERY_ID={recovery_id}")
    print("P5_03C_STAGE_D_EXISTING_MUTATION_REUSED=true")
    print("P5_03C_STAGE_D_NEW_APPROVAL_REQUESTED=false")
    print("P5_03C_STAGE_D_NEW_MUTATION_PERFORMED=false")
    print("P5_03C_STAGE_D_DURABLE_RECOVERY_CLASSIFICATION=committed")
    print("P5_03C_STAGE_D_DURABLE_RECEIPT_STATE=committed")
    print("P5_03C_STAGE_D_DURABLE_CORRELATION_VALID=true")
    print("P5_03C_STAGE_D_POSTCONDITION_MATCH=true")
    print("P5_03C_STAGE_D_COMPOSITE_EVIDENCE_THRESHOLD_PRESERVED=true")
    print("P5_03C_STAGE_D_PROJECTED_STATE=succeeded")
    print("P5_03C_STAGE_D_PROJECTED_DURABILITY=completed_record")
    print("P5_03C_STAGE_D_CURRENT_RECOVERY_VISIBILITY=unavailable")
    print("P5_03C_STAGE_D_HUD_RESTART_RECONSTRUCTION_MATCH=true")
    print("P5_03C_STAGE_D_PRIVATE_PATH_EGRESS=false")
    print("P5_03C_STAGE_D_LIVE_SESSIONDB_WRITTEN=false")
    print("P5_03C_STAGE_D_REAL_VAULT_INBOX_TOUCHED=false")
    print("P5_03C_STAGE_D_RESUME_QUALIFICATION=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            "P5_03C_STAGE_D_RESUME_QUALIFICATION=FAIL; "
            f"ERROR={type(exc).__name__}:{exc}",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
