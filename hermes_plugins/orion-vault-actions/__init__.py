"""Orion Phase 5 native vault-actions plugin, P5-01 source-only slice.

P5-01 is intentionally non-mutating. It provides read-only preview tools plus a
fail-closed placeholder apply tool so Hermes generic approval interception can
be tested before any live vault mutation is authorized.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import stat
import time
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict

PLUGIN_VERSION = "p5-01-0.1"
MAX_TEXT_CHARS = 100_000
PREVIEW_TTL_SECONDS = 600.0
PREVIEW_CACHE_LIMIT = 32

DEFAULT_VAULT_ROOT = r"C:\Personal\Me"
DEFAULT_INBOX_ROOT = r"C:\Personal\Orion-Inbox"

PREVIEW_EDIT_TOOL = "orion_vault_preview_edit"
PREVIEW_MOVE_TOOL = "orion_vault_preview_move_draft"
APPLY_TOOL = "orion_vault_apply_plan"

_PREVIEWS: Dict[str, Dict[str, Any]] = {}
_PREVIEW_TIMES: Dict[str, float] = {}


class PathPolicyError(ValueError):
    """Raised when a requested path violates the Orion vault containment policy."""


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_text(text: str) -> str:
    return _sha_bytes(text.encode("utf-8"))


def _plan_token(plan: Dict[str, Any]) -> str:
    payload = json.dumps(
        plan,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _unified_diff(old: str, new: str, old_name: str, new_name: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=old_name,
            tofile=new_name,
            lineterm="\n",
        )
    )


def _roots() -> tuple[Path, Path]:
    vault = Path(os.environ.get("ORION_VAULT_ROOT", DEFAULT_VAULT_ROOT))
    inbox = Path(os.environ.get("ORION_INBOX_ROOT", DEFAULT_INBOX_ROOT))
    return vault, inbox


def _normalize_relative(raw: Any) -> PurePosixPath:
    value = str(raw or "").strip()
    if not value or "\x00" in value:
        raise PathPolicyError("invalid_relative_path")

    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(normalized)

    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise PathPolicyError("absolute_path_rejected")

    if not posix.parts or any(part in ("", ".", "..") for part in posix.parts):
        raise PathPolicyError("path_traversal_rejected")

    return posix


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False

    if stat.S_ISLNK(info.st_mode):
        return True

    attrs = getattr(info, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & flag)


def _ensure_contained(root_real: Path, candidate_real: Path) -> None:
    try:
        candidate_real.relative_to(root_real)
    except ValueError as exc:
        raise PathPolicyError("resolved_path_outside_root") from exc


def _resolve_under_root(
    root: Path,
    raw_relative: Any,
    *,
    must_exist: bool = False,
    allow_missing_leaf: bool = False,
) -> tuple[Path, str]:
    relative = _normalize_relative(raw_relative)

    if not root.is_dir():
        raise PathPolicyError("root_missing")

    root_real = root.resolve(strict=True)
    candidate = root.joinpath(*relative.parts)

    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and _is_reparse_point(cursor):
            raise PathPolicyError("reparse_point_rejected")

    if candidate.exists():
        candidate_real = candidate.resolve(strict=True)
        _ensure_contained(root_real, candidate_real)
    else:
        if must_exist:
            raise FileNotFoundError("path_not_found")

        ancestor = candidate.parent
        while not ancestor.exists() and ancestor != root:
            ancestor = ancestor.parent
        ancestor_real = ancestor.resolve(strict=True)
        _ensure_contained(root_real, ancestor_real)

        if not allow_missing_leaf and not candidate.exists():
            raise FileNotFoundError("path_not_found")

    return candidate, relative.as_posix()


def _require_markdown(relative: str) -> None:
    if not relative.lower().endswith(".md"):
        raise PathPolicyError("markdown_only")


def _read_utf8(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PathPolicyError("utf8_required") from exc
    return data, text


def _remember_preview(token: str, plan: Dict[str, Any]) -> None:
    now = time.monotonic()

    expired = [
        key
        for key, created in _PREVIEW_TIMES.items()
        if now - created > PREVIEW_TTL_SECONDS
    ]
    for key in expired:
        _PREVIEWS.pop(key, None)
        _PREVIEW_TIMES.pop(key, None)

    if len(_PREVIEWS) >= PREVIEW_CACHE_LIMIT:
        oldest = min(_PREVIEW_TIMES, key=_PREVIEW_TIMES.get)
        _PREVIEWS.pop(oldest, None)
        _PREVIEW_TIMES.pop(oldest, None)

    _PREVIEWS[token] = dict(plan)
    _PREVIEW_TIMES[token] = now


def _lookup_preview(token: str) -> Dict[str, Any] | None:
    created = _PREVIEW_TIMES.get(token)
    if created is None:
        return None

    if time.monotonic() - created > PREVIEW_TTL_SECONDS:
        _PREVIEWS.pop(token, None)
        _PREVIEW_TIMES.pop(token, None)
        return None

    plan = _PREVIEWS.get(token)
    return dict(plan) if plan else None


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def preview_edit(params: Dict[str, Any], **_: Any) -> str:
    vault_root, _ = _roots()

    target, target_rel = _resolve_under_root(
        vault_root,
        params.get("target_relative_path"),
        must_exist=True,
    )
    _require_markdown(target_rel)

    new_text = params.get("new_content")
    if not isinstance(new_text, str):
        return _json({"success": False, "error": "new_content_required"})
    if len(new_text) > MAX_TEXT_CHARS:
        return _json(
            {
                "success": False,
                "error": "new_content_too_large",
                "max_chars": MAX_TEXT_CHARS,
            }
        )

    old_bytes, old_text = _read_utf8(target)
    old_sha = _sha_bytes(old_bytes)
    new_sha = _sha_text(new_text)

    plan = {
        "schema_version": 1,
        "action": "edit_note",
        "target_relative_path": target_rel,
        "target_canonical_path": str(target.resolve(strict=True)),
        "original_sha256": old_sha,
        "proposed_sha256": new_sha,
    }
    token = _plan_token(plan)
    _remember_preview(token, plan)

    return _json(
        {
            "success": True,
            "mode": "preview",
            "changed": old_sha != new_sha,
            "plan_token": token,
            "plan": plan,
            "diff": _unified_diff(
                old_text,
                new_text,
                f"vault/{target_rel}",
                f"vault/{target_rel}",
            ),
            "mutation_performed": False,
        }
    )


def preview_move_draft(params: Dict[str, Any], **_: Any) -> str:
    vault_root, inbox_root = _roots()

    source, source_rel = _resolve_under_root(
        inbox_root,
        params.get("source_draft"),
        must_exist=True,
    )
    target, target_rel = _resolve_under_root(
        vault_root,
        params.get("target_relative_path"),
        allow_missing_leaf=True,
    )
    _require_markdown(source_rel)
    _require_markdown(target_rel)

    if target.exists():
        return _json(
            {
                "success": False,
                "error": "target_already_exists",
                "target_relative_path": target_rel,
            }
        )

    source_bytes, source_text = _read_utf8(source)
    if "orion_draft: true" not in source_text or "status: draft" not in source_text:
        return _json({"success": False, "error": "source_is_not_orion_draft"})

    target_parent_real = target.parent.resolve(strict=True)
    plan = {
        "schema_version": 1,
        "action": "move_draft",
        "source_draft": source_rel,
        "source_canonical_path": str(source.resolve(strict=True)),
        "target_relative_path": target_rel,
        "target_parent_canonical_path": str(target_parent_real),
        "source_sha256": _sha_bytes(source_bytes),
        "target_state": "absent",
    }
    token = _plan_token(plan)
    _remember_preview(token, plan)

    return _json(
        {
            "success": True,
            "mode": "preview",
            "plan_token": token,
            "plan": plan,
            "diff": _unified_diff(
                "",
                source_text,
                "/dev/null",
                f"vault/{target_rel}",
            ),
            "mutation_performed": False,
        }
    )


def apply_plan_placeholder(params: Dict[str, Any], **_: Any) -> str:
    token = str(params.get("plan_token") or "").strip()
    plan = _lookup_preview(token) if token else None
    return _json(
        {
            "success": False,
            "error": "p5_01_mutation_not_authorized",
            "plan_known": bool(plan),
            "mutation_performed": False,
        }
    )


def _approval_summary(plan: Dict[str, Any]) -> str:
    action = plan.get("action", "vault_action")
    target = (
        plan.get("target_canonical_path")
        or plan.get("target_relative_path")
        or "<unknown target>"
    )

    if action == "edit_note":
        return (
            "Approve Orion vault edit preview? "
            f"Target: {target}. "
            f"Original SHA-256: {plan.get('original_sha256')}. "
            f"Proposed SHA-256: {plan.get('proposed_sha256')}. "
            "P5-01 handler remains fail-closed and will not mutate."
        )

    if action == "move_draft":
        return (
            "Approve Orion draft move preview? "
            f"Source: {plan.get('source_canonical_path')}. "
            f"Target: {plan.get('target_relative_path')}. "
            f"Source SHA-256: {plan.get('source_sha256')}. "
            "P5-01 handler remains fail-closed and will not mutate."
        )

    return "Approve Orion vault plan? P5-01 handler remains fail-closed and will not mutate."


def pre_tool_call(tool_name: str = "", args: Dict[str, Any] | None = None, **_: Any):
    if tool_name != APPLY_TOOL:
        return None

    params = args if isinstance(args, dict) else {}
    token = str(params.get("plan_token") or "").strip()
    plan = _lookup_preview(token) if token else None

    if not plan:
        return {
            "action": "block",
            "message": "P5-01 blocked: missing, unknown, or expired vault preview plan.",
        }

    return {
        "action": "approve",
        "message": _approval_summary(plan),
        "rule_key": f"orion_vault_plan:{token}",
    }


def register(ctx):
    preview_edit_schema = {
        "name": PREVIEW_EDIT_TOOL,
        "description": (
            "Read-only Orion vault edit preview. Returns exact diff, hashes, and "
            "an immutable plan token. Performs no filesystem mutation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_relative_path": {"type": "string"},
                "new_content": {"type": "string"},
            },
            "required": ["target_relative_path", "new_content"],
        },
    }

    preview_move_schema = {
        "name": PREVIEW_MOVE_TOOL,
        "description": (
            "Read-only Orion inbox-to-vault draft move preview. Returns exact "
            "target, diff, source hash, and immutable plan token. Performs no mutation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source_draft": {"type": "string"},
                "target_relative_path": {"type": "string"},
            },
            "required": ["source_draft", "target_relative_path"],
        },
    }

    apply_schema = {
        "name": APPLY_TOOL,
        "description": (
            "P5-01 approval-contract placeholder for a previously previewed Orion "
            "vault plan. The current handler intentionally refuses all mutation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "plan_token": {"type": "string"},
            },
            "required": ["plan_token"],
        },
    }

    ctx.register_tool(
        name=PREVIEW_EDIT_TOOL,
        toolset="orion_vault",
        schema=preview_edit_schema,
        handler=preview_edit,
    )
    ctx.register_tool(
        name=PREVIEW_MOVE_TOOL,
        toolset="orion_vault",
        schema=preview_move_schema,
        handler=preview_move_draft,
    )
    ctx.register_tool(
        name=APPLY_TOOL,
        toolset="orion_vault",
        schema=apply_schema,
        handler=apply_plan_placeholder,
    )
    ctx.register_hook("pre_tool_call", pre_tool_call)
