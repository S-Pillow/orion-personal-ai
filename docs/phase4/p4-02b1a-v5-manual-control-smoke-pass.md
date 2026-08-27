# P4-02B1A — v5 Manual Brain Control Smoke PASS

Date: 2026-08-27
Status: **PASS / READY FOR AUTONOMOUS LIFECYCLE VERIFICATION**

## Scope

This run exercised only the five native iai Brain control actions after the container-safe BrainView compatibility source and sidecar deployment had already been accepted. It did not deploy source, restart/recreate the accepted core container, expose the Docker socket, or change iai memory semantics.

## Preflight

- Accepted core container: `orion-iai-m5-c`
- Accepted core container ID: `ea9fb7afbe6b394373390310a94bcacb21470388d1310a9305c7ef9e6a97b2d7`
- Accepted core `StartedAt`: `2026-08-26T08:49:00.989990394Z`
- Brain dashboard container ID: `b163bfd69177b03d7104d57a38c4be819e181e98cd540229ecdc912026465da0`
- Lifecycle before smoke: `WAKE`
- Preflight marker: `P4_02B1A_V5_PREFLIGHT=PASS`

## Manual control acceptance

1. **Let it rest** — PASS. BrainView returned successful native control acceptance for `user_initiated_sleep`; observed lifecycle two seconds later remained `WAKE`, which is not treated as a failure because the control-plane contract is asynchronous and the acceptance criterion for this button is that the native request with a valid reason is accepted.
2. **Wake** — PASS. Native `force_wake` was accepted and lifecycle reached/was `WAKE`.
3. **Sort memories now** — PASS. Native `force_rem` was accepted.
4. **Restart the subconscious** — PASS. Returned `external_manager`; no container/systemd lifecycle action occurred.
5. **Rest the subconscious** — PASS. Returned `external_manager`; no unintended daemon stop occurred.

Observed markers:

- `P4_02B1A_V5_LET_IT_REST=PASS`
- `P4_02B1A_V5_WAKE=PASS`
- `P4_02B1A_V5_SORT_MEMORIES=PASS`
- `P4_02B1A_V5_RESTART_CONTROL=EXTERNALLY_MANAGED`
- `P4_02B1A_V5_STOP_CONTROL=EXTERNALLY_MANAGED`
- `P4_02B1A_V5_EXTERNAL_LIFECYCLE_NO_MUTATION=PASS`

## Runtime preservation

Lifecycle after the smoke was `WAKE`. The accepted core container ID and `StartedAt` were unchanged, and the Brain dashboard container was also unchanged during the smoke. Native Brain/read health remained available.

Observed markers:

- `P4_02B1A_V5_ACCEPTED_CONTAINER_UNCHANGED=PASS`
- `P4_02B1A_V5_DASHBOARD_CONTAINER_UNCHANGED=PASS`
- `P4_02B1A_V5_IAI_MEMORY_RUNTIME_PRESERVED=PASS`
- `P4_02B1A_V5_MANUAL_CONTROLS=PASS`
- `P4_02B1A_V5_READY_FOR_AUTONOMOUS_LIFECYCLE=PASS`
- `P4_02B1A_V5=PASS`
- repaired wrapper completion: `P4_02B1A_V5R4=PASS`

Local evidence file reported by the run:

`E:\Orion-Phase2\P4-02B1A-evidence\p4-02b1a-v5-manual-control-smoke-20260827T220334Z.json`

## Harness history relevant to this pass

The successful smoke used the original bounded v5 test after repairing only harness defects discovered before any control request could be sent: scalar-string indexing of one-line `docker inspect` output and a PowerShell `$HOME` automatic-variable collision. Earlier repair attempts stopped before the control section and therefore did not mutate Brain control state.

## Next acceptance boundary

P4-02B1A is **not closed yet**. The remaining acceptance work is native autonomous lifecycle verification using production thresholds and actual iai lifecycle/event evidence:

- `WAKE -> DROWSY` on the native idle path,
- `DROWSY -> SLEEP` when the native 30-minute/sleep-eligibility conditions are satisfied,
- `SLEEP -> HIBERNATION` after a completed sleep cycle while still idle,
- foreground demand/wake signaling returns the lifecycle to `WAKE`,
- no production threshold changes, no hand-edited iai state, and no accepted-core container restart/recreation.

Only after that evidence passes should P4-02B1A close and P4-02B2 resume.
