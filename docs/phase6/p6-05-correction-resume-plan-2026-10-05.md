# P6-05 Reminder CRUD + HUD — Correction/Resume Plan

Status: **SUPERSEDED BY QUALIFIED P6-05 IMPLEMENTATION / MERGE-INTEGRATION HANDOFF**

Original date: 2026-10-05  
Updated: 2026-10-06

This document was the durable resume point while P6-05 was still being corrected. That correction cycle is now complete. Do not use the old finalization flow as the active P6-05 procedure.

The current handoff is:

`docs/phase6/p6-05-merge-readiness-and-integration-plan-2026-10-06.md`

## Final qualified implementation

P6-05 is implemented on:

- branch: `feature/p6-05-reminder-crud-hud`
- qualified commit: `b255aeb4a86daa2fc2a54688a2cae7a4b9ec9456`
- source parent: `69309e1559428ffee0455ed9f476222600e392a4`

Accepted Hermes baseline remains:

- tag: `v2026.8.27`
- package: `0.20.6`
- commit: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- profile: `companion`
- COMPANION home: `%LOCALAPPDATA%\hermes\profiles\companion`

Final repository qualification passed:

- reminder regression suite: **41/41**
- full HUD regression suite: **244/244**
- JavaScript syntax: PASS
- Python compile checks: PASS
- `git diff --check`: PASS
- exact P6-05 scope: 16 files
- local commit verification: PASS
- feature-branch push and remote SHA verification: PASS

The final uncertainty-semantics correction prevents the HUD from encouraging a naïve repeat when a mutation may already have happened. Mutating 5xx outcomes are treated as uncertain, the HUD performs read-only reconciliation, and no automatic mutation retry is performed.

## Architecture retained

The accepted P6-05 boundary is unchanged:

- Hermes owns reminder scheduling and durable job state.
- Orion does not add a second scheduler or timer daemon.
- Orion operates only on explicitly Orion-owned reminders.
- reminder create/list/get/pause/resume/cancel are bounded operations;
- no reminder `run` route or generic cron proxy exists;
- browser presentation is not durable authority;
- create binds native delivery intent `discord` without configuring a Discord destination;
- actual live delivery remains P6-06 work under separate authorization.

## Resolved correction items

The former blockers in this document are resolved:

- Hermes commit **and** project-version gate are present;
- reminder refresh is independent of conversation-gateway online state;
- schedule examples are limited to accepted parser forms;
- explicit Discord delivery intent is bound;
- the stale Phase 3 ordering test was repaired semantically;
- four legacy tests that froze the pre-Reminder workspace shape were updated to preserve their real contracts;
- post-mutation uncertainty behavior is explicitly handled and regression-tested.

Earlier brittle PowerShell/Python source-rewrite helpers are retired. Their failures were tooling failures, not P6-05 architectural failures.

## Current blocker: branch topology

P6-05 is not blocked on implementation quality. It is blocked from a **direct feature-branch merge** by repository history.

Current main:

- `5da4a9a326423e02f5d00b40a59c4192a10321a0`

GitHub comparison reports the feature branch is **96 commits ahead and 4 commits behind** current main, with merge base:

- `5ab6f44ae4c87044dcff528fef8e75345b703e74`

The P6-05 implementation is the final single commit on top of a 95-commit Phase 6 history that current main does not contain. A direct merge or normal PR from the feature branch would therefore import unrelated history.

Do not:

- merge `feature/p6-05-reminder-crud-hud` directly into main;
- rebase or force-push the qualified evidence branch merely to make history cleaner;
- merge main into the qualified feature branch before integration;
- run the old `Invoke-P6-05-FinalizeCorrection.ps1` against the completed implementation.

## Current integration direction

The researched integration path is a fresh branch from current main followed by a cherry-pick of **only**:

`b255aeb4a86daa2fc2a54688a2cae7a4b9ec9456`

The integration procedure must first verify clean state, exact refs, identical preimages for the 16 P6-05 files between current main and the source commit's parent, and no in-progress cherry-pick. The cherry-pick should use `-x` for public-branch provenance. Any conflict must cause an immediate abort and stop; no improvisational conflict resolution is authorized in the same unit.

After the cherry-pick, the integration candidate must prove:

- same 16-file scope;
- source/integration stable patch IDs match;
- compile and JavaScript syntax gates pass;
- 41/41 reminder tests pass;
- full HUD suite passes;
- `git diff --check` passes;
- integration branch is exactly one commit ahead of its main base;
- working tree is clean.

Do not push or merge that integration candidate without separate authorization.

## P6-06 remains separate

P6-06 is not started by P6-05 integration. It still requires separate authorization for live acceptance, including exact Discord destination qualification, one bounded live reminder, delivery evidence, missed/manual-off behavior, interrupted-run handling, duplicate suppression, delivery failure, sibling isolation, and corruption-preservation coverage where destructive testing is required.

For the complete current integration research and process lessons, use:

`docs/phase6/p6-05-merge-readiness-and-integration-plan-2026-10-06.md`
