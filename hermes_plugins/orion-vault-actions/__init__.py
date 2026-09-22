"""Orion Phase 5 native vault-actions plugin, source-only candidate.

P5-01 is intentionally non-mutating. It provides read-only preview tools plus a
fail-closed placeholder apply tool so Hermes generic approval interception can
be tested before any live vault mutation is authorized.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import secrets
import stat
import threading
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict

PLUGIN_VERSION = "p5-01-0.1"
MAX_TEXT_CHARS = 100_000
PREVIEW_TTL_SECONDS = 600.0
PREVIEW_CACHE_LIMIT = 32
MAX_APPROVAL_MESSAGE_CHARS = 16_000
APPROVAL_ATTEMPT_LIMIT = 32
DISPOSABLE_MUTATION_FLAG = "ORION_P5_ALLOW_DISPOSABLE_MUTATION"
RECOVERY_ROOT_ENV = "ORION_P5_RECOVERY_ROOT"

DEFAULT_VAULT_ROOT = r"C:\Personal\Me"
DEFAULT_INBOX_ROOT = r"C:\Personal\Orion-Inbox"

PREVIEW_EDIT_TOOL = "orion_vault_preview_edit"
PREVIEW_MOVE_TOOL = "orion_vault_preview_move_draft"
RECOMMEND_TOOL = "orion_vault_recommend_destination"
APPLY_TOOL = "orion_vault_apply_plan"

IAI_MCP_SERVER = "iai-mcp"
IAI_RECALL_TOOL = "memory_recall"
IAI_TEMPORAL_RECALL_TOOL = "memory_temporal_recall"

_PREVIEWS: Dict[str, Dict[str, Any]] = {}
_PREVIEW_TIMES: Dict[str, float] = {}
_APPROVAL_ATTEMPTS: Dict[str, Dict[str, Any]] = {}
_APPROVAL_ATTEMPTS_LOCK = threading.Lock()
_CANDIDATE_CONSUMED_PLANS: set[str] = set()
_CANDIDATE_CONSUMED_LOCK = threading.Lock()


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
    records = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=old_name,
        tofile=new_name,
        lineterm="\n",
    )
    # difflib leaves an unterminated final content line without a delimiter.
    # Mark it explicitly so the approval preview cannot merge adjacent records.
    return "".join(
        record if record.endswith("\n") else record + "\n\\ No newline at end of file\n"
        for record in records
    )


def _roots() -> tuple[Path, Path]:
    vault = Path(os.environ.get("ORION_VAULT_ROOT", DEFAULT_VAULT_ROOT))
    inbox = Path(os.environ.get("ORION_INBOX_ROOT", DEFAULT_INBOX_ROOT))
    return vault, inbox


def _normalize_relative(raw: Any) -> PurePosixPath:
    if not isinstance(raw, str) or not raw:
        raise PathPolicyError("invalid_relative_path")

    normalized = raw.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(normalized)

    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise PathPolicyError("absolute_path_rejected")

    parts = normalized.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise PathPolicyError("path_traversal_rejected")

    # Validate each component using Windows rules even when fixture tests run
    # on another OS. ADS, device names, and trimmed names are never vault paths.
    forbidden = '<>:"|?*'
    devices = {"CON", "PRN", "AUX", "NUL"}
    devices.update(f"COM{i}" for i in range(1, 10))
    devices.update(f"LPT{i}" for i in range(1, 10))
    for part in parts:
        if (any(ord(char) < 32 or char in forbidden for char in part)
                or part.endswith((" ", "."))
                or part.split(".", 1)[0].upper() in devices):
            raise PathPolicyError("invalid_windows_component")

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
        if must_exist and not candidate.is_file():
            raise FileNotFoundError("path_not_found")
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


def _doc_tag(source_name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", source_name.lower()).strip("-")[:64]
    return f"doc:{slug or 'inline'}"


def _vault_doc_tag_index(vault_root: Path) -> Dict[str, list[str]]:
    if not vault_root.is_dir():
        raise PathPolicyError("root_missing")

    root_real = vault_root.resolve(strict=True)
    index: Dict[str, list[str]] = {}

    for dirpath, dirnames, filenames in os.walk(vault_root, followlinks=False):
        current = Path(dirpath)

        safe_dirs = []
        for name in dirnames:
            child = current / name
            if _is_reparse_point(child):
                continue
            try:
                _ensure_contained(root_real, child.resolve(strict=True))
            except (OSError, PathPolicyError):
                continue
            safe_dirs.append(name)
        dirnames[:] = safe_dirs

        for name in filenames:
            if not name.lower().endswith(".md"):
                continue

            path = current / name
            if _is_reparse_point(path):
                continue
            try:
                resolved = path.resolve(strict=True)
                _ensure_contained(root_real, resolved)
                relative = path.relative_to(vault_root).as_posix()
            except (OSError, ValueError, PathPolicyError):
                continue

            index.setdefault(_doc_tag(relative), []).append(relative)

    return index


def _mcp_result_payload(envelope: Any) -> Dict[str, Any] | None:
    if not isinstance(envelope, dict) or envelope.get("ok") is not True:
        return None

    payload = envelope.get("result")
    if isinstance(payload, dict):
        return payload

    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    return None


def _safe_positive_int(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def _recommend_destination_handler(ctx):
    def handle(params: Dict[str, Any], **_: Any) -> str:
        vault_root, inbox_root = _roots()

        source, source_rel = _resolve_under_root(
            inbox_root,
            params.get("source_draft"),
            must_exist=True,
        )
        _require_markdown(source_rel)

        source_bytes, source_text = _read_utf8(source)
        if len(source_text) > MAX_TEXT_CHARS:
            return _json(
                {
                    "success": False,
                    "error": "draft_too_large",
                    "max_chars": MAX_TEXT_CHARS,
                }
            )
        if "orion_draft: true" not in source_text or "status: draft" not in source_text:
            return _json({"success": False, "error": "source_is_not_orion_draft"})

        top = _safe_positive_int(params.get("top"), default=5, maximum=10)
        cue = source_text[:4000]

        try:
            recall_envelope = ctx.call_mcp(
                IAI_MCP_SERVER,
                IAI_RECALL_TOOL,
                {"cue": cue, "budget_tokens": 2000},
                timeout=30,
            )
        except Exception:
            return _json(
                {
                    "success": False,
                    "error": "iai_recall_unavailable",
                    "mutation_performed": False,
                }
            )

        recall = _mcp_result_payload(recall_envelope)
        if recall is None:
            return _json(
                {
                    "success": False,
                    "error": "iai_recall_invalid_response",
                    "mutation_performed": False,
                }
            )

        hits = [
            hit for hit in (recall.get("hits") or [])
            if isinstance(hit, dict) and str(hit.get("record_id") or "").strip()
        ]
        if not hits:
            return _json(
                {
                    "success": True,
                    "source_draft": source_rel,
                    "source_sha256": _sha_bytes(source_bytes),
                    "native_recall_hit_count": 0,
                    "recommendation_count": 0,
                    "recommendations": [],
                    "mutation_performed": False,
                }
            )

        metadata_limit = min(50, max(20, len(hits) * 4))
        try:
            metadata_envelope = ctx.call_mcp(
                IAI_MCP_SERVER,
                IAI_TEMPORAL_RECALL_TOOL,
                {"cue": cue, "limit": metadata_limit},
                timeout=30,
            )
        except Exception:
            return _json(
                {
                    "success": False,
                    "error": "iai_metadata_unavailable",
                    "mutation_performed": False,
                }
            )

        metadata = _mcp_result_payload(metadata_envelope)
        if metadata is None:
            return _json(
                {
                    "success": False,
                    "error": "iai_metadata_invalid_response",
                    "mutation_performed": False,
                }
            )

        tags_by_id: Dict[str, list[str]] = {}
        for item in metadata.get("hits") or []:
            if not isinstance(item, dict):
                continue
            record_id = str(item.get("id") or "").strip()
            tags = item.get("tags")
            if record_id and isinstance(tags, list):
                tags_by_id[record_id] = [
                    str(tag) for tag in tags if isinstance(tag, str)
                ]

        tag_index = _vault_doc_tag_index(vault_root)
        draft_name = PurePosixPath(source_rel).name
        recommendations = []
        seen_dirs = set()

        for native_rank, hit in enumerate(hits, start=1):
            record_id = str(hit.get("record_id") or "").strip()
            doc_tags = [
                tag for tag in tags_by_id.get(record_id, [])
                if tag.startswith("doc:")
            ]

            matched_source = None
            matched_tag = None
            for tag in doc_tags:
                paths = tag_index.get(tag, [])
                if len(paths) == 1:
                    matched_source = paths[0]
                    matched_tag = tag
                    break

            if not matched_source:
                continue

            parent = PurePosixPath(matched_source).parent.as_posix()
            if parent == ".":
                parent = ""

            directory_key = parent.casefold()
            if directory_key in seen_dirs:
                continue
            seen_dirs.add(directory_key)

            suggested = draft_name if not parent else f"{parent}/{draft_name}"
            recommendations.append(
                {
                    "rank": len(recommendations) + 1,
                    "directory": parent,
                    "suggested_target_relative_path": suggested,
                    "evidence_source_path": matched_source,
                    "evidence_doc_tag": matched_tag,
                    "record_id": record_id,
                    "native_recall_rank": native_rank,
                }
            )
            if len(recommendations) >= top:
                break

        return _json(
            {
                "success": True,
                "source_draft": source_rel,
                "source_sha256": _sha_bytes(source_bytes),
                "native_recall_hit_count": len(hits),
                "recommendation_count": len(recommendations),
                "recommendations": recommendations,
                "mutation_performed": False,
            }
        )

    return handle


def _remember_preview(
    token: str, plan: Dict[str, Any], *, diff: str, proposed_bytes: bytes
) -> None:
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

    # Keep the exact approved bytes and diff private to the bounded cache.
    # The public plan contains only identity and hashes, never replacement args.
    _PREVIEWS[token] = {
        **plan,
        "_approval_diff": diff,
        "_proposed_bytes": proposed_bytes,
    }
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
    diff = _unified_diff(
        old_text, new_text, f"vault/{target_rel}", f"vault/{target_rel}"
    )

    plan = {
        "schema_version": 1,
        "preview_nonce": secrets.token_hex(16),
        "action": "edit_note",
        "target_relative_path": target_rel,
        "target_canonical_path": str(target.resolve(strict=True)),
        "original_sha256": old_sha,
        "proposed_sha256": new_sha,
        "diff_sha256": _sha_text(diff),
    }
    token = _plan_token(plan)
    _remember_preview(token, plan, diff=diff, proposed_bytes=new_text.encode("utf-8"))

    return _json(
        {
            "success": True,
            "mode": "preview",
            "changed": old_sha != new_sha,
            "plan_token": token,
            "plan": plan,
            "diff": diff,
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
    source_file_id = None
    if os.name == "nt":
        try:
            source_file_id = _windows_path_file_identity(source)
        except Exception:
            return _json({
                "success": False,
                "error": "source_file_identity_unavailable",
                "mutation_performed": False,
            })
    if len(source_text) > MAX_TEXT_CHARS:
        return _json({"success": False, "error": "draft_too_large", "max_chars": MAX_TEXT_CHARS})
    if "orion_draft: true" not in source_text or "status: draft" not in source_text:
        return _json({"success": False, "error": "source_is_not_orion_draft"})

    ancestor = target.parent
    while not ancestor.exists() and ancestor != vault_root:
        ancestor = ancestor.parent
    target_parent_real = ancestor.resolve(strict=True)
    diff = _unified_diff("", source_text, "/dev/null", f"vault/{target_rel}")

    plan = {
        "schema_version": 1,
        "preview_nonce": secrets.token_hex(16),
        "action": "move_draft",
        "source_draft": source_rel,
        "source_canonical_path": str(source.resolve(strict=True)),
        "target_relative_path": target_rel,
        "target_candidate_path": str(target.absolute()),
        "target_canonical_path": str(target.resolve(strict=False)),
        "target_existing_ancestor_canonical_path": str(target_parent_real),
        "source_sha256": _sha_bytes(source_bytes),
        **({"source_file_id": source_file_id} if source_file_id else {}),
        "diff_sha256": _sha_text(diff),
        "target_state": "absent",
    }
    token = _plan_token(plan)
    _remember_preview(token, plan, diff=diff, proposed_bytes=source_bytes)

    return _json(
        {
            "success": True,
            "mode": "preview",
            "plan_token": token,
            "plan": plan,
            "diff": diff,
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
    target = plan.get("target_canonical_path")
    diff = plan.get("_approval_diff")
    proposed_bytes = plan.get("_proposed_bytes")
    if (not isinstance(target, str) or not target or not isinstance(diff, str)
            or not isinstance(proposed_bytes, bytes)
            or _sha_text(diff) != plan.get("diff_sha256")):
        raise ValueError("approval_preview_incomplete")

    if action == "edit_note":
        if _sha_bytes(proposed_bytes) != plan.get("proposed_sha256"):
            raise ValueError("proposed_content_mismatch")
        return (
            "Approve Orion vault edit preview? "
            f"Target: {target}. "
            f"Original SHA-256: {plan.get('original_sha256')}. "
            f"Proposed SHA-256: {plan.get('proposed_sha256')}.\n"
            f"Exact unified diff:\n{diff}\n"
            "Current apply handler remains fail-closed and will not mutate."
        )

    if action == "move_draft":
        if _sha_bytes(proposed_bytes) != plan.get("source_sha256"):
            raise ValueError("source_content_mismatch")
        return (
            "Approve Orion draft move preview? "
            f"Source: {plan.get('source_canonical_path')}. "
            f"Target: {target}. "
            f"Source SHA-256: {plan.get('source_sha256')}.\n"
            f"Exact unified diff:\n{diff}\n"
            "Current apply handler remains fail-closed and will not mutate."
        )

    if action == "restore_edit":
        restore_sha = plan.get("restore_sha256")
        if (
            _sha_bytes(proposed_bytes) != restore_sha
            or restore_sha != plan.get("recovery_backup_sha256")
        ):
            raise ValueError("restore_content_mismatch")
        return (
            "Approve Orion historical edit restore preview? "
            f"Recovery record: {plan.get('recovery_id')}. "
            f"Target: {target}. "
            f"Current SHA-256: {plan.get('current_sha256')}. "
            f"Restore SHA-256: {restore_sha}.\n"
            f"Exact unified diff:\n{diff}\n"
            "Restore execution is not registered and will not mutate."
        )

    if action == "restore_move_source":
        restore_sha = plan.get("restore_sha256")
        if (
            _sha_bytes(proposed_bytes) != restore_sha
            or restore_sha != plan.get("recovery_backup_sha256")
            or plan.get("source_state") != "absent"
        ):
            raise ValueError("restore_source_content_mismatch")
        return (
            "Approve Orion historical move-source restore preview? "
            f"Recovery record: {plan.get('recovery_id')}. "
            f"Inbox source to recreate: {target}. "
            f"Source state: absent. Restore SHA-256: {restore_sha}. "
            f"Reference vault target: {plan.get('reference_target_canonical_path')}.\n"
            f"Exact unified diff:\n{diff}\n"
            "Restore execution is not registered and will not mutate."
        )

    raise ValueError("unknown_vault_action")


def pre_tool_call(tool_name: str = "", args: Dict[str, Any] | None = None, **_: Any):
    if tool_name != APPLY_TOOL:
        return None

    try:
        params = args if isinstance(args, dict) else {}
        token = str(params.get("plan_token") or "").strip()
        plan = _lookup_preview(token) if token else None
        if plan:
            message = _approval_summary(plan)
            if len(message.encode("utf-8")) > MAX_APPROVAL_MESSAGE_CHARS:
                return {"action": "block", "message": "P5-02A blocked: exact approval diff is too large."}
    except Exception:
        # The installed Hermes hook registry logs callback exceptions and
        # otherwise omits their directive. Never let our callback throw.
        return {
            "action": "block",
            "message": "P5-02A blocked: vault approval preview could not be verified.",
        }
    if not plan:
        return {
            "action": "block",
            "message": "P5-01 blocked: missing, unknown, or expired vault preview plan.",
        }

    return {
        "action": "approve",
        "message": message,
        "rule_key": f"orion_vault_plan:{token}",
    }


def post_approval_response(
    pattern_key: str = "",
    description: str = "",
    choice: str = "",
    surface: str = "",
    coalesced: bool = False,
    **_: Any,
) -> None:
    """Observe a fresh one-time response for an internal apply attempt.

    This is not authorization by itself. The same handler that requested the
    approval must also receive an approved gate result and consume this mark.
    """
    if choice != "once" or surface not in ("cli", "gateway") or coalesced:
        return
    with _APPROVAL_ATTEMPTS_LOCK:
        pending = _APPROVAL_ATTEMPTS.get(pattern_key)
        if (pending is not None and pending["description"] == description
                and time.monotonic() - pending["created"] <= PREVIEW_TTL_SECONDS):
            pending["once"] = True
            pending["choice"] = choice
            pending["surface"] = surface


def _fresh_once_approval_evidence(
    plan_token: str, *, approval_request=None, redact=None
) -> Dict[str, Any]:
    """Return non-reusable evidence for one matched fresh human ONCE decision.

    The evidence is correlation metadata for a future durable receipt. It is
    deliberately insufficient to authorize any later action: no Hermes rule
    key/pattern key is returned, and the normal fresh approval attempt still
    has to exist in memory while the gate result is consumed.
    """
    failure = {
        "approved": False,
        "mutation_performed": False,
        "authorization_reusable": False,
    }
    try:
        plan = _lookup_preview(plan_token)
        if plan is None:
            return dict(failure, error="unknown_or_expired_plan")
        message = _approval_summary(plan)
        if len(message.encode("utf-8")) > MAX_APPROVAL_MESSAGE_CHARS:
            return dict(failure, error="approval_message_too_large")
        if redact is None:
            from agent.redact import redact_sensitive_text

            redact = redact_sensitive_text
        if redact(message) != message:
            return dict(failure, error="approval_message_redacted")
        if approval_request is None:
            from tools.approval import request_tool_approval

            approval_request = request_tool_approval
    except Exception:
        return dict(failure, error="approval_preparation_failed")

    attempt_id = secrets.token_hex(16)
    rule_key = f"orion_vault_attempt:{plan_token}:{secrets.token_hex(16)}"
    pattern_key = f"plugin_rule:{rule_key}"
    with _APPROVAL_ATTEMPTS_LOCK:
        if len(_APPROVAL_ATTEMPTS) >= APPROVAL_ATTEMPT_LIMIT:
            return dict(failure, error="approval_attempt_limit")
        _APPROVAL_ATTEMPTS[pattern_key] = {
            "attempt_id": attempt_id,
            "description": message,
            "created": time.monotonic(),
            "once": False,
            "choice": None,
            "surface": None,
        }

    try:
        result = approval_request(APPLY_TOOL, message, rule_key=rule_key)
        with _APPROVAL_ATTEMPTS_LOCK:
            pending = dict(_APPROVAL_ATTEMPTS.get(pattern_key) or {})
        approved = bool(
            isinstance(result, dict)
            and result.get("approved") is True
            and pending.get("once") is True
            and pending.get("choice") == "once"
            and pending.get("surface") in ("cli", "gateway")
        )
        if not approved:
            return dict(failure, error="fresh_once_not_observed")
        return {
            "approved": True,
            "mutation_performed": False,
            "authorization_reusable": False,
            "attempt_id": attempt_id,
            "plan_token": plan_token,
            "choice": "once",
            "surface": pending["surface"],
            "approval_message": message,
            "approval_message_sha256": _sha_text(message),
        }
    except Exception:
        return dict(failure, error="approval_gate_failed")
    finally:
        with _APPROVAL_ATTEMPTS_LOCK:
            _APPROVAL_ATTEMPTS.pop(pattern_key, None)


def _probe_fresh_once_approval(
    plan_token: str, *, approval_request=None, redact=None
) -> bool:
    """Compatibility bool wrapper around structured fresh-once evidence."""
    evidence = _fresh_once_approval_evidence(
        plan_token, approval_request=approval_request, redact=redact
    )
    return bool(evidence.get("approved") is True)


def _candidate_result(
    *,
    success: bool,
    error: str | None = None,
    mutation_performed: bool = False,
    recovery_required: bool = False,
    **extra: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": success,
        "mutation_performed": mutation_performed,
        "recovery_required": recovery_required,
    }
    if error:
        payload["error"] = error
    payload.update(extra)
    return payload


def _candidate_disposable_roots() -> tuple[Path, Path, Path]:
    """Return explicitly opted-in disposable roots for P5-02B source tests.

    This helper deliberately refuses the live default roots even when the
    opt-in flag is set. It is not a production authorization mechanism; it is
    a hard guard around the unregistered source candidate.
    """
    if os.environ.get(DISPOSABLE_MUTATION_FLAG) != "1":
        raise RuntimeError("disposable_mutation_not_enabled")

    raw_vault = os.environ.get("ORION_VAULT_ROOT")
    raw_inbox = os.environ.get("ORION_INBOX_ROOT")
    raw_recovery = os.environ.get(RECOVERY_ROOT_ENV)
    if not raw_vault or not raw_inbox or not raw_recovery:
        raise RuntimeError("disposable_roots_not_explicit")

    vault = Path(raw_vault)
    inbox = Path(raw_inbox)
    recovery = Path(raw_recovery)

    def normalized_identity(path: Path) -> str:
        return os.path.normcase(os.path.abspath(str(path.resolve(strict=False))))

    def windows_paths_overlap(raw_path: str, protected_root: str) -> bool:
        candidate = PureWindowsPath(raw_path)
        protected = PureWindowsPath(protected_root)
        for child, parent in ((candidate, protected), (protected, candidate)):
            try:
                child.relative_to(parent)
                return True
            except ValueError:
                continue
        return False

    if windows_paths_overlap(raw_vault, DEFAULT_VAULT_ROOT):
        raise RuntimeError("live_vault_root_overlap_rejected")
    if windows_paths_overlap(raw_inbox, DEFAULT_INBOX_ROOT):
        raise RuntimeError("live_inbox_root_overlap_rejected")
    if (windows_paths_overlap(raw_recovery, DEFAULT_VAULT_ROOT)
            or windows_paths_overlap(raw_recovery, DEFAULT_INBOX_ROOT)):
        raise RuntimeError("live_recovery_root_overlap_rejected")
    for root in (vault, inbox, recovery):
        if not root.is_dir():
            raise RuntimeError("disposable_root_missing")
        if _is_reparse_point(root):
            raise RuntimeError("disposable_root_reparse_rejected")

    vault_real = vault.resolve(strict=True)
    inbox_real = inbox.resolve(strict=True)
    recovery_real = recovery.resolve(strict=True)
    if windows_paths_overlap(str(vault_real), DEFAULT_VAULT_ROOT):
        raise RuntimeError("resolved_live_vault_overlap_rejected")
    if windows_paths_overlap(str(inbox_real), DEFAULT_INBOX_ROOT):
        raise RuntimeError("resolved_live_inbox_overlap_rejected")
    if (windows_paths_overlap(str(recovery_real), DEFAULT_VAULT_ROOT)
            or windows_paths_overlap(str(recovery_real), DEFAULT_INBOX_ROOT)):
        raise RuntimeError("resolved_live_recovery_overlap_rejected")
    identities = {
        normalized_identity(vault_real),
        normalized_identity(inbox_real),
        normalized_identity(recovery_real),
    }
    if len(identities) != 3:
        raise RuntimeError("disposable_roots_must_be_distinct")

    def contains(parent: Path, child: Path) -> bool:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False

    if (contains(vault_real, recovery_real)
            or contains(inbox_real, recovery_real)
            or contains(recovery_real, vault_real)
            or contains(recovery_real, inbox_real)):
        raise RuntimeError("recovery_root_must_be_disjoint")
    return vault, inbox, recovery


def _durable_write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _write_candidate_manifest(path: Path, payload: Dict[str, Any]) -> None:
    data = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8")
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(6))
    try:
        _durable_write_exclusive(temporary, data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _windows_file_identity_from_handle(handle) -> str:
    """Return the Windows volume + 128-bit file identity for an open handle."""
    import ctypes
    from ctypes import wintypes

    class FILE_ID_128(ctypes.Structure):
        _fields_ = [("Identifier", ctypes.c_ubyte * 16)]

    class FILE_ID_INFO(ctypes.Structure):
        _fields_ = [
            ("VolumeSerialNumber", ctypes.c_ulonglong),
            ("FileId", FILE_ID_128),
        ]

    get_info = ctypes.WinDLL("kernel32", use_last_error=True).GetFileInformationByHandleEx
    get_info.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    get_info.restype = wintypes.BOOL
    info = FILE_ID_INFO()
    # FILE_INFO_BY_HANDLE_CLASS.FileIdInfo == 0x12.
    if not get_info(handle, 0x12, ctypes.byref(info), ctypes.sizeof(info)):
        code = ctypes.get_last_error()
        raise OSError(code, "GetFileInformationByHandleEx(FileIdInfo) failed")
    file_id = bytes(info.FileId.Identifier).hex()
    return f"{int(info.VolumeSerialNumber):016x}:{file_id}"


def _windows_handle_is_reparse_point(handle) -> bool:
    import ctypes
    from ctypes import wintypes

    class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", wintypes.DWORD),
            ("ReparseTag", wintypes.DWORD),
        ]

    get_info = ctypes.WinDLL("kernel32", use_last_error=True).GetFileInformationByHandleEx
    get_info.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    get_info.restype = wintypes.BOOL
    info = FILE_ATTRIBUTE_TAG_INFO()
    # FILE_INFO_BY_HANDLE_CLASS.FileAttributeTagInfo == 9.
    if not get_info(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        code = ctypes.get_last_error()
        raise OSError(code, "GetFileInformationByHandleEx(FileAttributeTagInfo) failed")
    return bool(int(info.FileAttributes) & 0x400)


def _windows_open_file_handle(
    path: Path, *, desired_access: int, share_mode: int
):
    import ctypes
    from ctypes import wintypes

    create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    # FILE_FLAG_OPEN_REPARSE_POINT keeps a raced-in reparse object from being
    # transparently followed after the path-based containment check.
    handle = create_file(
        str(path),
        desired_access,
        share_mode,
        None,
        3,  # OPEN_EXISTING
        0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        code = ctypes.get_last_error()
        raise OSError(code, f"CreateFileW failed for {path}")
    return handle


def _windows_close_file_handle(handle) -> None:
    import ctypes
    from ctypes import wintypes

    close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    if not close_handle(handle):
        code = ctypes.get_last_error()
        raise OSError(code, "CloseHandle failed")


def _windows_path_file_identity(path: Path) -> str:
    """Read one path identity without retaining a lock/share restriction."""
    if os.name != "nt":
        raise RuntimeError("windows_identity_requires_windows")

    handle = _windows_open_file_handle(
        path,
        desired_access=0x80000000,  # GENERIC_READ
        share_mode=0x1 | 0x2 | 0x4,  # READ | WRITE | DELETE
    )
    try:
        if _windows_handle_is_reparse_point(handle):
            raise PathPolicyError("reparse_point_rejected")
        return _windows_file_identity_from_handle(handle)
    finally:
        _windows_close_file_handle(handle)


class _WindowsSourceGuard:
    """Hold the approved source object through target verification + deletion."""

    def __init__(self, path: Path):
        if os.name != "nt":
            raise RuntimeError("windows_source_guard_requires_windows")
        self.path = path
        self.handle = _windows_open_file_handle(
            path,
            # GENERIC_READ | DELETE. New conflicting write/delete/rename opens
            # are denied while this handle is alive because only READ is shared.
            desired_access=0x80000000 | 0x00010000,
            share_mode=0x1,  # FILE_SHARE_READ
        )
        try:
            if _windows_handle_is_reparse_point(self.handle):
                raise PathPolicyError("reparse_point_rejected")
            self.file_identity = _windows_file_identity_from_handle(self.handle)
        except Exception:
            try:
                _windows_close_file_handle(self.handle)
            finally:
                self.handle = None
            raise

    def read_bytes(self) -> bytes:
        if self.handle is None:
            raise RuntimeError("source_guard_closed")

        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_size = kernel32.GetFileSizeEx
        get_size.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
        get_size.restype = wintypes.BOOL
        set_pointer = kernel32.SetFilePointerEx
        set_pointer.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            wintypes.DWORD,
        ]
        set_pointer.restype = wintypes.BOOL
        read_file = kernel32.ReadFile
        read_file.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        read_file.restype = wintypes.BOOL

        size = ctypes.c_longlong()
        if not get_size(self.handle, ctypes.byref(size)):
            code = ctypes.get_last_error()
            raise OSError(code, "GetFileSizeEx failed")
        if size.value < 0 or size.value > MAX_TEXT_CHARS * 4:
            raise PathPolicyError("draft_too_large")

        new_position = ctypes.c_longlong()
        if not set_pointer(
            self.handle, ctypes.c_longlong(0), ctypes.byref(new_position), 0
        ):
            code = ctypes.get_last_error()
            raise OSError(code, "SetFilePointerEx failed")

        remaining = int(size.value)
        chunks = []
        while remaining:
            count = min(remaining, 64 * 1024)
            buffer = ctypes.create_string_buffer(count)
            read = wintypes.DWORD()
            if not read_file(
                self.handle, buffer, count, ctypes.byref(read), None
            ):
                code = ctypes.get_last_error()
                raise OSError(code, "ReadFile failed")
            if read.value == 0:
                raise OSError("unexpected_eof")
            chunks.append(buffer.raw[: read.value])
            remaining -= int(read.value)
        return b"".join(chunks)

    def mark_delete(self) -> None:
        if self.handle is None:
            raise RuntimeError("source_guard_closed")

        import ctypes
        from ctypes import wintypes

        class FILE_DISPOSITION_INFO(ctypes.Structure):
            _fields_ = [("DeleteFile", ctypes.c_ubyte)]

        set_info = ctypes.WinDLL(
            "kernel32", use_last_error=True
        ).SetFileInformationByHandle
        set_info.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        set_info.restype = wintypes.BOOL
        disposition = FILE_DISPOSITION_INFO(1)
        # FILE_INFO_BY_HANDLE_CLASS.FileDispositionInfo == 4.
        if not set_info(
            self.handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)
        ):
            code = ctypes.get_last_error()
            raise OSError(code, "SetFileInformationByHandle(FileDispositionInfo) failed")

    def close(self) -> None:
        if self.handle is None:
            return
        handle, self.handle = self.handle, None
        _windows_close_file_handle(handle)


def _candidate_replace_file(target: Path, replacement: Path) -> None:
    """Replace one existing file; use native ReplaceFileW on Windows."""
    if os.name != "nt":
        os.replace(replacement, target)
        return

    import ctypes

    replace_file = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
    replace_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    replace_file.restype = ctypes.c_int
    if not replace_file(str(target), str(replacement), None, 0, None, None):
        code = ctypes.get_last_error()
        raise OSError(code, "ReplaceFileW failed")


def _candidate_checkpoint(name: str, failure_hook=None) -> None:
    if failure_hook is not None:
        failure_hook(name)


def _candidate_mark_consumed(token: str) -> bool:
    with _CANDIDATE_CONSUMED_LOCK:
        if token in _CANDIDATE_CONSUMED_PLANS:
            return False
        _CANDIDATE_CONSUMED_PLANS.add(token)
        return True


def _candidate_recovery_dir(recovery_root: Path, token: str) -> Path:
    path = recovery_root / token
    path.mkdir(mode=0o700)
    return path


def _candidate_hash_under_root(
    root: Path, relative: Any
) -> tuple[str | None, str | None]:
    """Return (sha256, error) for one contained regular file, or (None, None) if absent."""
    try:
        path, _ = _resolve_under_root(root, relative, must_exist=True)
    except FileNotFoundError:
        return None, None
    except Exception as exc:
        return None, f"path_error:{type(exc).__name__}"
    try:
        return _sha_bytes(path.read_bytes()), None
    except Exception as exc:
        return None, f"read_error:{type(exc).__name__}"


def _inspect_disposable_recovery_candidate(plan_token: str) -> Dict[str, Any]:
    """Read-only reconciliation of one disposable recovery record.

    The manifest is evidence, not truth. Prepared records are classified from
    current source/target hashes so restart/crash recovery does not assume
    whether the protected filesystem step happened.
    """
    try:
        vault_root, inbox_root, recovery_root = _candidate_disposable_roots()
    except Exception as exc:
        return _candidate_result(success=False, error=str(exc))

    if not isinstance(plan_token, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_token):
        return _candidate_result(success=False, error="invalid_recovery_id")

    recovery_dir = recovery_root / plan_token
    try:
        if not recovery_dir.is_dir() or _is_reparse_point(recovery_dir):
            return _candidate_result(success=False, error="recovery_record_missing")
        recovery_real = recovery_dir.resolve(strict=True)
        _ensure_contained(recovery_root.resolve(strict=True), recovery_real)

        manifest_path = recovery_dir / "manifest.json"
        if (not manifest_path.is_file() or _is_reparse_point(manifest_path)):
            return _candidate_result(success=False, error="recovery_manifest_missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest_not_object")
    except json.JSONDecodeError:
        return _candidate_result(success=False, error="recovery_manifest_invalid_json")
    except Exception as exc:
        return _candidate_result(
            success=False, error=f"recovery_manifest_error:{type(exc).__name__}"
        )

    action = manifest.get("action")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("plan_token") != plan_token
        or manifest.get("state") not in ("prepared", "committed")
        or action not in (
            "edit_note", "move_draft", "restore_edit", "restore_move_source"
        )
    ):
        return _candidate_result(success=False, error="recovery_manifest_invalid")

    if action == "restore_edit":
        origin_recovery_id = manifest.get("origin_recovery_id")
        before_sha = manifest.get("before_sha256")
        after_sha = manifest.get("after_sha256")
        target_rel = manifest.get("target_relative_path")
        artifact_name = manifest.get("backup_file")
        if (
            not re.fullmatch(r"[0-9a-f]{64}", str(origin_recovery_id or ""))
            or artifact_name != "before_restore.bin"
            or not isinstance(before_sha, str)
            or not isinstance(after_sha, str)
        ):
            return _candidate_result(success=False, error="recovery_manifest_invalid")
        artifact = recovery_dir / artifact_name
        if not artifact.is_file() or _is_reparse_point(artifact):
            return _candidate_result(success=False, error="recovery_backup_missing")
        backup_sha = _sha_bytes(artifact.read_bytes())
        if backup_sha != before_sha:
            return _candidate_result(success=False, error="recovery_backup_hash_mismatch")

        target_sha, target_error = _candidate_hash_under_root(vault_root, target_rel)
        if target_error:
            return _candidate_result(success=False, error=target_error)
        if manifest["state"] == "committed":
            classification = (
                "committed" if target_sha == after_sha else "committed_then_changed"
            )
            recovery_required = False
        elif target_sha == before_sha:
            classification = "prepared_no_effect"
            recovery_required = False
        elif target_sha == after_sha:
            classification = "applied_unfinalized"
            recovery_required = True
        else:
            classification = "divergent_unresolved"
            recovery_required = True

        return _candidate_result(
            success=True,
            mutation_performed=False,
            recovery_required=recovery_required,
            recovery_id=plan_token,
            origin_recovery_id=origin_recovery_id,
            action=action,
            manifest_state=manifest["state"],
            classification=classification,
            backup_sha256=backup_sha,
            target_sha256=target_sha,
            before_sha256=before_sha,
            after_sha256=after_sha,
            target_relative_path=target_rel,
        )

    if action == "restore_move_source":
        origin_recovery_id = manifest.get("origin_recovery_id")
        source_rel = manifest.get("source_draft")
        after_sha = manifest.get("after_sha256")
        artifact_name = manifest.get("evidence_file")
        if (
            not re.fullmatch(r"[0-9a-f]{64}", str(origin_recovery_id or ""))
            or manifest.get("before_state") != "absent"
            or artifact_name != "created_source.bin"
            or not isinstance(after_sha, str)
        ):
            return _candidate_result(success=False, error="recovery_manifest_invalid")
        artifact = recovery_dir / artifact_name
        if not artifact.is_file() or _is_reparse_point(artifact):
            return _candidate_result(success=False, error="recovery_backup_missing")
        backup_sha = _sha_bytes(artifact.read_bytes())
        if backup_sha != after_sha:
            return _candidate_result(success=False, error="recovery_backup_hash_mismatch")

        source_current, source_error = _candidate_hash_under_root(
            inbox_root, source_rel
        )
        if source_error:
            return _candidate_result(success=False, error=source_error)
        if manifest["state"] == "committed":
            classification = (
                "committed"
                if source_current == after_sha
                else "committed_then_changed"
            )
            recovery_required = False
        elif source_current is None:
            classification = "prepared_no_effect"
            recovery_required = False
        elif source_current == after_sha:
            classification = "applied_unfinalized"
            recovery_required = True
        else:
            classification = "divergent_unresolved"
            recovery_required = True

        return _candidate_result(
            success=True,
            mutation_performed=False,
            recovery_required=recovery_required,
            recovery_id=plan_token,
            origin_recovery_id=origin_recovery_id,
            action=action,
            manifest_state=manifest["state"],
            classification=classification,
            backup_sha256=backup_sha,
            source_sha256=source_current,
            after_sha256=after_sha,
            source_draft=source_rel,
        )

    backup_name = manifest.get("backup_file")
    expected_backup = "original.bin" if action == "edit_note" else "source.bin"
    if backup_name != expected_backup:
        return _candidate_result(success=False, error="recovery_backup_name_invalid")
    backup = recovery_dir / backup_name
    if not backup.is_file() or _is_reparse_point(backup):
        return _candidate_result(success=False, error="recovery_backup_missing")

    try:
        backup_sha = _sha_bytes(backup.read_bytes())
    except Exception as exc:
        return _candidate_result(
            success=False, error=f"recovery_backup_error:{type(exc).__name__}"
        )

    if action == "edit_note":
        before_sha = manifest.get("before_sha256")
        after_sha = manifest.get("after_sha256")
        target_rel = manifest.get("target_relative_path")
        if (
            not isinstance(before_sha, str)
            or not isinstance(after_sha, str)
            or backup_sha != before_sha
        ):
            return _candidate_result(success=False, error="recovery_backup_hash_mismatch")

        target_sha, target_error = _candidate_hash_under_root(vault_root, target_rel)
        if target_error:
            return _candidate_result(success=False, error=target_error)

        if manifest["state"] == "committed":
            classification = (
                "committed"
                if target_sha == after_sha
                else "committed_then_changed"
            )
            recovery_required = False
        elif target_sha == before_sha:
            classification = "prepared_no_effect"
            recovery_required = False
        elif target_sha == after_sha:
            classification = "applied_unfinalized"
            recovery_required = True
        else:
            classification = "divergent_unresolved"
            recovery_required = True

        return _candidate_result(
            success=True,
            mutation_performed=False,
            recovery_required=recovery_required,
            recovery_id=plan_token,
            action=action,
            manifest_state=manifest["state"],
            classification=classification,
            backup_sha256=backup_sha,
            target_sha256=target_sha,
            before_sha256=before_sha,
            after_sha256=after_sha,
            target_relative_path=target_rel,
        )

    source_sha = manifest.get("source_sha256")
    source_rel = manifest.get("source_draft")
    target_rel = manifest.get("target_relative_path")
    if not isinstance(source_sha, str) or backup_sha != source_sha:
        return _candidate_result(success=False, error="recovery_backup_hash_mismatch")

    source_current, source_error = _candidate_hash_under_root(inbox_root, source_rel)
    target_current, target_error = _candidate_hash_under_root(vault_root, target_rel)
    if source_error:
        return _candidate_result(success=False, error=source_error)
    if target_error:
        return _candidate_result(success=False, error=target_error)

    if manifest["state"] == "committed":
        classification = (
            "committed"
            if source_current is None and target_current == source_sha
            else "committed_then_changed"
        )
        recovery_required = False
    elif source_current == source_sha and target_current is None:
        classification = "prepared_no_effect"
        recovery_required = False
    elif source_current == source_sha and target_current == source_sha:
        classification = "duplicate_unresolved"
        recovery_required = True
    elif source_current is None and target_current == source_sha:
        classification = "applied_unfinalized"
        recovery_required = True
    else:
        classification = "divergent_unresolved"
        recovery_required = True

    return _candidate_result(
        success=True,
        mutation_performed=False,
        recovery_required=recovery_required,
        recovery_id=plan_token,
        action=action,
        manifest_state=manifest["state"],
        classification=classification,
        backup_sha256=backup_sha,
        source_sha256=source_current,
        target_sha256=target_current,
        approved_source_sha256=source_sha,
        source_draft=source_rel,
        target_relative_path=target_rel,
    )


def _read_disposable_recovery_backup(
    recovery_root: Path, recovery_id: str, backup_name: str
) -> tuple[Path, bytes]:
    recovery_dir = recovery_root / recovery_id
    if not recovery_dir.is_dir() or _is_reparse_point(recovery_dir):
        raise FileNotFoundError("recovery_record_missing")
    _ensure_contained(
        recovery_root.resolve(strict=True), recovery_dir.resolve(strict=True)
    )
    backup = recovery_dir / backup_name
    if not backup.is_file() or _is_reparse_point(backup):
        raise FileNotFoundError("recovery_backup_missing")
    return backup, backup.read_bytes()


def _preview_disposable_restore_candidate(recovery_id: str) -> Dict[str, Any]:
    """Build a historical restore preview without mutating any file.

    Only already-committed recovery records are eligible. Prepared/unresolved
    records belong to recovery-resolution flows, not historical restore.
    """
    try:
        vault_root, inbox_root, recovery_root = _candidate_disposable_roots()
    except Exception as exc:
        return _candidate_result(success=False, error=str(exc))

    inspected = _inspect_disposable_recovery_candidate(recovery_id)
    if not inspected.get("success"):
        return _candidate_result(
            success=False,
            error=inspected.get("error", "recovery_inspection_failed"),
        )
    if inspected.get("manifest_state") != "committed":
        return _candidate_result(
            success=False,
            error="historical_restore_requires_committed_record",
        )

    action = inspected.get("action")
    try:
        if action == "edit_note":
            target_rel = inspected.get("target_relative_path")
            target, normalized_rel = _resolve_under_root(
                vault_root, target_rel, must_exist=True
            )
            _require_markdown(normalized_rel)
            current_bytes, current_text = _read_utf8(target)
            _backup_path, backup_bytes = _read_disposable_recovery_backup(
                recovery_root, recovery_id, "original.bin"
            )
            try:
                backup_text = backup_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return _candidate_result(
                    success=False, error="recovery_backup_utf8_required"
                )

            backup_sha = _sha_bytes(backup_bytes)
            if backup_sha != inspected.get("backup_sha256"):
                return _candidate_result(
                    success=False, error="recovery_backup_hash_mismatch"
                )

            current_sha = _sha_bytes(current_bytes)
            target_file_id = None
            if os.name == "nt":
                try:
                    target_file_id = _windows_path_file_identity(target)
                except Exception:
                    return _candidate_result(
                        success=False, error="restore_target_file_identity_unavailable"
                    )

            diff = _unified_diff(
                current_text,
                backup_text,
                f"vault/{normalized_rel}",
                f"vault/{normalized_rel}",
            )
            plan = {
                "schema_version": 1,
                "preview_nonce": secrets.token_hex(16),
                "action": "restore_edit",
                "recovery_id": recovery_id,
                "recovery_action": "edit_note",
                "recovery_manifest_state": "committed",
                "target_relative_path": normalized_rel,
                "target_canonical_path": str(target.resolve(strict=True)),
                "current_sha256": current_sha,
                "restore_sha256": backup_sha,
                "recovery_backup_sha256": backup_sha,
                **(
                    {"target_file_id": target_file_id}
                    if target_file_id else {}
                ),
                "diff_sha256": _sha_text(diff),
            }
            token = _plan_token(plan)
            _remember_preview(
                token, plan, diff=diff, proposed_bytes=backup_bytes
            )
            return _candidate_result(
                success=True,
                mutation_performed=False,
                mode="preview",
                restore_kind="historical_edit",
                plan_token=token,
                plan=plan,
                diff=diff,
                changed=current_sha != backup_sha,
            )

        if action == "move_draft":
            source_rel = inspected.get("source_draft")
            source, normalized_rel = _resolve_under_root(
                inbox_root, source_rel, allow_missing_leaf=True
            )
            _require_markdown(normalized_rel)
            if source.exists() or os.path.lexists(source):
                return _candidate_result(
                    success=False, error="restore_source_exists"
                )
            if not source.parent.is_dir():
                return _candidate_result(
                    success=False, error="restore_source_parent_missing"
                )
            if _is_reparse_point(source.parent):
                return _candidate_result(
                    success=False, error="restore_source_parent_reparse_rejected"
                )

            _backup_path, backup_bytes = _read_disposable_recovery_backup(
                recovery_root, recovery_id, "source.bin"
            )
            try:
                backup_text = backup_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return _candidate_result(
                    success=False, error="recovery_backup_utf8_required"
                )
            if (
                "orion_draft: true" not in backup_text
                or "status: draft" not in backup_text
            ):
                return _candidate_result(
                    success=False, error="recovery_backup_not_orion_draft"
                )

            backup_sha = _sha_bytes(backup_bytes)
            if backup_sha != inspected.get("backup_sha256"):
                return _candidate_result(
                    success=False, error="recovery_backup_hash_mismatch"
                )

            target_rel = inspected.get("target_relative_path")
            target_path, _ = _resolve_under_root(
                vault_root, target_rel, allow_missing_leaf=True
            )
            if target_path.exists():
                if not target_path.is_file():
                    return _candidate_result(
                        success=False, error="restore_reference_target_not_file"
                    )
                target_sha = _sha_bytes(target_path.read_bytes())
                target_state = "present"
            else:
                target_sha = None
                target_state = "absent"
            diff = _unified_diff(
                "",
                backup_text,
                "/dev/null",
                f"inbox/{normalized_rel}",
            )
            plan = {
                "schema_version": 1,
                "preview_nonce": secrets.token_hex(16),
                "action": "restore_move_source",
                "recovery_id": recovery_id,
                "recovery_action": "move_draft",
                "recovery_manifest_state": "committed",
                "source_draft": normalized_rel,
                "source_state": "absent",
                "target_relative_path": normalized_rel,
                "target_canonical_path": str(source.resolve(strict=False)),
                "source_parent_canonical_path": str(
                    source.parent.resolve(strict=True)
                ),
                "restore_sha256": backup_sha,
                "recovery_backup_sha256": backup_sha,
                "reference_target_relative_path": target_rel,
                "reference_target_canonical_path": str(
                    target_path.resolve(strict=False)
                ),
                "reference_target_state": target_state,
                "reference_target_sha256": target_sha,
                "diff_sha256": _sha_text(diff),
            }
            token = _plan_token(plan)
            _remember_preview(
                token, plan, diff=diff, proposed_bytes=backup_bytes
            )
            return _candidate_result(
                success=True,
                mutation_performed=False,
                mode="preview",
                restore_kind="historical_move_source",
                plan_token=token,
                plan=plan,
                diff=diff,
                changed=True,
            )

        return _candidate_result(
            success=False, error="unsupported_recovery_action"
        )
    except FileNotFoundError as exc:
        return _candidate_result(success=False, error=str(exc))
    except Exception as exc:
        return _candidate_result(
            success=False, error=f"restore_preview_error:{type(exc).__name__}"
        )


def _revalidate_disposable_restore_preview(plan_token: str) -> Dict[str, Any]:
    """Read-only final-state check for a previously built restore preview."""
    plan = _lookup_preview(plan_token)
    if plan is None:
        return _candidate_result(success=False, error="unknown_or_expired_plan")
    if plan.get("action") not in ("restore_edit", "restore_move_source"):
        return _candidate_result(success=False, error="not_restore_preview")

    try:
        _approval_summary(plan)
        vault_root, inbox_root, recovery_root = _candidate_disposable_roots()
    except Exception as exc:
        return _candidate_result(success=False, error=str(exc))

    recovery_id = plan.get("recovery_id")
    inspected = _inspect_disposable_recovery_candidate(recovery_id)
    if (
        not inspected.get("success")
        or inspected.get("manifest_state") != "committed"
    ):
        return _candidate_result(
            success=False, error="restore_recovery_record_changed"
        )

    try:
        backup_name = (
            "original.bin"
            if plan.get("action") == "restore_edit"
            else "source.bin"
        )
        _backup_path, backup_bytes = _read_disposable_recovery_backup(
            recovery_root, recovery_id, backup_name
        )
        if (
            _sha_bytes(backup_bytes) != plan.get("restore_sha256")
            or _sha_bytes(backup_bytes) != plan.get("recovery_backup_sha256")
        ):
            return _candidate_result(
                success=False, error="restore_backup_changed"
            )

        if plan.get("action") == "restore_edit":
            target, normalized_rel = _resolve_under_root(
                vault_root, plan.get("target_relative_path"), must_exist=True
            )
            if (
                normalized_rel != plan.get("target_relative_path")
                or str(target.resolve(strict=True))
                != plan.get("target_canonical_path")
            ):
                return _candidate_result(
                    success=False, error="restore_target_identity_changed"
                )
            if os.name == "nt" and plan.get("target_file_id"):
                try:
                    current_file_id = _windows_path_file_identity(target)
                except Exception:
                    return _candidate_result(
                        success=False,
                        error="restore_target_file_identity_unavailable",
                    )
                if current_file_id != plan.get("target_file_id"):
                    return _candidate_result(
                        success=False, error="restore_target_file_id_changed"
                    )
            if _sha_bytes(target.read_bytes()) != plan.get("current_sha256"):
                return _candidate_result(
                    success=False, error="restore_current_state_changed"
                )
        else:
            source, normalized_rel = _resolve_under_root(
                inbox_root, plan.get("source_draft"), allow_missing_leaf=True
            )
            if normalized_rel != plan.get("source_draft"):
                return _candidate_result(
                    success=False, error="restore_source_identity_changed"
                )
            if str(source.resolve(strict=False)) != plan.get("target_canonical_path"):
                return _candidate_result(
                    success=False, error="restore_source_identity_changed"
                )
            if (
                not source.parent.is_dir()
                or _is_reparse_point(source.parent)
                or str(source.parent.resolve(strict=True))
                != plan.get("source_parent_canonical_path")
            ):
                return _candidate_result(
                    success=False, error="restore_source_parent_changed"
                )
            if source.exists() or os.path.lexists(source):
                return _candidate_result(
                    success=False, error="restore_source_no_longer_absent"
                )

        return _candidate_result(
            success=True,
            mutation_performed=False,
            recovery_required=False,
            valid=True,
            plan_token=plan_token,
            recovery_id=recovery_id,
            action=plan.get("action"),
        )
    except FileNotFoundError:
        return _candidate_result(
            success=False, error="restore_required_path_missing"
        )
    except Exception as exc:
        return _candidate_result(
            success=False, error=f"restore_revalidation_error:{type(exc).__name__}"
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _public_plan_snapshot(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Persist only the public immutable plan fields, never cached bytes/diff."""
    return {
        key: value
        for key, value in plan.items()
        if not str(key).startswith("_")
    }


def _validate_candidate_approval_evidence(
    plan_token: str, plan: Dict[str, Any], evidence: Any
) -> Dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ValueError("approval_evidence_required")
    if (
        evidence.get("approved") is not True
        or evidence.get("authorization_reusable") is not False
        or evidence.get("plan_token") != plan_token
        or evidence.get("choice") != "once"
        or evidence.get("surface") not in ("cli", "gateway")
        or not re.fullmatch(r"[0-9a-f]{32}", str(evidence.get("attempt_id") or ""))
    ):
        raise ValueError("approval_evidence_invalid")

    message = _approval_summary(plan)
    if (
        evidence.get("approval_message") != message
        or evidence.get("approval_message_sha256") != _sha_text(message)
    ):
        raise ValueError("approval_evidence_message_mismatch")
    return {
        "attempt_id": evidence["attempt_id"],
        "surface": evidence["surface"],
        "choice": "once",
        "approval_message": message,
        "approval_message_sha256": evidence["approval_message_sha256"],
        "authorization_reusable": False,
    }


def _candidate_receipt_payload(
    *,
    recovery_id: str,
    plan_token: str,
    plan: Dict[str, Any],
    approval: Dict[str, Any],
    backup_file: str,
    backup_sha256: str,
    state: str,
    created_at_utc: str,
    final_classification: str | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema_version": 1,
        "receipt_type": "orion_vault_action",
        "recovery_id": recovery_id,
        "plan_token": plan_token,
        "plan": _public_plan_snapshot(plan),
        "approval": dict(approval),
        "backup_file": backup_file,
        "backup_sha256": backup_sha256,
        "state": state,
        "created_at_utc": created_at_utc,
        "updated_at_utc": _utc_now_iso(),
    }
    if plan.get("action") in ("restore_edit", "restore_move_source"):
        payload["origin_recovery_id"] = plan.get("recovery_id")
    if final_classification:
        payload["final_classification"] = final_classification
    return payload


def _write_candidate_receipt_prepared(
    recovery_dir: Path,
    *,
    plan_token: str,
    plan: Dict[str, Any],
    approval: Dict[str, Any],
    backup_file: str,
    backup_sha256: str,
) -> None:
    path = recovery_dir / "receipt.json"
    created = _utc_now_iso()
    payload = _candidate_receipt_payload(
        recovery_id=plan_token,
        plan_token=plan_token,
        plan=plan,
        approval=approval,
        backup_file=backup_file,
        backup_sha256=backup_sha256,
        state="prepared",
        created_at_utc=created,
    )
    data = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8")
    _durable_write_exclusive(path, data)


def _commit_candidate_receipt(
    recovery_dir: Path, *, final_classification: str
) -> None:
    path = recovery_dir / "receipt.json"
    if not path.is_file() or _is_reparse_point(path):
        raise RuntimeError("receipt_missing")
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("receipt_invalid_json") from exc
    if (
        not isinstance(current, dict)
        or current.get("schema_version") != 1
        or current.get("state") != "prepared"
    ):
        raise RuntimeError("receipt_invalid_state")
    payload = dict(current)
    payload["state"] = "committed"
    payload["final_classification"] = final_classification
    payload["updated_at_utc"] = _utc_now_iso()
    _write_candidate_manifest(path, payload)


def _receipt_approval_message_matches_plan(
    plan: Dict[str, Any], message: str
) -> bool:
    """Bind persisted approval text back to the immutable public plan."""
    action = plan.get("action")
    if action == "edit_note":
        prefix = (
            "Approve Orion vault edit preview? "
            f"Target: {plan.get('target_canonical_path')}. "
            f"Original SHA-256: {plan.get('original_sha256')}. "
            f"Proposed SHA-256: {plan.get('proposed_sha256')}.\n"
            "Exact unified diff:\n"
        )
        suffix = "\nCurrent apply handler remains fail-closed and will not mutate."
    elif action == "move_draft":
        prefix = (
            "Approve Orion draft move preview? "
            f"Source: {plan.get('source_canonical_path')}. "
            f"Target: {plan.get('target_canonical_path')}. "
            f"Source SHA-256: {plan.get('source_sha256')}.\n"
            "Exact unified diff:\n"
        )
        suffix = "\nCurrent apply handler remains fail-closed and will not mutate."
    elif action == "restore_edit":
        prefix = (
            "Approve Orion historical edit restore preview? "
            f"Recovery record: {plan.get('recovery_id')}. "
            f"Target: {plan.get('target_canonical_path')}. "
            f"Current SHA-256: {plan.get('current_sha256')}. "
            f"Restore SHA-256: {plan.get('restore_sha256')}.\n"
            "Exact unified diff:\n"
        )
        suffix = "\nRestore execution is not registered and will not mutate."
    elif action == "restore_move_source":
        prefix = (
            "Approve Orion historical move-source restore preview? "
            f"Recovery record: {plan.get('recovery_id')}. "
            f"Inbox source to recreate: {plan.get('target_canonical_path')}. "
            f"Source state: absent. Restore SHA-256: {plan.get('restore_sha256')}. "
            f"Reference vault target: {plan.get('reference_target_canonical_path')}.\n"
            "Exact unified diff:\n"
        )
        suffix = "\nRestore execution is not registered and will not mutate."
    else:
        return False

    if not message.startswith(prefix) or not message.endswith(suffix):
        return False
    diff = message[len(prefix):len(message) - len(suffix)]
    return _sha_text(diff) == plan.get("diff_sha256")


def _inspect_disposable_receipt_candidate(recovery_id: str) -> Dict[str, Any]:
    """Read-only restart-safe validation of a durable correlation receipt."""
    try:
        _vault_root, _inbox_root, recovery_root = _candidate_disposable_roots()
    except Exception as exc:
        return _candidate_result(success=False, error=str(exc))

    if not isinstance(recovery_id, str) or not re.fullmatch(
        r"[0-9a-f]{64}", recovery_id
    ):
        return _candidate_result(success=False, error="invalid_recovery_id")

    recovery_dir = recovery_root / recovery_id
    receipt_path = recovery_dir / "receipt.json"
    try:
        if (
            not recovery_dir.is_dir()
            or _is_reparse_point(recovery_dir)
            or not receipt_path.is_file()
            or _is_reparse_point(receipt_path)
        ):
            return _candidate_result(success=False, error="receipt_missing")
        _ensure_contained(
            recovery_root.resolve(strict=True), recovery_dir.resolve(strict=True)
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _candidate_result(success=False, error="receipt_invalid_json")
    except Exception as exc:
        return _candidate_result(
            success=False, error=f"receipt_read_error:{type(exc).__name__}"
        )

    if not isinstance(receipt, dict):
        return _candidate_result(success=False, error="receipt_invalid")
    plan = receipt.get("plan")
    approval = receipt.get("approval")
    if (
        receipt.get("schema_version") != 1
        or receipt.get("receipt_type") != "orion_vault_action"
        or receipt.get("recovery_id") != recovery_id
        or receipt.get("plan_token") != recovery_id
        or receipt.get("state") not in ("prepared", "committed")
        or not isinstance(plan, dict)
        or _plan_token(plan) != recovery_id
        or not isinstance(approval, dict)
        or approval.get("choice") != "once"
        or approval.get("surface") not in ("cli", "gateway")
        or approval.get("authorization_reusable") is not False
        or not isinstance(approval.get("approval_message"), str)
        or len(approval.get("approval_message", "").encode("utf-8"))
            > MAX_APPROVAL_MESSAGE_CHARS
        or not re.fullmatch(
            r"[0-9a-f]{32}", str(approval.get("attempt_id") or "")
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            str(approval.get("approval_message_sha256") or ""),
        )
        or _sha_text(approval.get("approval_message", ""))
            != approval.get("approval_message_sha256")
        or not _receipt_approval_message_matches_plan(
            plan, approval.get("approval_message", "")
        )
        or (
            receipt.get("state") == "committed"
            and receipt.get("final_classification") != "committed"
        )
        or (
            receipt.get("state") == "prepared"
            and receipt.get("final_classification") is not None
        )
        or (
            plan.get("action") in ("restore_edit", "restore_move_source")
            and receipt.get("origin_recovery_id") != plan.get("recovery_id")
        )
    ):
        return _candidate_result(success=False, error="receipt_invalid")

    backup_name = receipt.get("backup_file")
    backup = recovery_dir / str(backup_name or "")
    if (
        backup_name not in (
            "original.bin", "source.bin", "before_restore.bin", "created_source.bin"
        )
        or not backup.is_file()
        or _is_reparse_point(backup)
    ):
        return _candidate_result(success=False, error="receipt_backup_missing")
    backup_sha = _sha_bytes(backup.read_bytes())
    if backup_sha != receipt.get("backup_sha256"):
        return _candidate_result(
            success=False, error="receipt_backup_hash_mismatch"
        )

    recovery = _inspect_disposable_recovery_candidate(recovery_id)
    if not recovery.get("success"):
        return _candidate_result(
            success=False,
            error="receipt_recovery_record_invalid",
        )
    if (
        recovery.get("action") != plan.get("action")
        or recovery.get("backup_sha256") != backup_sha
    ):
        return _candidate_result(
            success=False, error="receipt_recovery_correlation_mismatch"
        )

    current_classification = recovery.get("classification")
    receipt_reconciliation_required = receipt.get("state") != "committed"
    recovery_required = bool(recovery.get("recovery_required"))
    if receipt_reconciliation_required and current_classification == "committed":
        current_classification = "applied_unfinalized"
        recovery_required = True

    return _candidate_result(
        success=True,
        mutation_performed=False,
        recovery_required=recovery_required,
        correlation_valid=True,
        authorization_reusable=False,
        recovery_id=recovery_id,
        plan_token=recovery_id,
        action=plan.get("action"),
        receipt_state=receipt.get("state"),
        receipt_finalized=receipt.get("state") == "committed",
        receipt_reconciliation_required=receipt_reconciliation_required,
        final_classification=receipt.get("final_classification"),
        current_classification=current_classification,
        approval_message_sha256=approval.get("approval_message_sha256"),
        approval_attempt_id=approval.get("attempt_id"),
        approval_surface=approval.get("surface"),
        approval_choice=approval.get("choice"),
        backup_sha256=backup_sha,
    )


def _execute_disposable_plan_candidate(
    plan_token: str, *, failure_hook=None, approval_evidence=None
) -> Dict[str, Any]:
    """P5-02B unregistered mutation prototype for disposable roots only.

    The public APPLY_TOOL does not call this function. It exists so edit/move
    durability, stale-state, recovery, and race behavior can be exercised
    before any live mutation handler is authorized.
    """
    try:
        vault_root, inbox_root, recovery_root = _candidate_disposable_roots()
        plan = _lookup_preview(plan_token)
        if plan is None:
            return _candidate_result(success=False, error="unknown_or_expired_plan")
        _approval_summary(plan)  # validates exact cached diff/proposed bytes.
        with _CANDIDATE_CONSUMED_LOCK:
            if plan_token in _CANDIDATE_CONSUMED_PLANS:
                return _candidate_result(success=False, error="plan_already_consumed")
    except Exception as exc:
        return _candidate_result(success=False, error=str(exc))

    receipt_approval = None
    if approval_evidence is not None:
        try:
            receipt_approval = _validate_candidate_approval_evidence(
                plan_token, plan, approval_evidence
            )
        except Exception as exc:
            return _candidate_result(success=False, error=str(exc))

    action = plan.get("action")
    recovery_dir: Path | None = None
    mutation_started = False
    source_guard = None

    try:
        if action == "edit_note":
            target, target_rel = _resolve_under_root(
                vault_root, plan.get("target_relative_path"), must_exist=True
            )
            if str(target.resolve(strict=True)) != plan.get("target_canonical_path"):
                return _candidate_result(success=False, error="target_identity_changed")
            old_bytes, _ = _read_utf8(target)
            if _sha_bytes(old_bytes) != plan.get("original_sha256"):
                return _candidate_result(success=False, error="stale_original_hash")
            proposed = plan.get("_proposed_bytes")
            if not isinstance(proposed, bytes):
                return _candidate_result(success=False, error="proposed_bytes_missing")
            if _sha_bytes(proposed) != plan.get("proposed_sha256"):
                return _candidate_result(success=False, error="proposed_hash_mismatch")

            recovery_dir = _candidate_recovery_dir(recovery_root, plan_token)
            backup = recovery_dir / "original.bin"
            manifest = recovery_dir / "manifest.json"
            _durable_write_exclusive(backup, old_bytes)
            _write_candidate_manifest(manifest, {
                "schema_version": 1,
                "state": "prepared",
                "action": action,
                "plan_token": plan_token,
                "target_relative_path": target_rel,
                "before_sha256": plan.get("original_sha256"),
                "after_sha256": plan.get("proposed_sha256"),
                "backup_file": "original.bin",
            })
            if receipt_approval is not None:
                _write_candidate_receipt_prepared(
                    recovery_dir,
                    plan_token=plan_token,
                    plan=plan,
                    approval=receipt_approval,
                    backup_file="original.bin",
                    backup_sha256=_sha_bytes(old_bytes),
                )
            _candidate_checkpoint("edit_after_recovery", failure_hook)

            temporary = target.with_name(
                f".{target.name}.orion-{plan_token[:12]}-{secrets.token_hex(4)}.tmp"
            )
            try:
                _durable_write_exclusive(temporary, proposed)
                _candidate_checkpoint("edit_before_replace", failure_hook)
                if not _candidate_mark_consumed(plan_token):
                    return _candidate_result(
                        success=False, error="plan_already_consumed",
                        recovery_dir=str(recovery_dir),
                    )
                mutation_started = True
                _candidate_replace_file(target, temporary)
                _candidate_checkpoint("edit_after_replace", failure_hook)
            finally:
                if temporary.exists():
                    temporary.unlink()

            current = target.read_bytes()
            if _sha_bytes(current) != plan.get("proposed_sha256"):
                return _candidate_result(
                    success=False,
                    error="post_write_hash_mismatch",
                    mutation_performed=True,
                    recovery_required=True,
                    recovery_dir=str(recovery_dir),
                )
            _write_candidate_manifest(manifest, {
                "schema_version": 1,
                "state": "committed",
                "action": action,
                "plan_token": plan_token,
                "target_relative_path": target_rel,
                "before_sha256": plan.get("original_sha256"),
                "after_sha256": plan.get("proposed_sha256"),
                "backup_file": "original.bin",
            })
            if receipt_approval is not None:
                _commit_candidate_receipt(
                    recovery_dir, final_classification="committed"
                )
            return _candidate_result(
                success=True,
                mutation_performed=True,
                recovery_dir=str(recovery_dir),
                target_relative_path=target_rel,
                after_sha256=plan.get("proposed_sha256"),
            )

        if action == "move_draft":
            source, source_rel = _resolve_under_root(
                inbox_root, plan.get("source_draft"), must_exist=True
            )
            target, target_rel = _resolve_under_root(
                vault_root, plan.get("target_relative_path"), allow_missing_leaf=True
            )
            if str(source.resolve(strict=True)) != plan.get("source_canonical_path"):
                return _candidate_result(success=False, error="source_identity_changed")
            if str(target.resolve(strict=False)) != plan.get("target_canonical_path"):
                return _candidate_result(success=False, error="target_identity_changed")
            if not target.parent.is_dir():
                return _candidate_result(success=False, error="target_parent_missing")
            if _is_reparse_point(target.parent):
                return _candidate_result(success=False, error="target_parent_reparse_rejected")
            if target.exists() or os.path.lexists(target):
                return _candidate_result(success=False, error="target_already_exists")

            if os.name == "nt":
                try:
                    source_guard = _WindowsSourceGuard(source)
                except Exception:
                    return _candidate_result(
                        success=False, error="source_handle_unavailable"
                    )
                expected_file_id = plan.get("source_file_id")
                if (not expected_file_id
                        or source_guard.file_identity != expected_file_id):
                    try:
                        source_guard.close()
                    except Exception:
                        pass
                    return _candidate_result(
                        success=False, error="source_file_id_changed"
                    )
                source_bytes = source_guard.read_bytes()
                try:
                    source_text = source_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    source_guard.close()
                    return _candidate_result(
                        success=False, error="utf8_required"
                    )
            else:
                source_bytes, source_text = _read_utf8(source)

            if _sha_bytes(source_bytes) != plan.get("source_sha256"):
                if source_guard is not None:
                    source_guard.close()
                return _candidate_result(success=False, error="stale_source_hash")
            if "orion_draft: true" not in source_text or "status: draft" not in source_text:
                if source_guard is not None:
                    source_guard.close()
                return _candidate_result(success=False, error="source_is_not_orion_draft")

            recovery_dir = _candidate_recovery_dir(recovery_root, plan_token)
            backup = recovery_dir / "source.bin"
            manifest = recovery_dir / "manifest.json"
            _durable_write_exclusive(backup, source_bytes)
            _write_candidate_manifest(manifest, {
                "schema_version": 1,
                "state": "prepared",
                "action": action,
                "plan_token": plan_token,
                "source_draft": source_rel,
                "target_relative_path": target_rel,
                "source_sha256": plan.get("source_sha256"),
                "backup_file": "source.bin",
            })
            if receipt_approval is not None:
                _write_candidate_receipt_prepared(
                    recovery_dir,
                    plan_token=plan_token,
                    plan=plan,
                    approval=receipt_approval,
                    backup_file="source.bin",
                    backup_sha256=_sha_bytes(source_bytes),
                )
            _candidate_checkpoint("move_after_recovery", failure_hook)

            if not _candidate_mark_consumed(plan_token):
                if source_guard is not None:
                    source_guard.close()
                    source_guard = None
                return _candidate_result(
                    success=False, error="plan_already_consumed",
                    recovery_dir=str(recovery_dir),
                )
            mutation_started = True
            _durable_write_exclusive(target, source_bytes)
            _candidate_checkpoint("move_after_target_create", failure_hook)

            if _sha_bytes(target.read_bytes()) != plan.get("source_sha256"):
                if source_guard is not None:
                    source_guard.close()
                    source_guard = None
                return _candidate_result(
                    success=False,
                    error="target_hash_mismatch",
                    mutation_performed=True,
                    recovery_required=True,
                    recovery_dir=str(recovery_dir),
                )

            latest_source = (
                source_guard.read_bytes()
                if source_guard is not None
                else source.read_bytes()
            )
            if _sha_bytes(latest_source) != plan.get("source_sha256"):
                cleanup_ok = False
                try:
                    if (_sha_bytes(target.read_bytes()) == plan.get("source_sha256")):
                        target.unlink()
                        cleanup_ok = True
                except OSError:
                    cleanup_ok = False
                if source_guard is not None:
                    try:
                        source_guard.close()
                    except Exception:
                        cleanup_ok = False
                    source_guard = None
                return _candidate_result(
                    success=False,
                    error="source_changed_before_delete",
                    mutation_performed=True,
                    recovery_required=not cleanup_ok,
                    recovery_dir=str(recovery_dir),
                )

            _candidate_checkpoint("move_before_source_delete", failure_hook)
            if source_guard is not None:
                source_guard.mark_delete()
                _candidate_checkpoint("move_after_delete_mark", failure_hook)
                source_guard.close()
                source_guard = None
            else:
                source.unlink()
            _candidate_checkpoint("move_after_source_delete", failure_hook)

            if source.exists() or not target.is_file():
                return _candidate_result(
                    success=False,
                    error="move_postcondition_failed",
                    mutation_performed=True,
                    recovery_required=True,
                    recovery_dir=str(recovery_dir),
                )
            if _sha_bytes(target.read_bytes()) != plan.get("source_sha256"):
                return _candidate_result(
                    success=False,
                    error="move_post_hash_mismatch",
                    mutation_performed=True,
                    recovery_required=True,
                    recovery_dir=str(recovery_dir),
                )

            _write_candidate_manifest(manifest, {
                "schema_version": 1,
                "state": "committed",
                "action": action,
                "plan_token": plan_token,
                "source_draft": source_rel,
                "target_relative_path": target_rel,
                "source_sha256": plan.get("source_sha256"),
                "backup_file": "source.bin",
            })
            if receipt_approval is not None:
                _commit_candidate_receipt(
                    recovery_dir, final_classification="committed"
                )
            return _candidate_result(
                success=True,
                mutation_performed=True,
                recovery_dir=str(recovery_dir),
                source_draft=source_rel,
                target_relative_path=target_rel,
                after_sha256=plan.get("source_sha256"),
            )

        return _candidate_result(success=False, error="unsupported_action")
    except FileExistsError:
        close_failed = False
        try:
            if source_guard is not None:
                source_guard.close()
                source_guard = None
        except Exception:
            close_failed = True
        return _candidate_result(
            success=False,
            error="exclusive_target_or_recovery_exists",
            mutation_performed=mutation_started,
            recovery_required=mutation_started or close_failed,
            recovery_dir=str(recovery_dir) if recovery_dir else None,
        )
    except Exception as exc:
        close_failed = False
        try:
            if source_guard is not None:
                source_guard.close()
                source_guard = None
        except Exception:
            close_failed = True
        return _candidate_result(
            success=False,
            error=f"candidate_failure:{type(exc).__name__}",
            mutation_performed=mutation_started,
            recovery_required=mutation_started or close_failed,
            recovery_dir=str(recovery_dir) if recovery_dir else None,
        )


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

    recommend_schema = {
        "name": RECOMMEND_TOOL,
        "description": (
            "Read-only Orion destination recommendation for an inbox draft. "
            "Uses native iai memory_recall ordering and maps iai document tags "
            "back to exactly one current contained Markdown source. Ambiguous "
            "or missing mappings are omitted. Performs no vault/inbox mutation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source_draft": {"type": "string"},
                "top": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
            },
            "required": ["source_draft"],
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
        name=RECOMMEND_TOOL,
        toolset="orion_vault",
        schema=recommend_schema,
        handler=_recommend_destination_handler(ctx),
    )
    ctx.register_tool(
        name=APPLY_TOOL,
        toolset="orion_vault",
        schema=apply_schema,
        handler=apply_plan_placeholder,
    )
    ctx.register_hook("pre_tool_call", pre_tool_call)
    ctx.register_hook("post_approval_response", post_approval_response)
