"""Browser-safe projection of Hermes reminder authority.

This module owns presentation normalization only. It does not schedule, fire,
retry, repair, pause, resume, remove, or otherwise mutate Hermes jobs.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


ORION_REMINDER_PREFIX = "ORION_REMINDER_V1 :: "


class ReminderProjectionError(ValueError):
    """Raised when authoritative data cannot be projected safely."""


def is_orion_reminder(job: Mapping[str, Any]) -> bool:
    name = job.get("name")
    return isinstance(name, str) and name.startswith(ORION_REMINDER_PREFIX)


def reminder_title(job: Mapping[str, Any]) -> str:
    if not is_orion_reminder(job):
        raise ReminderProjectionError("job is not an Orion-owned reminder")
    title = str(job.get("name") or "")[len(ORION_REMINDER_PREFIX):].strip()
    return title or "Untitled reminder"


def project_execution(
    record: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return only bounded reminder-run evidence safe for the HUD.

    Process IDs, source paths, environment state, raw job prompts, and other
    implementation details are deliberately omitted.
    """
    if record is None:
        return None
    if not isinstance(record, Mapping):
        raise ReminderProjectionError("execution record must be an object")

    status = str(record.get("status") or "unknown").strip().lower()
    delivery = record.get("delivery_outcome")
    error_class = record.get("error_class")

    return {
        "id": str(record.get("id") or ""),
        "job_id": str(record.get("job_id") or ""),
        "scheduled_at": record.get("scheduled_at"),
        "claimed_at": record.get("claimed_at"),
        "started_at": record.get("started_at"),
        "finished_at": record.get("finished_at"),
        "status": status,
        "delivery_outcome": (
            str(delivery).strip().lower()
            if delivery not in (None, "")
            else None
        ),
        "error_class": (
            str(error_class).strip().lower()
            if error_class not in (None, "")
            else None
        ),
    }


def _attention(
    *,
    state: str,
    latest: Mapping[str, Any] | None,
) -> str:
    if latest:
        status = str(latest.get("status") or "").lower()
        delivery = str(latest.get("delivery_outcome") or "").lower()

        if status == "unknown":
            return "unknown"
        if status == "failed":
            return "failed"
        if delivery == "failed":
            return "delivery_failed"

    if state in {"error", "unknown"}:
        return "unknown"

    return "none"


def project_reminder(
    job: Mapping[str, Any],
    *,
    latest_execution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(job, Mapping):
        raise ReminderProjectionError("job must be an object")
    if not is_orion_reminder(job):
        raise ReminderProjectionError("job is not an Orion-owned reminder")

    job_id = str(job.get("job_id") or "")
    if not job_id:
        raise ReminderProjectionError("reminder is missing native job_id")

    raw_enabled = job.get("enabled", True)
    if not isinstance(raw_enabled, bool):
        raise ReminderProjectionError(
            "reminder enabled field must be boolean"
        )
    enabled = raw_enabled
    state = str(
        job.get("state")
        or ("scheduled" if enabled else "paused")
    ).strip().lower()

    latest = project_execution(latest_execution)

    return {
        "id": job_id,
        "title": reminder_title(job),
        # Summary intentionally does not expose prompt_preview/job prompt.
        "summary": reminder_title(job),
        "schedule": job.get("schedule"),
        "next_scheduled_time": job.get("next_run_at"),
        "state": state,
        "enabled": enabled,
        "last_run_at": job.get("last_run_at"),
        "last_run_outcome": (
            latest.get("status")
            if latest is not None
            else job.get("last_status")
        ),
        "delivery_outcome": (
            latest.get("delivery_outcome")
            if latest is not None
            else None
        ),
        "error_class": (
            latest.get("error_class")
            if latest is not None
            else None
        ),
        "attention": _attention(
            state=state,
            latest=latest,
        ),
    }


def project_reminder_list(
    native_payload: Mapping[str, Any],
    *,
    latest_executions: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(native_payload, Mapping):
        raise ReminderProjectionError("native list result must be an object")
    if native_payload.get("success") is not True:
        raise ReminderProjectionError("native list did not report success=true")

    jobs = native_payload.get("jobs")
    if not isinstance(jobs, list):
        raise ReminderProjectionError("native list is missing jobs array")

    scheduler_active = native_payload.get("gateway_running")
    if scheduler_active not in (True, False, None):
        raise ReminderProjectionError(
            "native scheduler state must be boolean or null"
        )

    latest_map = latest_executions or {}
    projected: list[dict[str, Any]] = []

    for job in jobs:
        if not isinstance(job, Mapping) or not is_orion_reminder(job):
            continue
        job_id = str(job.get("job_id") or "")
        projected.append(
            project_reminder(
                job,
                latest_execution=latest_map.get(job_id),
            )
        )

    return {
        "authority": "hermes",
        "scheduler_active": scheduler_active,
        "count": len(projected),
        "reminders": projected,
    }


def project_execution_history(
    records: Iterable[Mapping[str, Any]],
    *,
    job_id: str,
) -> dict[str, Any]:
    projected = []

    for record in records:
        if str(record.get("job_id") or "") != job_id:
            continue
        item = project_execution(record)
        if item is not None:
            projected.append(item)

    return {
        "authority": "hermes",
        "reminder_id": job_id,
        "count": len(projected),
        "runs": projected,
    }