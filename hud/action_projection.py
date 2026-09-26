"""Browser-safe P5-03A2 action/evidence projection.

This module is deliberately authority-free. It normalizes already-observed
Hermes/plugin evidence into a bounded presentation schema. It does not execute
tools, resolve approvals, persist action truth, inspect the vault, or infer
unsupported protected-action lifecycle stages.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

SCHEMA_VERSION = "orion.action-projection.v1"
EVIDENCE_SCHEMA_VERSION = "orion.action-evidence.v1"

CANONICAL_APPROVAL_CHOICES = ("once", "session", "always", "deny")
PREVIEW_TOOLS = frozenset({
    "orion_vault_preview_edit",
    "orion_vault_preview_move_draft",
    "orion_vault_preview_delete",
})
APPLY_TOOL = "orion_vault_apply_plan"
VAULT_TOOLS = PREVIEW_TOOLS | {APPLY_TOOL}

STALE_ERRORS = frozenset({
    "stale_original_hash",
    "stale_source_hash",
    "target_identity_changed",
    "target_file_id_changed",
    "source_identity_changed",
    "source_file_id_changed",
    "target_already_exists",
    "delete_target_identity_changed",
    "delete_target_file_id_changed",
    "delete_target_hash_changed",
    "delete_target_changed_before_delete",
    "restore_recovery_record_changed",
    "restore_backup_changed",
    "restore_target_identity_changed",
    "restore_target_file_id_changed",
    "restore_current_state_changed",
    "restore_source_identity_changed",
    "restore_source_parent_changed",
    "restore_source_no_longer_absent",
})

REFUSAL_ERRORS = frozenset({
    "invalid_production_mutation_mode",
    "production_mutation_not_enabled",
    "unknown_or_expired_plan",
    "plan_already_consumed",
    "approval_evidence_required",
    "approval_evidence_already_consumed",
    "approval_attempt_limit",
    "approval_message_redacted",
    "approval_message_too_large",
    "approval_preparation_failed",
    "fresh_once_not_observed",
    "approval_gate_failed",
})

SAFE_RESULT_FIELDS = (
    "action",
    "plan_token",
    "recovery_id",
    "origin_recovery_id",
    "target_relative_path",
    "source_draft",
    "target_canonical_path",
    "source_canonical_path",
    "reference_target_canonical_path",
    "original_sha256",
    "proposed_sha256",
    "source_sha256",
    "target_sha256",
    "before_sha256",
    "after_sha256",
    "current_sha256",
    "restore_sha256",
    "target_file_id",
    "source_file_id",
    "changed",
)
SAFE_PLAN_FIELDS = (
    "action",
    "target_relative_path",
    "source_draft",
    "target_canonical_path",
    "source_canonical_path",
    "reference_target_canonical_path",
    "original_sha256",
    "proposed_sha256",
    "source_sha256",
    "target_sha256",
    "current_sha256",
    "restore_sha256",
    "target_file_id",
    "source_file_id",
    "target_state",
    "source_state",
    "diff_sha256",
)

_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_CODE_RE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MAX_TEXT = 4096
_MAX_APPROVAL_TEXT = 256 * 1024
_MAX_MESSAGE_TEXT = 256 * 1024


def _bounded_text(value: Any, limit: int = _MAX_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = value.replace("\x00", "").strip()
    return cleaned[:limit]


def _exact_text(value: Any, limit: int = _MAX_APPROVAL_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    if "\x00" in value or len(value.encode("utf-8", errors="ignore")) > limit:
        return ""
    return value


def _safe_id(value: Any) -> str:
    text = str(value or "").strip()
    return text if _ID_RE.fullmatch(text) else ""


def _safe_code(value: Any) -> str:
    text = str(value or "").strip()
    return text if _CODE_RE.fullmatch(text) else ""


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _bounded_text(value, 1024)
    return None


def _common(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("session_id", "run_id", "message_id", "tool_call_id"):
        value = _safe_id(data.get(key))
        if value:
            out[key] = value
    for key in ("seq", "ts", "timestamp"):
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = value
    return out


def _runtime(runtime: Any) -> dict[str, str]:
    if not isinstance(runtime, dict):
        return {}
    out: dict[str, str] = {}
    for source_key, target_key in (
        ("provider", "provider"),
        ("model", "model"),
        ("route_source", "route_source"),
    ):
        value = _bounded_text(runtime.get(source_key), 160)
        if value:
            out[target_key] = value
    return out


def _projection(
    state: str,
    source: str,
    *,
    durability: str,
    common: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "state": state,
        "source": source,
        "durability": durability,
    }
    if common:
        payload.update(common)
    for key, value in extra.items():
        if value is not None and value != "":
            payload[key] = value
    return payload


def _approval_choices(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [choice for choice in CANONICAL_APPROVAL_CHOICES if choice in value]


def project_approval_request(data: dict[str, Any]) -> dict[str, Any]:
    common = _common(data)
    raw_run_id = data.get("run_id")
    run_id_exact = (
        isinstance(raw_run_id, str)
        and bool(raw_run_id)
        and _safe_id(raw_run_id) == raw_run_id
    )
    if not run_id_exact:
        common.pop("run_id", None)
    if "command" in data:
        raw_command = data.get("command")
    else:
        raw_command = data.get("tool_name")
    command = _exact_text(raw_command, 240)
    command_exact = bool(
        isinstance(raw_command, str)
        and command
        and command == raw_command
        and raw_command == raw_command.strip()
    )
    description = _exact_text(data.get("description"))
    choices = _approval_choices(data.get("choices"))
    run_id = raw_run_id if run_id_exact else None
    exact_ready = bool(
        run_id and command_exact and description and choices
    )
    unavailable_reason = (
        "approval_run_id_unavailable"
        if not run_id
        else "canonical_approval_content_unavailable"
    )
    projection = _projection(
        "approval_requested" if exact_ready else "unavailable",
        "hermes_approval_event",
        durability="transient_live",
        common=common,
        command=command,
        description=description,
        choices=choices if exact_ready else [],
        reason=None if exact_ready else unavailable_reason,
    )
    return {
        **common,
        "event": "approval.request",
        **({"command": command} if command else {}),
        **({"description": description} if description else {}),
        "choices": choices if exact_ready else [],
        "projection": projection,
    }


def project_approval_response(
    run_id: str,
    requested_choice: str,
    payload: Any,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("object") != "hermes.run.approval_response":
        return None
    if _safe_id(run_id) != run_id:
        return None
    observed_run = payload.get("run_id")
    if not isinstance(observed_run, str) or observed_run != run_id:
        return None
    choice = payload.get("choice")
    requested = requested_choice
    if (
        not isinstance(choice, str)
        or not isinstance(requested, str)
        or choice not in CANONICAL_APPROVAL_CHOICES
        or requested not in CANONICAL_APPROVAL_CHOICES
        or choice != requested
    ):
        return None
    resolved = payload.get("resolved")
    if not isinstance(resolved, int) or isinstance(resolved, bool) or resolved <= 0:
        return None
    state = "approval_denied" if choice == "deny" else "approval_accepted"
    projection = _projection(
        state,
        "hermes_approval_response",
        durability="turn_scoped",
        common={"run_id": run_id},
        decision=choice,
        resolved=resolved,
        execution_proven=False,
    )
    return {
        "object": "orion.approval_decision",
        "run_id": run_id,
        "choice": choice,
        "resolved": resolved,
        "execution_proven": False,
        "projection": projection,
    }


def _json_object(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return None
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _tool_call_name_map(messages: Iterable[Any]) -> dict[str, str]:
    names: dict[str, str] = {}
    for message in messages:
        if not isinstance(message, dict):
            continue
        calls = message.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            call_id = _safe_id(call.get("id"))
            function = call.get("function")
            name = ""
            if isinstance(function, dict):
                name = _safe_code(function.get("name"))
            if call_id and name:
                names[call_id] = name
    return names


def _tool_name(message: dict[str, Any], names: dict[str, str]) -> str:
    direct = _safe_code(message.get("tool_name") or message.get("name"))
    if direct:
        return direct
    call_id = _safe_id(message.get("tool_call_id"))
    return names.get(call_id, "")


def _copy_allowed_fields(result: dict[str, Any], out: dict[str, Any]) -> None:
    for key in SAFE_RESULT_FIELDS:
        value = result.get(key)
        if key.endswith("sha256"):
            if isinstance(value, str) and _HASH_RE.fullmatch(value):
                out[key] = value.lower()
            continue
        if key.endswith("_file_id"):
            safe = _bounded_text(value, 256)
            if safe:
                out[key] = safe
            continue
        safe = _safe_scalar(value)
        if safe is not None and safe != "":
            out[key] = safe


def _copy_plan_fields(plan: Any, out: dict[str, Any]) -> None:
    if not isinstance(plan, dict):
        return
    for key in SAFE_PLAN_FIELDS:
        value = plan.get(key)
        if key.endswith("sha256"):
            if isinstance(value, str) and _HASH_RE.fullmatch(value):
                out[key] = value.lower()
            continue
        if key.endswith("_file_id"):
            safe = _bounded_text(value, 256)
            if safe:
                out[key] = safe
            continue
        safe = _safe_scalar(value)
        if safe is not None and safe != "":
            out[key] = safe


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(_HASH_RE.fullmatch(value))


def _present_text(value: Any, limit: int = 4096) -> bool:
    return bool(_bounded_text(value, limit))


def _present_text_exact(value: Any, limit: int = 1024) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and _bounded_text(value, limit) == value
    )


def _preview_evidence_complete(
    tool_name: str,
    result: dict[str, Any],
) -> bool:
    plan_token = result.get("plan_token")
    plan = result.get("plan")
    if not _valid_hash(plan_token) or not isinstance(plan, dict):
        return False
    if "diff" not in result or not isinstance(result.get("diff"), str):
        return False
    diff = _exact_text(result.get("diff"))
    if diff != result.get("diff"):
        return False
    expected_action = {
        "orion_vault_preview_edit": "edit_note",
        "orion_vault_preview_move_draft": "move_draft",
        "orion_vault_preview_delete": "delete_note",
    }.get(tool_name)
    if not expected_action or plan.get("action") != expected_action:
        return False
    diff_sha = plan.get("diff_sha256")
    if (
        not _valid_hash(diff_sha)
        or hashlib.sha256(diff.encode("utf-8")).hexdigest() != diff_sha.lower()
    ):
        return False

    if expected_action == "edit_note":
        return (
            _present_text_exact(plan.get("target_relative_path"))
            and _present_text_exact(plan.get("target_canonical_path"))
            and _valid_hash(plan.get("original_sha256"))
            and _valid_hash(plan.get("proposed_sha256"))
        )
    if expected_action == "move_draft":
        return (
            _present_text_exact(plan.get("source_draft"))
            and _present_text_exact(plan.get("source_canonical_path"))
            and _present_text_exact(plan.get("target_relative_path"))
            and _present_text_exact(plan.get("target_canonical_path"))
            and _valid_hash(plan.get("source_sha256"))
            and plan.get("target_state") == "absent"
        )
    return (
        _present_text_exact(plan.get("target_relative_path"))
        and _present_text_exact(plan.get("target_canonical_path"))
        and _valid_hash(plan.get("target_sha256"))
        and plan.get("target_state") == "present"
    )


def _success_evidence_complete(result: dict[str, Any]) -> bool:
    if result.get("error") not in (None, ""):
        return False
    action = _safe_code(result.get("action"))
    recovery_id = result.get("recovery_id")
    if not _valid_hash(recovery_id):
        return False

    if action in {"edit_note", "delete_note"}:
        return _present_text(result.get("target_relative_path"))
    if action == "move_draft":
        return (
            _present_text(result.get("source_draft"))
            and _present_text(result.get("target_relative_path"))
        )
    if action in {"restore_edit", "restore_move_source"}:
        return _valid_hash(result.get("origin_recovery_id"))
    return False


def project_tool_message(
    message: dict[str, Any],
    *,
    name_map: dict[str, str] | None = None,
    hydrated: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return None
    names = name_map or {}
    tool_name = _tool_name(message, names)
    if tool_name not in VAULT_TOOLS:
        return None
    result = _json_object(message.get("content"))
    if result is None:
        return _projection(
            "unknown",
            "hermes_tool_result",
            durability="completed_record",
            common=_common(message),
            tool_name=tool_name,
            reason="structured_result_unavailable",
            hydrated=hydrated,
        )

    common = _common(message)
    if tool_name in PREVIEW_TOOLS:
        preview_error_present = "error" in result
        preview_error = _safe_code(result.get("error"))
        preview_recovery_conflict = (
            "recovery_required" in result
            and result.get("recovery_required") is not False
        )
        preview_claim = (
            result.get("success") is True
            and result.get("mode") == "preview"
            and result.get("mutation_performed") is False
            and not preview_error_present
            and not preview_recovery_conflict
        )
        is_preview = preview_claim and _preview_evidence_complete(
            tool_name, result
        )
        if is_preview:
            state = "unavailable" if hydrated else "preview_ready"
            out = _projection(
                state,
                "vault_preview_result",
                durability="completed_record" if hydrated else "turn_scoped",
                common=common,
                tool_name=tool_name,
                historical_state="preview_ready" if hydrated else None,
                current_actionability="unavailable" if hydrated else "turn_scoped",
                hydrated=hydrated,
            )
        elif result.get("success") is False or preview_error_present:
            out = _projection(
                "failed",
                "vault_preview_result",
                durability="completed_record",
                common=common,
                tool_name=tool_name,
                hydrated=hydrated,
            )
        elif preview_recovery_conflict:
            out = _projection(
                "unavailable",
                "vault_preview_result",
                durability="completed_record" if hydrated else "turn_scoped",
                common=common,
                tool_name=tool_name,
                reason="preview_recovery_conflict",
                hydrated=hydrated,
            )
        else:
            out = _projection(
                "unavailable",
                "vault_preview_result",
                durability="completed_record" if hydrated else "turn_scoped",
                common=common,
                tool_name=tool_name,
                reason="preview_evidence_incomplete",
                hydrated=hydrated,
            )
        plan_token = _bounded_text(result.get("plan_token"), 256)
        if plan_token:
            out["plan_token"] = plan_token
        _copy_plan_fields(result.get("plan"), out)
        diff = _exact_text(result.get("diff"))
        if diff:
            out["diff"] = diff
        if result.get("success") is not None:
            out["success"] = result.get("success") is True
        out["mutation_performed"] = result.get("mutation_performed") is True
        if preview_error:
            out["error"] = preview_error
        return out

    raw_success = result.get("success")
    raw_mutation = result.get("mutation_performed")
    raw_recovery = result.get("recovery_required")
    success = raw_success is True
    mutation = raw_mutation is True
    recovery_required = raw_recovery is True
    mutation_false = raw_mutation is False
    recovery_false = raw_recovery is False
    error = _safe_code(result.get("error"))

    if success and mutation and raw_recovery is not False:
        state = "unknown"
        projection_reason = (
            "conflicting_action_result"
            if recovery_required
            else "success_evidence_incomplete"
        )
    elif success and mutation and error:
        state = "unknown"
        projection_reason = "conflicting_action_result"
    elif (
        success
        and mutation
        and recovery_false
        and _success_evidence_complete(result)
    ):
        state = "succeeded"
        projection_reason = None
    elif success and mutation and recovery_false:
        state = "unknown"
        projection_reason = "success_evidence_incomplete"
    elif error in STALE_ERRORS and mutation_false and recovery_false:
        state = "stale_plan"
        projection_reason = None
    elif error in REFUSAL_ERRORS and mutation_false:
        state = "refused"
        projection_reason = None
    elif raw_success is False or error:
        state = "failed"
        projection_reason = None
    else:
        state = "unknown"
        projection_reason = "action_result_insufficient"

    out = _projection(
        state,
        "vault_action_result",
        durability="completed_record",
        common=common,
        tool_name=tool_name,
        success=raw_success if isinstance(raw_success, bool) else None,
        mutation_performed=(
            raw_mutation if isinstance(raw_mutation, bool) else None
        ),
        recovery_required=(
            raw_recovery if isinstance(raw_recovery, bool) else None
        ),
        error=error or None,
        reason=projection_reason,
        hydrated=hydrated,
    )
    _copy_allowed_fields(result, out)
    plan_token = _bounded_text(result.get("plan_token"), 256)
    if plan_token:
        out["plan_token"] = plan_token
    if result.get("recovery_id") or recovery_required:
        out["recovery_state"] = "unavailable"
    return out


def project_action_evidence(
    messages: Any,
    *,
    hydrated: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    names = _tool_call_name_map(messages)
    items: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        projected = project_tool_message(message, name_map=names, hydrated=hydrated)
        if projected is not None:
            items.append(projected)
    return items[-max(1, min(int(limit or 20), 100)):]


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content[:_MAX_MESSAGE_TEXT]
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    total = 0
    for part in content:
        text = ""
        if isinstance(part, str):
            text = part
        elif isinstance(part, dict):
            candidate = part.get("text")
            if isinstance(candidate, str):
                text = candidate
        if not text:
            continue
        remaining = _MAX_MESSAGE_TEXT - total
        if remaining <= 0:
            break
        text = text[:remaining]
        parts.append(text)
        total += len(text)
    return "\n".join(parts)


def _message_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    for key in ("data", "messages", "items"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def project_transcript_payload(payload: Any) -> dict[str, Any]:
    rows = _message_list(payload)
    safe_rows: list[dict[str, Any]] = []
    for row in rows:
        role = row.get("role")
        if role not in ("user", "assistant"):
            continue
        content = _message_text(row.get("content"))
        if not content:
            continue
        item: dict[str, Any] = {"role": role, "content": content}
        for key in ("id", "session_id"):
            value = _safe_id(row.get(key))
            if value:
                item[key] = value
        timestamp = row.get("timestamp")
        if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
            item["timestamp"] = timestamp
        safe_rows.append(item)
    out: dict[str, Any] = {"object": "orion.transcript", "data": safe_rows}
    if isinstance(payload, dict):
        for key in ("limit", "offset", "has_more"):
            value = payload.get(key)
            if isinstance(value, (int, bool)) and not isinstance(value, str):
                out[key] = value
    return out


def project_action_evidence_payload(
    payload: Any,
    *,
    session_id: str,
) -> dict[str, Any]:
    rows = _message_list(payload)
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "session_id": session_id,
        "source": "hermes_session_messages",
        "current_recovery_visibility": "unavailable",
        "items": project_action_evidence(rows, hydrated=True),
    }


def project_run_status(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    run_id = _safe_id(payload.get("run_id"))
    status = _safe_code(payload.get("status"))
    if not run_id or not status:
        return None
    out: dict[str, Any] = {
        "object": "orion.run_status",
        "run_id": run_id,
        "status": status,
        "action_state": "unobserved",
        "source": "hermes_run_status",
    }
    session_id = _safe_id(payload.get("session_id"))
    if session_id:
        out["session_id"] = session_id
    last_event = _safe_code(payload.get("last_event"))
    if last_event:
        out["last_event"] = last_event
    for key in ("created_at", "updated_at"):
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = value
    if payload.get("error"):
        out["run_error_observed"] = True
    return out


def project_stream_event(
    event_name: str,
    data: Any,
) -> tuple[str, dict[str, Any]] | None:
    if not isinstance(data, dict):
        return None
    name = str(event_name or data.get("event") or "").strip()
    common = _common(data)

    if name == "run.started":
        out = {**common, "event": name}
        runtime = _runtime(data.get("runtime"))
        if runtime:
            out["runtime"] = runtime
        return name, out

    if name == "message.started":
        out = {**common, "event": name}
        message = data.get("message")
        if isinstance(message, dict):
            message_id = _safe_id(message.get("id"))
            role = _safe_code(message.get("role"))
            safe_message: dict[str, str] = {}
            if message_id:
                safe_message["id"] = message_id
            if role:
                safe_message["role"] = role
            if safe_message:
                out["message"] = safe_message
        return name, out

    if name == "assistant.delta":
        return name, {
            **common,
            "event": name,
            "delta": _exact_text(data.get("delta"), 128 * 1024),
        }

    if name == "tool.progress":
        out = {**common, "event": name}
        tool_name = _safe_code(data.get("tool_name"))
        if tool_name:
            out["tool_name"] = tool_name
        delta = _bounded_text(data.get("delta") or data.get("preview"), 1000)
        if delta:
            out["delta"] = delta
        return name, out

    if name in {"tool.started", "tool.completed", "tool.failed"}:
        out = {**common, "event": name}
        tool_name = _safe_code(data.get("tool_name"))
        if tool_name:
            out["tool_name"] = tool_name
        preview = _bounded_text(data.get("preview"), 240)
        if preview:
            out["preview"] = preview
        return name, out

    if name == "approval.request":
        return name, project_approval_request(data)

    if name == "assistant.completed":
        out = {**common, "event": name}
        content = _exact_text(data.get("content"), _MAX_MESSAGE_TEXT)
        if content:
            out["content"] = content
        runtime = _runtime(data.get("runtime"))
        if runtime:
            out["runtime"] = runtime
        for key in ("completed", "partial", "interrupted"):
            if isinstance(data.get(key), bool):
                out[key] = data[key]
        return name, out

    if name == "run.completed":
        out = {**common, "event": name}
        runtime = _runtime(data.get("runtime"))
        if runtime:
            out["runtime"] = runtime
        out["action_evidence"] = project_action_evidence(
            data.get("messages"), hydrated=False
        )
        return name, out

    if name in {"run.cancelled", "run.failed", "error", "done"}:
        out = {**common, "event": name}
        if name in {"run.failed", "error"}:
            out["run_error_observed"] = True
        return name, out

    return (
        "projection.unobserved",
        {
            **common,
            "event": "projection.unobserved",
            "projection": _projection(
                "unobserved",
                "unsupported_stream_event",
                durability="transient_live",
                common=common,
                observed_event=_safe_code(name) or "unknown",
            ),
        },
    )
