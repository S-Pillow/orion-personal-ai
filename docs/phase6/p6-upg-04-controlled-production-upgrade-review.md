# P6-UPG-04 — Controlled Production Hermes v0.21.5 Upgrade Review

Status: **PREPARED FOR OWNER REVIEW — PRODUCTION MUTATION NOT AUTHORIZED**

## Accepted candidate

Hermes target:

- tag: `v2026.9.24`
- package: `0.21.5`
- commit: `f97608f178d1ffeca59860195ab7da295f7c8e5f`

Qualified Orion candidate:

- exact Hermes v0.21.5 target;
- P6-UPG-02 Orion compatibility patch;
- upstream `f57d2357485f1cc234e438b813e75c241a09c9e7` external-worker
  dependency fix;
- combined artifact:
  `compat/hermes/v2026.9.24-orion-qualified-combined.patch`;
- combined SHA-256:
  `21edb9cf49eb6e2724852dc090f755cf38564db5026ab4d0b3814f34c0b355e4`.

P6-UPG-03 acceptance:

- upstream worker regression set: 5 passed;
- Orion-relevant focused set: 56 passed, 15 skipped;
- SQLite integrity selftest: PASS;
- production logical state unchanged;
- installed Hermes unchanged;
- no restart or live reminder.

## Authorization boundary

This document is planning only.

Do not perform any of the following without a separate explicit owner
authorization for P6-UPG-04:

- change the installed Hermes source or pin;
- replace the installed dependency environment;
- mutate COMPANION state;
- stop or restart the production gateway;
- run a live reminder;
- delete or repair runtime state.

## Production preflight — all must pass before mutation

1. Installed Hermes still matches the accepted production pin:
   `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`.
2. Orion production cron state is read-only inspected and matches the accepted
   logical baseline.
3. No claimed/running cron execution and no active scheduler-owned run.
4. No `source-completion-pending` marker.
5. Exactly one gateway listener owns port 8642.
6. Capture gateway PID, executable, command line, and listener ownership.
7. Record current runtime-state file metadata without printing secrets or raw
   private state.
8. Confirm the combined compatibility artifact SHA-256 exactly matches the
   accepted value above.
9. Confirm the artifact applies cleanly to the exact target commit in a
   disposable checkout.
10. Capture rollback inputs before any replacement.

Any mismatch is a STOP condition.

## Controlled production mutation

Execution must be one bounded operator packet. The implementation packet should:

1. stage the exact v0.21.5 target;
2. apply the single combined qualified compatibility artifact;
3. verify transformed source hashes before activation;
4. preserve the accepted production installation for rollback;
5. activate the new installation/pin without touching COMPANION data;
6. perform one controlled gateway restart;
7. make no other runtime-state edits.

The exact PowerShell mutation commands are intentionally not stored here before
authorization and same-day preflight. They must be generated from the current
installed layout immediately before execution.

## Mandatory post-restart acceptance

The upgrade is not accepted merely because an updater reports success.

All of the following must pass:

1. installed source/pin resolves to the exact intended v0.21.5 candidate;
2. exactly one gateway process/listener returns on port 8642;
3. gateway status is independently healthy;
4. no `source-completion-pending` marker remains;
5. ticker heartbeat advances under the restarted gateway;
6. no stale-lock condition is present;
7. fresh-connection `PRAGMA integrity_check` returns `ok`;
8. turn-machinery warm-up completes, or one bounded first-turn acceptance probe
   succeeds before the gateway is considered fully ready;
9. production cron jobs/execution ledger remain logically intact;
10. no unexpected duplicate scheduler ownership is observed.

Only after those gates pass may a separately approved minimal live-reminder
acceptance be considered.

## Rollback triggers

Rollback rather than diagnose in-place if any of these occur immediately after
activation:

- gateway fails to return;
- listener ownership is ambiguous or duplicated;
- SQLite integrity fails;
- state schema or logical counts drift unexpectedly;
- ticker does not advance;
- worker/bootstrap failure prevents normal cron ownership;
- source-completion state is stranded;
- warm-up/first-turn readiness cannot be established within the bounded
  acceptance window.

Rollback must restore the accepted production installation and restart only the
gateway required to return to the prior state. Runtime databases must not be
hand-edited as part of rollback.
