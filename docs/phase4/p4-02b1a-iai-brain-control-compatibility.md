# P4-02B1A — iai Brain Control Compatibility

Status: **IN PROGRESS**

## Purpose

Verify that the native iai Brain dashboard controls behave correctly in Orion's Docker/s6 deployment without changing iai memory semantics.

## Confirmed defect

The BrainView `sleep` action sends `user_initiated_sleep` with `type` and `ts`, while the daemon validator requires `reason` as a string. This explains the operator-visible `that didn't go through` response from **Let it rest**.

## Compatibility boundary

This ticket may change only Brain dashboard/control-plane compatibility. It must not alter iai recall, ranking, fading, consolidation semantics, correction semantics, storage schema, or Orion's canonical-memory decision.

For Docker deployments, BrainView process lifecycle controls must not attempt `systemctl --user` from a sidecar. The safe MVP behavior is to report that daemon process lifecycle is externally/container managed. Full stop/restart orchestration belongs in Orion's later system-control surface rather than granting the Brain sidecar Docker-socket privileges.

## Acceptance

1. **Sort memories now** — `force_rem` is accepted by the daemon.
2. **Let it rest** — `user_initiated_sleep` includes a valid reason and is accepted.
3. **Wake** — `force_wake` is accepted and the daemon returns toward awake state.
4. **Restart the subconscious** — in the Docker sidecar deployment, returns an explicit externally-managed status instead of a broken `systemctl --user` attempt.
5. **Rest the subconscious** — same safe externally-managed behavior; no unintended daemon stop.
6. Dashboard presents safe human-readable feedback for externally managed lifecycle actions.
7. Native iai Brain/read path remains healthy.
8. Accepted Hermes/iai container and iai volume are not restarted/recreated by this compatibility deployment.
9. **Autonomous lifecycle** — after the manual controls pass, verify that the daemon can manage its own state without operator clicks using iai's native lifecycle rules rather than Orion-specific timers.
10. Observe/verify the native automatic path `WAKE -> DROWSY` after the configured idle event, `DROWSY -> SLEEP` when the native sleep-eligibility condition is satisfied, and `SLEEP -> HIBERNATION` after a completed sleep cycle while still idle.
11. Verify foreground activity/wake signaling returns the lifecycle to `WAKE` as defined by upstream iai, and that normal activity refreshes the daemon rather than leaving it stuck in a sleep state.
12. Autonomous-state verification must use native iai lifecycle/event evidence. Do not modify idle thresholds or memory semantics merely to make the test finish faster; if a bounded accelerated test is needed, it must be isolated from the accepted profile and followed by an observation of the real production configuration.

## Autonomous lifecycle basis

Pinned iai 3.0.8 source defines the native state machine as follows: `WAKE` becomes `DROWSY` on `IDLE_5MIN`; `DROWSY` returns to `WAKE` on heartbeat refresh and becomes `SLEEP` on `IDLE_30MIN` when `sleep_eligible` is true; `SLEEP` becomes `HIBERNATION` after `SLEEP_CYCLE_DONE` when still idle; request/wake events return toward `WAKE`. Orion should verify that this upstream behavior is actually active in the deployed COMPANION brain rather than implementing a second lifecycle policy.

## Live attempt history

### v1 — harness failure before source/runtime mutation

The parser gate passed, runtime preflight passed, and the script created the local iai fork clone if absent. Execution then stopped on a PowerShell harness-generation defect: a minified command was emitted as `Write-HostP4_02B1A_FORK_CLONED=PASS` instead of `Write-Host "P4_02B1A_FORK_CLONED=PASS"`.

This failure occurred immediately after the clone branch and before the compatibility source patch, commit/push, dashboard backup/deploy, dashboard restart, or any Brain daemon control action. No accepted Hermes/iai container restart or memory-runtime mutation occurred.

### v2 — false-positive host Python launcher

The parser gate, runtime preflight, existing fork check, fork sync, source patch, and source assertions all passed. The local fork working tree now contains only the intended compatibility edits to `brainview.py` and the Brain dashboard `index.html`.

Execution then stopped before commit/push because Windows exposed a `python.exe` App Execution Alias even though no usable host Python interpreter was installed. The script therefore tried to run `python -m py_compile` and received the Microsoft Store launcher message.

No compatibility commit was created or pushed. No dashboard backup/deploy/restart occurred. No Brain control request was sent. The accepted Hermes/iai container and memory runtime were not changed.

The next revision must treat the two expected local source edits as a bounded continuation state and compile the candidate `brainview.py` with the Python runtime already present inside the Brain dashboard container instead of trusting a Windows `python.exe` alias.

## Repository routing

- `S-Pillow/iai-personal-memory-engine`: upstream-compatible BrainView control-plane compatibility source.
- `S-Pillow/orion-personal-ai`: deployment/acceptance evidence and Phase 4 status.

## Next after closure

Complete the autonomous-lifecycle verification above, then resume **P4-02B2 — typed Orion HUD → Hermes → iai**. Full daemon stop/restart buttons can be implemented in Orion's system-control layer later without exposing the Docker socket to native BrainView.
