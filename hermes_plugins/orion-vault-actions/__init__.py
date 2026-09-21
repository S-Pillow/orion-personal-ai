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
import re
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
RECOMMEND_TOOL = "orion_vault_recommend_destination"
APPLY_TOOL = "orion_vault_apply_plan"

IAI_MCP_SERVER = "iai-mcp"
IAI_RECALL_TOOL = "memory_recall"
IAI_TEMPORAL_RECALL_TOOL = "memory_temporal_recall"

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

    ancestor = target.parent
    while not ancestor.exists() and ancestor != vault_root:
        ancestor = ancestor.parent
    target_parent_real = ancestor.resolve(strict=True)

    plan = {
        "schema_version": 1,
        "action": "move_draft",
        "source_draft": source_rel,
        "source_canonical_path": str(source.resolve(strict=True)),
        "target_relative_path": target_rel,
        "target_candidate_path": str(target.absolute()),
        "target_existing_ancestor_canonical_path": str(target_parent_real),
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
