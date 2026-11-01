#!/usr/bin/env python3
"""Session/profile v3: sampled startup + corrected production mutation observer.

v3 keeps the v2 structural identity and read-only SQLite persistence observers, but
retains the existing 90-second readiness acceptance boundary. While waiting it emits
bounded process/log samples so any recurrence of the earlier startup miss is evidence,
not an opaque timeout. Production mutation checks compare static config and gateway PID
identity; volatile live DB/status mtime changes are informational only.
"""
from __future__ import annotations

import time
from pathlib import Path

import v0225_gateway_startup_timing_diagnostic as startup_diag
import v0225_isolated_gateway_contract_smoke as base
import v0225_isolated_gateway_contract_smoke_v2 as gateway_v2
import v0225_isolated_gateway_contract_smoke_v5 as v5
import v0225_isolated_session_profile_contract_smoke as v1
import v0225_isolated_session_profile_contract_smoke_v2 as v2gate

START_TIMEOUT_S = 90.0
SAMPLE_INTERVAL_S = 10.0

_snapshot_calls: list[dict] = []


def stable_production_snapshot(root: Path, profile_home: Path) -> dict:
    """Mutation-sensitive production snapshot, excluding expected live-runtime churn."""
    static = startup_diag._static_snapshot(root, profile_home)
    pid = startup_diag._pid_snapshot(root, profile_home)
    volatile = startup_diag._volatile_snapshot(root, profile_home)
    _snapshot_calls.append({"static": static, "pid": pid, "volatile": volatile})

    if len(_snapshot_calls) == 2:
        first, second = _snapshot_calls
        volatile_changed = startup_diag._changed_paths(first["volatile"], second["volatile"])
        print(
            "PRODUCTION_VOLATILE_RUNTIME_CHANGED="
            + ("NONE" if not volatile_changed else ";".join(volatile_changed))
        )
        print("PRODUCTION_VOLATILE_RUNTIME_CHANGE_IS_MUTATION_ORACLE=false")
        if first["static"] == second["static"]:
            print("PRODUCTION_STATIC_CONFIG_UNCHANGED=PASS")
        if first["pid"] == second["pid"]:
            print("PRODUCTION_GATEWAY_PID_IDENTITY_UNCHANGED=PASS")

    return {"static": static, "pid": pid}


def wait_http_ready_sampled(proc, port: int, log_path: Path, key: str) -> None:
    """Preserve the 90-second gate while making recurrence evidence observable."""
    started = time.monotonic()
    deadline = started + START_TIMEOUT_S
    next_sample = started + 2.0
    last_state = "UNREACHABLE"

    while time.monotonic() < deadline:
        if proc.poll() is not None:
            rc = proc.returncode
            classification = "WATCHDOG_EXIT_75" if rc == 75 else f"PROCESS_EXIT_{rc}"
            raise RuntimeError(
                "isolated gateway exited before session-gate HTTP readiness: "
                f"{classification}\n"
                + gateway_v2.proc_diag(proc, log_path)
                + "\n--- SAFE LOG TAIL ---\n"
                + base.safe_log_tail(log_path, key)
            )

        last_state = v5.health_state(port)
        now = time.monotonic()
        if last_state == "HTTP_200|status=ok":
            elapsed = now - started
            print(f"SESSION_GATE_HTTP_READY=PASS|elapsed_s={elapsed:.3f}")
            print("SESSION_GATE_STARTUP_CLASSIFICATION=READY_WITHIN_90S")
            return

        if now >= next_sample:
            startup_diag._sample(proc, log_path, started, port)
            next_sample = now + SAMPLE_INTERVAL_S
        time.sleep(0.25)

    startup_diag._sample(proc, log_path, started, port)
    raise RuntimeError(
        "isolated gateway did not become HTTP-ready within the retained 90-second "
        f"session-gate boundary; last={last_state}\n"
        + gateway_v2.proc_diag(proc, log_path)
        + "\n--- SAFE LOG TAIL ---\n"
        + base.safe_log_tail(log_path, key, lines=120)
    )


def main() -> int:
    # Observer corrections only; the underlying session CRUD contract stays unchanged.
    v1.v5.probe_scratch_identity = v2gate.structural_scratch_identity
    v1.verify_persisted_scratch_session = v2gate.verify_persisted_scratch_session_sqlite
    v1.v5.wait_http_ready = wait_http_ready_sampled
    v1.base.snapshot_production = stable_production_snapshot

    print("SESSION_PROFILE_HARNESS_VERSION=v3")
    print("STARTUP_ACCEPTANCE_BOUNDARY_S=90")
    print("STARTUP_SAMPLING=enabled")
    print("PRODUCTION_MUTATION_ORACLE=static_config_plus_gateway_pid_identity")
    return v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
