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

The parser gate, runtime preflight, existing fork check, fork sync, source patch, and source assertions all passed. The local fork working tree then contained only the intended compatibility edits to `brainview.py` and the Brain dashboard `index.html`.

Execution stopped before commit/push because Windows exposed a `python.exe` App Execution Alias even though no usable host Python interpreter was installed. No dashboard deployment or Brain control request occurred.

### v3 — CRLF-sensitive import guard harness failure

The source patch stage completed, but the harness used `(?m)^import os$` against Windows CRLF text and falsely reported that the required import was missing. This was recorded separately as a harness defect. No source push or dashboard mutation occurred in that attempt.

### v3r1 — source accepted and pushed; dashboard chmod harness failure

The repaired continuation passed source assertions, target-runtime Python compile, and diff validation. It committed and pushed the exact compatibility source to the iai fork:

- iai fork commit: `55a8c32ece1f2af32002b3e0e542bead7290bdf1`
- message: `fix: make BrainView controls container-safe`
- changed files only: `src/iai_mcp/brainview.py`, `src/iai_mcp/_deploy/brainview/index.html`

The source adds the required `reason` to `user_initiated_sleep`, returns `external_manager` for Docker-managed start/stop/restart lifecycle requests, and maps that status to the Brain UI text `managed by the runtime`.

The same attempt backed up the dashboard package files, copied the candidate files into the dashboard container, then failed only because the harness tried to force `chmod 644` on package files owned by root in the container and received `Operation not permitted`. The bounded rollback/recovery path ran. No Brain control request was sent and the accepted Hermes/iai core container was not restarted.

### v4 — Brain dashboard sidecar deployment PASS

The post-push continuation verified the committed source and detected that the exact candidate bytes were already present in the dashboard package paths. Source and live SHA-256 values matched:

- `brainview.py`: `25bae7c529c35f112b91f25a00208c134b1df4785f254006d08b3f0428f73a8b`
- `index.html`: `6bdf084550ebc013210c109fdc6d7d25c4e82685386104c4f8b898f0903eef96`

Live package files were mode `755`, owner/group `0:0`, and runtime-readable. The corrected continuation intentionally skipped chmod rather than broadening privileges. Only `orion-iai-dashboard` was restarted; its post-restart `StartedAt` was `2026-08-27T21:18:16.630972148Z`. Brain HTTP on `127.0.0.1:4477` passed, the `managed by the runtime` copy was present, deployed hashes persisted, and accepted core container `orion-iai-m5-c` remained the same container ID with the same `StartedAt` (`2026-08-26T08:49:00.989990394Z`).

Deployment status: **PASS / READY FOR MANUAL CONTROL SMOKE**.

## Repository routing

- `S-Pillow/iai-personal-memory-engine`: upstream-compatible BrainView control-plane compatibility source.
- `S-Pillow/orion-personal-ai`: deployment/acceptance evidence and Phase 4 status.

## Next

Run the bounded manual Brain control smoke for **Let it rest**, **Wake**, **Sort memories now**, **Restart the subconscious**, and **Rest the subconscious**. Verify that restart/stop report externally managed and do not stop the iai daemon. After manual controls pass, complete the autonomous-lifecycle verification above. Only then close P4-02B1A and resume **P4-02B2 — typed Orion HUD → Hermes → iai**.
