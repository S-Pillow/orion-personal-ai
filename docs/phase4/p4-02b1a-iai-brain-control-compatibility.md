# P4-02B1A — iai Brain Control Compatibility

Status: **IN PROGRESS**

## Purpose

Verify that the native iai Brain dashboard controls behave correctly in Orion's Docker/s6 deployment without changing iai memory semantics, and verify that iai's native autonomous lifecycle has the host-idle evidence it requires in the containerized COMPANION topology.

## Confirmed defect

The BrainView `sleep` action sends `user_initiated_sleep` with `type` and `ts`, while the daemon validator requires `reason` as a string. This explains the operator-visible `that didn't go through` response from **Let it rest**.

## Compatibility boundary

The accepted BrainView fix may change only Brain dashboard/control-plane compatibility. The autonomous-lifecycle follow-up may add only the minimum integration seam required to supply iai with real host-idle evidence that its existing `IdleDetector` cannot see from a Windows-hosted Linux container.

Neither part may alter iai recall, ranking, fading, consolidation semantics, correction semantics, storage schema, idle thresholds, transition rules, or Orion's canonical-memory decision.

For Docker deployments, BrainView process lifecycle controls must not attempt `systemctl --user` from a sidecar. The safe MVP behavior is to report that daemon process lifecycle is externally/container managed. Full stop/restart orchestration belongs in Orion's later system-control surface rather than granting the Brain sidecar Docker-socket privileges.

## Acceptance

1. **Sort memories now** — `force_rem` is accepted by the daemon.
2. **Let it rest** — `user_initiated_sleep` includes a valid reason and is accepted.
3. **Wake** — `force_wake` is accepted and the daemon returns toward awake state.
4. **Restart the subconscious** — in the Docker sidecar deployment, returns an explicit externally-managed status instead of a broken `systemctl --user` attempt.
5. **Rest the subconscious** — same safe externally-managed behavior; no unintended daemon stop.
6. Dashboard presents safe human-readable feedback for externally managed lifecycle actions.
7. Native iai Brain/read path remains healthy.
8. Accepted Hermes/iai container and iai volume are not restarted/recreated by the manual-control compatibility deployment.
9. **Autonomous lifecycle** — after the manual controls pass, verify that the daemon can manage its own state without operator clicks using iai's native lifecycle rules rather than Orion-specific timers.
10. Observe/verify the native automatic path `WAKE -> DROWSY` after the configured idle event, `DROWSY -> SLEEP` when the native sleep-eligibility condition is satisfied, and `SLEEP -> HIBERNATION` after a completed sleep cycle while still idle.
11. Verify foreground activity/wake signaling returns the lifecycle to `WAKE` as defined by upstream iai, and that normal activity refreshes the daemon rather than leaving it stuck in a sleep state.
12. Autonomous-state verification must use native iai lifecycle/event evidence. Do not modify idle thresholds or memory semantics merely to make the test finish faster; if a bounded accelerated test is needed, it must be isolated from the accepted profile and followed by an observation of the real production configuration.
13. Any container-host idle compatibility seam must fail closed on missing/stale/malformed evidence and must feed the existing iai lifecycle policy rather than implement a second Orion sleep policy.

## Autonomous lifecycle basis

Pinned iai 3.0.8 source defines the native state machine as follows: `WAKE` becomes `DROWSY` on `IDLE_5MIN`; `DROWSY` returns to `WAKE` on heartbeat refresh and becomes `SLEEP` on `IDLE_30MIN` when `sleep_eligible` is true; `SLEEP` becomes `HIBERNATION` after `SLEEP_CYCLE_DONE` when still idle; request/wake events return toward `WAKE`. Orion should verify that this upstream behavior is actually active in the deployed COMPANION brain rather than implementing a second lifecycle policy.

Pinned 3.0.8 also intentionally refreshes each live MCP wrapper heartbeat every 30 seconds. The daemon has a nightly window-deep-idle path specifically so a live wrapper can remain fresh while real OS-level human-idle evidence still admits consolidation. On Linux that evidence comes from seat-attached `systemd-logind` sessions; a headless Windows-hosted Docker container has no such seat, so native `os_idle_sec` is unknown unless an integration seam supplies the host observation.

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

### v5 / v5r4 — manual Brain control smoke PASS

After harness-only repairs for PowerShell scalar output indexing and the reserved `$HOME` variable collision, the bounded manual-control smoke completed successfully against the accepted production containers.

Observed acceptance markers:

- lifecycle pre-state: `WAKE`
- **Let it rest**: accepted
- **Wake**: accepted; authoritative lifecycle observed `WAKE`
- **Sort memories now**: accepted
- **Restart the subconscious**: `EXTERNALLY_MANAGED`
- **Rest the subconscious**: `EXTERNALLY_MANAGED`
- accepted core container ID/StartedAt unchanged
- Brain dashboard container unchanged during the control smoke
- iai memory runtime preserved
- evidence: `E:\Orion-Phase2\P4-02B1A-evidence\p4-02b1a-v5-manual-control-smoke-20260827T220334Z.json`

Manual controls status: **PASS**.

### v6A / v6Ar1 — transport repaired, but store-specific evidence later invalidated

The first v6A probe stopped before executing Python because Windows PowerShell 5.1 stripped embedded double quotes from the multiline `python -c` argument. The corrected v6Ar1 transport fed Python over stdin via `docker exec -i ... python -` and completed read-only.

However, later production discovery proved that the v6A/v6Ar1 probe resolved store-specific state through `Path.home()` under a root `docker exec`, so it inspected `/root/.iai-mcp` rather than the live COMPANION store `/opt/data/profiles/companion/.iai-mcp`. `/root/.iai-mcp` does not exist in the accepted runtime.

Therefore the following v6A/v6Ar1 store-specific observations are **withdrawn as production acceptance evidence**:

- lifecycle value read from the fallback path
- wrapper count / heartbeat-idle result
- pending/honored request state
- bounded lifecycle-event lookback
- derived `sleep_eligible` result that depended on the wrong wrapper directory

The code/config threshold reads (`300s`, `1800s`, `14400s`) were real defaults, and the platform `IdleDetector` result showing no OS-idle source remains diagnostically relevant because that detector is not store-path based. The accepted core/dashboard identities also remained unchanged.

### v6B / v6Br1 — observer harness corrected, then stopped after wrong-store behavior exposed

The first v6B observer had a PowerShell `${Name}:` interpolation/parser defect and executed nothing. The repaired v6Br1 ran read-only but repeatedly reported `WAKE`, `fresh=0`, and `eligible=True` from the same wrong root-store fallback. It was stopped rather than allowed to run through the night.

Subsequent direct runtime inspection established the real production state:

- live daemon process: `iai lilli (iai_mcp.daemon) store=/opt/data/profiles/companion/.iai-mcp`
- correctly addressed daemon status: healthy, iai 3.0.8, `fsm_state=WAKE`, scheduler not paused, tick advancing
- real socket: `/opt/data/profiles/companion/.iai-mcp/.daemon.sock`
- live persistent wrapper: iai 3.0.8 Node wrapper with heartbeat refreshing every 30 seconds
- real lifecycle log contained only the accepted manual transitions on 2026-08-27 and no autonomous idle transition

The earlier unqualified `iai-mcp daemon status -> daemon not running` result was also a probe-addressing false negative caused by the root HOME/socket default; explicitly setting the COMPANION HOME/store/socket returned a healthy daemon status.

## Autonomous lifecycle container-idle root cause

The pinned iai repository and current upstream main were reviewed after the failed observer. The behavior is intentional on both sides of the mismatch:

1. `mcp-wrapper/src/lifecycle.ts` refreshes a live wrapper heartbeat every 30 seconds.
2. `heartbeat_scanner.py` treats a heartbeat <=90 seconds old with a live PID as fresh; one fresh wrapper makes the scanner active.
3. `daemon/__init__.py` normally chooses `wake_refresh` for an active wrapper, but has a nightly window-deep-idle arm intended to see past an open/fresh wrapper when real OS human-idle evidence exists.
4. `idle_detector.py` obtains Linux human-idle evidence only from seat-attached `systemd-logind` sessions and deliberately ignores headless/no-seat sessions.
5. In Orion's Windows-hosted Docker container, no such Linux interactive seat exists, so `os_idle_sec` is unknown. With the persistent wrapper fresh, the native deep-idle arm cannot engage and `wake_refresh` wins.
6. Current upstream `CodeAbra/iai-personal-memory-engine` main still has this same idle-source model; no built-in container/Windows-host idle-provider seam was found.

Root cause status: **CONFIRMED HARD INTEGRATION MISMATCH**, not a dead daemon and not a defective wrapper heartbeat.

Detailed discovery record:

`docs/phase4/p4-02b1a-autonomous-lifecycle-container-idle-discovery.md`

## Compatibility candidate

The smallest intent-preserving candidate is an external host-idle observation at iai's existing `IdleDetector` boundary:

- opt-in env: `IAI_MCP_EXTERNAL_IDLE_PATH`
- schema-v1 JSON containing `idle_sec`, timezone-aware `observed_at`, and source metadata
- fresh, finite, non-negative observations only
- stale (>90s), future-invalid, malformed, missing, wrong-schema, or non-finite evidence is ignored/falls back to the native detector
- when the option is absent, native platform behavior is unchanged
- no lifecycle threshold or transition rule changes

Orion's Windows-side producer uses native `GetLastInputInfo` and atomically writes through the already accepted `C:\HermesAgent\data` -> `/opt/data` mount. No Docker socket, network listener, new memory store, lifecycle-state edit, or privilege expansion is introduced.

Staged candidate work:

- iai fork branch: `compat/orion-external-idle-signal`
- iai candidate head: `b6d356e67526ed30cc3e7a466597992fc440b800`
- draft iai PR: `S-Pillow/iai-personal-memory-engine#1`
- Orion host bridge branch: `feature/p4-02b1a-host-idle-bridge`
- Orion host bridge head: `729ec2863a2029e3218c0a9cd4ba50efbb300ad2`
- draft Orion PR: `S-Pillow/orion-personal-ai#2`

No production deployment of this candidate has occurred.

## Repository routing

- `S-Pillow/iai-personal-memory-engine`: upstream-compatible BrainView and host-idle compatibility source.
- `S-Pillow/orion-personal-ai`: Windows host evidence producer, deployment/acceptance evidence, and Phase 4 status.

## Next

Run the candidate in a disposable/no-network validation boundary first. It must prove the exact fork source accepts a fresh Windows-produced host-idle observation, rejects stale/malformed evidence, preserves the native 1800-second eligibility threshold, and leaves `orion-iai-m5-c` unchanged.

Only after that PASS should the project inspect and patch the canonical daemon pre-exec/service environment to set `IAI_MCP_EXTERNAL_IDLE_PATH`, build/deploy a bounded candidate runtime, and observe the real native production lifecycle. Final P4-02B1A closure still requires authoritative automatic `WAKE -> DROWSY -> SLEEP -> HIBERNATION` evidence plus a separate foreground-activity return to `WAKE`.
