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


def _probe_fresh_once_approval(
    plan_token: str, *, approval_request=None, redact=None
) -> bool:
    """Source-only handler-side approval candidate; never writes a file.

    An isolated test-only tool may call this to exercise Hermes dispatch. The
    registered apply handler remains a fail-closed placeholder. A future
    mutator would need separate final state checks, one-use plan consumption,
    atomic recovery, and qualified exact-diff display before any write.
    """
    try:
        plan = _lookup_preview(plan_token)
        if plan is None:
            return False
        message = _approval_summary(plan)
        if len(message.encode("utf-8")) > MAX_APPROVAL_MESSAGE_CHARS:
            return False
        if redact is None:
            from agent.redact import redact_sensitive_text

            redact = redact_sensitive_text
        if redact(message) != message:
            return False
        if approval_request is None:
            from tools.approval import request_tool_approval

            approval_request = request_tool_approval
    except Exception:
        return False

    # The random key is private to this invocation; a grant for the public
    # plan token or an earlier attempt cannot satisfy a fresh human response.
    rule_key = f"orion_vault_attempt:{plan_token}:{secrets.token_hex(16)}"
    pattern_key = f"plugin_rule:{rule_key}"
    with _APPROVAL_ATTEMPTS_LOCK:
        if len(_APPROVAL_ATTEMPTS) >= APPROVAL_ATTEMPT_LIMIT:
            return False
        _APPROVAL_ATTEMPTS[pattern_key] = {
            "description": message, "created": time.monotonic(), "once": False
        }
    try:
        result = approval_request(APPLY_TOOL, message, rule_key=rule_key)
        with _APPROVAL_ATTEMPTS_LOCK:
            observed = bool(_APPROVAL_ATTEMPTS[pattern_key]["once"])
        return bool(isinstance(result, dict) and result.get("approved") is True and observed)
    except Exception:
        return False
    finally:
        with _APPROVAL_ATTEMPTS_LOCK:
            _APPROVAL_ATTEMPTS.pop(pattern_key, None)



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


def _execute_disposable_plan_candidate(
    plan_token: str, *, failure_hook=None
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

    action = plan.get("action")
    recovery_dir: Path | None = None
    mutation_started = False

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

            source_bytes, source_text = _read_utf8(source)
            if _sha_bytes(source_bytes) != plan.get("source_sha256"):
                return _candidate_result(success=False, error="stale_source_hash")
            if "orion_draft: true" not in source_text or "status: draft" not in source_text:
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
            _candidate_checkpoint("move_after_recovery", failure_hook)

            if not _candidate_mark_consumed(plan_token):
                return _candidate_result(
                    success=False, error="plan_already_consumed",
                    recovery_dir=str(recovery_dir),
                )
            mutation_started = True
            _durable_write_exclusive(target, source_bytes)
            _candidate_checkpoint("move_after_target_create", failure_hook)

            if _sha_bytes(target.read_bytes()) != plan.get("source_sha256"):
                return _candidate_result(
                    success=False,
                    error="target_hash_mismatch",
                    mutation_performed=True,
                    recovery_required=True,
                    recovery_dir=str(recovery_dir),
                )

            latest_source = source.read_bytes()
            if _sha_bytes(latest_source) != plan.get("source_sha256"):
                cleanup_ok = False
                try:
                    if (_sha_bytes(target.read_bytes()) == plan.get("source_sha256")):
                        target.unlink()
                        cleanup_ok = True
                except OSError:
                    cleanup_ok = False
                return _candidate_result(
                    success=False,
                    error="source_changed_before_delete",
                    mutation_performed=True,
                    recovery_required=not cleanup_ok,
                    recovery_dir=str(recovery_dir),
                )

            _candidate_checkpoint("move_before_source_delete", failure_hook)
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
        return _candidate_result(
            success=False,
            error="exclusive_target_or_recovery_exists",
            mutation_performed=mutation_started,
            recovery_required=mutation_started,
            recovery_dir=str(recovery_dir) if recovery_dir else None,
        )
    except Exception as exc:
        return _candidate_result(
            success=False,
            error=f"candidate_failure:{type(exc).__name__}",
            mutation_performed=mutation_started,
            recovery_required=mutation_started,
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
