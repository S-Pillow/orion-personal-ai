"""P6-02 disposable qualification for the Hermes native cronjob adapter.

This probe deliberately binds HERMES_HOME to a disposable directory before
importing Hermes cron modules. It exercises management actions only; it never
runs a cron job, starts the gateway, or invokes an LLM/provider.
"""
from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any


def emit(key: str, value: Any) -> None:
    if isinstance(value, bool):
        value = str(value).lower()
    print(f"{key}={value}")


def parse_result(label: str, payload: str) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except Exception as exc:
        raise AssertionError(f"{label}: cronjob result was not JSON: {payload!r}") from exc
    if not isinstance(data, dict):
        raise AssertionError(f"{label}: expected JSON object, got {type(data).__name__}")
    return data


def require_success(label: str, payload: str) -> dict[str, Any]:
    data = parse_result(label, payload)
    if data.get("success") is not True:
        raise AssertionError(f"{label}: expected success=true, got {data!r}")
    return data


def require_failure(label: str, payload: str) -> dict[str, Any]:
    data = parse_result(label, payload)
    if data.get("success") is not False:
        raise AssertionError(f"{label}: expected success=false, got {data!r}")
    if not data.get("error"):
        raise AssertionError(f"{label}: expected a deterministic error field")
    return data


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: p6-02-disposable-cron-adapter-qualification.py "
            "<hermes-root> <disposable-hermes-home>",
            file=sys.stderr,
        )
        return 2

    hermes_root = Path(sys.argv[1]).resolve()
    home = Path(sys.argv[2]).resolve()

    if not hermes_root.is_dir():
        raise AssertionError(f"Hermes root missing: {hermes_root}")
    home.mkdir(parents=True, exist_ok=True)
    scripts_dir = home / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # A no-agent script is stored only so the create-path validator has a real,
    # contained script target. This qualification never invokes action='run'.
    noop = scripts_dir / "p6_02_qualification_noop.py"
    noop.write_text('print("P6-02 disposable qualification only")\n', encoding="utf-8")

    # Bind the child process to the disposable store before any Hermes imports.
    os.environ["HERMES_HOME"] = str(home)
    os.environ.pop("HERMES_PROFILE", None)
    sys.path.insert(0, str(hermes_root))

    emit("P6_02_CHILD_HERMES_HOME", os.environ["HERMES_HOME"])
    emit("P6_02_CHILD_HERMES_PROFILE_PRESENT", "HERMES_PROFILE" in os.environ)

    # Prevent accidental outbound network traffic while allowing loopback-only
    # liveness probes. Management qualification must not contact a provider.
    original_connect = socket.socket.connect
    external_attempts: list[str] = []

    def guarded_connect(sock: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) and address else str(address)
        if str(host).lower() not in {"127.0.0.1", "::1", "localhost"}:
            external_attempts.append(str(address))
            raise AssertionError(f"external network attempt blocked: {address!r}")
        return original_connect(sock, address)

    socket.socket.connect = guarded_connect  # type: ignore[assignment]

    from tools.cronjob_tools import cronjob

    emit("P6_02_CRONJOB_IMPORT", "PASS")

    initial = require_success(
        "initial-list",
        cronjob(action="list", include_disabled=True),
    )
    if initial.get("count") != 0 or initial.get("jobs") != []:
        raise AssertionError(
            "Disposable HERMES_HOME was not empty; possible profile/store misbinding: "
            f"{initial!r}"
        )
    emit("P6_02_INITIAL_LIST_EMPTY", True)

    missing_schedule = require_failure(
        "missing-schedule",
        cronjob(
            action="create",
            name="P6-02 invalid create",
            no_agent=True,
            script=noop.name,
        ),
    )
    emit("P6_02_ERROR_MISSING_SCHEDULE", missing_schedule["error"])

    created = require_success(
        "create",
        cronjob(
            action="create",
            name="P6-02 disposable one-shot",
            schedule="30m",
            deliver="local",
            no_agent=True,
            script=noop.name,
        ),
    )
    job_id = created.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise AssertionError(f"create: missing job_id: {created!r}")
    for field in ("name", "schedule", "deliver", "next_run_at", "job"):
        if field not in created:
            raise AssertionError(f"create: missing structured field {field!r}")
    emit("P6_02_CREATE_STRUCTURED", True)
    emit("P6_02_CREATED_JOB_ID", job_id)
    emit("P6_02_CREATE_GATEWAY_RUNNING", created.get("gateway_running"))

    listed = require_success("list-after-create", cronjob(action="list", include_disabled=True))
    if listed.get("count") != 1:
        raise AssertionError(f"list-after-create: expected one job: {listed!r}")
    jobs = listed.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 1 or jobs[0].get("job_id") != job_id:
        raise AssertionError(f"list-after-create: wrong job projection: {listed!r}")
    if jobs[0].get("schedule") != "once in 30m":
        raise AssertionError(f"list-after-create: unexpected schedule projection: {listed!r}")
    emit("P6_02_LIST_STRUCTURED", True)
    emit("P6_02_LIST_JOB_ID_FIELD", "job_id")

    paused = require_success(
        "pause",
        cronjob(action="pause", job_id=job_id, reason="P6-02 qualification"),
    )
    paused_job = paused.get("job")
    if not isinstance(paused_job, dict):
        raise AssertionError(f"pause: missing structured job object: {paused!r}")
    if paused_job.get("job_id") != job_id or paused_job.get("state") != "paused":
        raise AssertionError(f"pause: unexpected job projection: {paused!r}")
    if paused_job.get("enabled") is not False:
        raise AssertionError(f"pause: expected enabled=false: {paused!r}")
    emit("P6_02_PAUSE_SUCCESS", True)

    resumed = require_success("resume", cronjob(action="resume", job_id=job_id))
    resumed_job = resumed.get("job")
    if not isinstance(resumed_job, dict):
        raise AssertionError(f"resume: missing structured job object: {resumed!r}")
    if resumed_job.get("job_id") != job_id or resumed_job.get("state") != "scheduled":
        raise AssertionError(f"resume: unexpected job projection: {resumed!r}")
    if resumed_job.get("enabled") is not True:
        raise AssertionError(f"resume: expected enabled=true: {resumed!r}")
    emit("P6_02_RESUME_SUCCESS", True)

    updated = require_success(
        "update",
        cronjob(action="update", job_id=job_id, name="P6-02 disposable renamed"),
    )
    updated_job = updated.get("job")
    if not isinstance(updated_job, dict):
        raise AssertionError(f"update: missing structured job object: {updated!r}")
    if updated_job.get("job_id") != job_id or updated_job.get("name") != "P6-02 disposable renamed":
        raise AssertionError(f"update: unexpected job projection: {updated!r}")
    emit("P6_02_UPDATE_SUCCESS", True)

    removed = require_success("remove", cronjob(action="remove", job_id=job_id))
    removed_job = removed.get("removed_job")
    if not isinstance(removed_job, dict) or removed_job.get("id") != job_id:
        raise AssertionError(f"remove: unexpected removed_job projection: {removed!r}")
    emit("P6_02_REMOVE_SUCCESS", True)

    final_list = require_success("final-list", cronjob(action="list", include_disabled=True))
    if final_list.get("count") != 0 or final_list.get("jobs") != []:
        raise AssertionError(f"final-list: disposable store not empty: {final_list!r}")
    emit("P6_02_FINAL_LIST_EMPTY", True)

    missing_job = require_failure("removed-job-lookup", cronjob(action="pause", job_id=job_id))
    emit("P6_02_ERROR_REMOVED_JOB", missing_job["error"])

    jobs_json = home / "cron" / "jobs.json"
    if not jobs_json.exists():
        raise AssertionError("Expected disposable cron/jobs.json to be created")
    emit("P6_02_DISPOSABLE_JOBS_JSON_EXISTS", True)

    executions_db = home / "cron" / "executions.db"
    emit("P6_02_DISPOSABLE_EXECUTIONS_DB_EXISTS", executions_db.exists())

    if external_attempts:
        raise AssertionError(f"External network attempts were observed: {external_attempts!r}")
    emit("P6_02_EXTERNAL_NETWORK_ATTEMPTS", 0)
    emit("P6_02_JOB_RUN_INVOKED", False)
    emit("P6_02_LLM_PROVIDER_INVOCATION_OBSERVED", False)
    emit("P6_02_DISPOSABLE_CRON_ADAPTER_PROBE", "PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
