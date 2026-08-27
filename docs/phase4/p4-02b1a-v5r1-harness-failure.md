# P4-02B1A v5r1 — manual-control smoke repair harness failure

Date: 2026-08-27

Status: **HARNESS FAILURE — NO BRAIN CONTROL REQUEST SENT**

## Observed boundary

The v5r1 repair wrapper inspected the original v5 script and reported:

- `P4_02B1A_V5R1_DOCKER_INSPECT_PATCH_COUNT=1`
- `P4_02B1A_V5R1_LIFECYCLE_OUTPUT_PATCH_COUNT=0`

It then stopped before writing or launching the repaired v5 script.

Therefore no Brain control request (`sleep`, `wake`, `consolidate`, `restart`, or `stop`) was sent by this attempt.

## Diagnosis

The original v5 script does contain the PowerShell single-item indexing defect in `Get-ContainerState`: it indexes `(Invoke-Native ...)[0]`, so a one-line `docker inspect` result can be unrolled to a scalar string and `[0]` returns only the first character.

The v5r1 repair wrapper incorrectly assumed that the lifecycle reader had the same defect. The actual v5 lifecycle reader is already array-safe: it captures the `docker exec ... cat <lifecycle_state.json>` output into `$lines` and then joins `@($lines)` before JSON parsing. The second repair anchor therefore correctly matched zero times.

This is a repair-wrapper defect, not an iai runtime or Brain-control defect.

## Minimum correction

Patch only the `Get-ContainerState` docker-inspect site by wrapping the `Invoke-Native` result with `@(...)`, validating at least one output line, and indexing the resulting array. Leave the lifecycle reader unchanged and require an explicit guard that the already-safe lifecycle reader is still present before launching the repaired smoke.

## Safety disposition

No source deploy, dashboard restart, accepted core-container restart, lifecycle-file edit, memory-runtime edit, or Brain control action occurred in this v5r1 attempt. P4-02B1A remains in progress at the manual-control smoke boundary.
