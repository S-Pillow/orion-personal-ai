# P5-03A2 — Session-Chat Approval Compatibility Candidate

Status: **SOURCE CANDIDATE / NOT DEPLOYED / REVIEW REQUIRED**

This candidate backports only the Hermes approval seam needed by the accepted P5-03A2 Option B decision.

## Evidence basis

The installed Hermes baseline is commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` with the accepted P4-04A audio compatibility patch.

Read-only shape discovery established:

- session-chat already creates a unique `run_id`;
- session-chat uses `_run_agent` and preserves existing SessionDB/runtime/model-lock behavior;
- session-chat has no `_run_approval_sessions` registration and no gateway approval notify callback;
- `_run_agent` has no approval callback/session-key seam in the pinned build;
- `/v1/runs` already scopes approval authority by `run_id`, registers Hermes' native gateway notify callback, and cleans both the callback and run map;
- `POST /v1/runs/{run_id}/approval` resolves only through `_run_approval_sessions`.

A later upstream Hermes implementation independently adopted the same narrow pattern: `_run_agent` accepts a separate `approval_notify_callback` and `approval_session_key`, and session-chat registers the generated `run_id` as the approval namespace. That later code refactored approval-context helpers into a separate module; the pinned v0.20.6 baseline still defines them in `tools.approval`, and this candidate deliberately follows the pinned source. The later implementation is corroborating design evidence only; P5-03A2 does not upgrade Hermes or copy unrelated upstream changes.

## Candidate behavior

The patch:

1. adds optional `approval_notify_callback` and `approval_session_key` parameters to the existing pinned `_run_agent`;
2. scopes the executor thread's Hermes approval context to the supplied approval key only for that turn using the pinned build's native `tools.approval.set_current_session_key()` / `reset_current_session_key()` helpers;
3. registers and unregisters Hermes' existing gateway notify callback around `agent.run_conversation`;
4. keeps `gateway_session_key` unchanged for existing conversation/memory semantics;
5. registers session-chat's generated `run_id` in `_run_approval_sessions`;
6. emits a redacted native-shaped `approval.request` through the existing session-chat SSE queue;
7. passes the run-scoped approval callback/key into `_run_agent`;
8. unregisters the run-scoped gateway notify callback both in session-chat terminal cleanup and before disconnect drain waits, so a worker blocked on approval is actively released;
9. removes the run approval mapping in session-chat final cleanup.

The explicit disconnect unregister is required because Hermes' native `unregister_gateway_notify()` wakes blocked approval waiters. An executor-backed turn interrupted while awaiting approval can otherwise remain blocked before reaching the worker-thread `finally`.

No second approval engine or store is introduced.

## Composition with P4-04A

The wrapper and patcher accept only the exact Hermes commit plus the exact P4-04A worktree shape and live SHA-256:

`ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888`

It verifies the installed Hermes HEAD, exact expected dirty-file set, target path, existing P4-04A backup, and P4-04A manifest before planning or applying.

Its own rollback restores the exact accepted P4-04A patched state, not pristine upstream Hermes.

## Actions

- `SelfTest`: synthetic deterministic transformation/compile test.
- `Plan`: read-only transform against the installed accepted P4-04A source. Prints the combined planned post-patch SHA-256. Performs no write.
- `Verify`: read-only installed-state verification.
- `Apply`: guarded source replacement after self-test and exact base verification.
- `Rollback`: guarded restore to exact accepted P4-04A state.

`Apply` and `Rollback` are **not authorized by adding these files to the Orion repository**. They require a separate operator approval after source review, self-test, and read-only `Plan`.

## Remaining acceptance before deployment

Before any `Apply`:

- parser/syntax check the wrapper and Python patcher;
- run `SelfTest`;
- run `Plan` with Hermes stopped;
- record the planned combined SHA-256;
- review the generated source diff without modifying installed Hermes;
- add/run focused no-mutation approval-isolation tests;
- confirm ordinary session-chat/session history/runtime/model-lock behavior remains unchanged.

No vault read, mutation, approval request, protected action, dependency upgrade, or Hermes start is required for candidate review.
