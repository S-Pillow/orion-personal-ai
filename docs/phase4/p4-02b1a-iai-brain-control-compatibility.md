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

## Repository routing

- `S-Pillow/iai-personal-memory-engine`: upstream-compatible BrainView control-plane compatibility source.
- `S-Pillow/orion-personal-ai`: deployment/acceptance evidence and Phase 4 status.

## Next after closure

Resume **P4-02B2 — typed Orion HUD → Hermes → iai**. Full daemon stop/restart buttons can be implemented in Orion's system-control layer later without exposing the Docker socket to native BrainView.
