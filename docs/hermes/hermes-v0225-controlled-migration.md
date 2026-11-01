# Hermes v0.22.5 Controlled Migration

Status: **PRE-INSTALL QUALIFICATION — ACTIVE**

Prepared: 2026-10-30

Canonical current qualification status:

- `docs/hermes/hermes-v0225-qualification-status.md`

## Current qualification checkpoint

Completed and reconciled as of 2026-10-31:

- exact v0.22.5 source candidate qualification — **PASS**;
- retained compatibility delta P4-04A / P6-03 / P6-04A — source-qualified;
- isolated standalone gateway contract v6 — **PASS WITH WINDOWS BIND-ENUMERATION LIMITATION**;
- bounded startup timing diagnostic — **PASS**, HTTP-ready in **8.285 s**;
- isolated session/profile resource contract v3 — **PASS**, HTTP-ready in **7.745 s**, session CRUD/auth/persistence/profile isolation proven with zero model/memory/STT/TTS provider calls.

Current gate:

- P6-03 exact pre-repair `jobs.json` preservation + P6-04A durable `error_class` isolated runtime contract — **UNRESOLVED AT COMMON CRON/ASYNCIO IMPORT BOUNDARY**. The phase-instrumented v2 harness proved that both children fail before their P6 operations execute: importing `cron.jobs` or `cron.executions` reaches `cron.__init__ -> cron.scheduler -> cron.scheduler_delivery -> asyncio`, where the runtime raises `NameError: name 'base_events' is not defined`. v2's production health/static-config/PID and candidate-source postconditions passed. The next bounded oracle is `scripts/hermes_upgrade/v0225_windows_asyncio_import_diagnostic.py`; do not rerun the P6 functional harness until that import diagnostic is reconciled.

Production remains on accepted Hermes `0.20.6` / `v2026.8.27` / `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`. No production cutover or runtime mutation is authorized by the progress above.

## Decision

Orion will prepare and qualify a COMPANION Hermes migration from the accepted pinned
checkout `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (`v2026.8.27`, Hermes Agent
v0.20.6) toward upstream Hermes `v0.22.5` at release commit
`bf0203a794a07aac3ff764972ab9087baa4e4f4e`.

This is an upgrade project, not approval to install stock v0.22.5 unqualified. The target
release has known post-release defects, so production cutover is gated on Orion-specific
qualification and may retarget to a newer stable Hermes release if one lands before
cutover and materially reduces relevant risk.

This replaces the prior strategy of indefinitely carrying compatibility patches on the
August Hermes baseline. The migration is controlled rather than a blind `hermes update`
because the installed checkout contains accepted Orion compatibility changes.

## Acceptance priority

Five product/system pillars are hard gates for production cutover:

1. **Orion** — accepted lifecycle ownership, gateway health, HUD launch-after-health,
   COMPANION profile behavior, iai integration, and no second lifecycle/supervision path.
2. **Memory** — existing memory/vault state remains intact and readable; iai keeps the
   accepted COMPANION home/environment; DC-02 remains incremental-only; no destructive
   migration, silent re-index, or loss of memory evidence is accepted.
3. **Voice** — native Hermes STT/TTS contracts, Edge TTS, Orion PTT, Speak Replies,
   interruption/barge-in, and typed fallback must pass on the candidate.
4. **Chat** — normal turns, streaming, session continuity, stop/interruption, approval
   behavior, long-session handling, and no lost/duplicated turns must pass.
5. **Security** — API authentication, localhost/bind expectations, credential isolation,
   approval/authorization boundaries, profile isolation, plugin/tool execution boundaries,
   dependency integrity, and secret non-disclosure must not regress.

Cron, LSP, Hermes Desktop, optional plugins, unrelated messaging platforms, and other
non-core surfaces are **not independent blockers**. A defect in one of those surfaces
becomes blocking only if its failure mode crosses into one of the five hard gates above
(for example, a cron-labelled bug that can crash the gateway or corrupt shared session
state).

## v0.22.5 reported-issue gate

The following known reports were reviewed before migration execution. Their labels do not
determine blocking status; blast radius against the five hard gates does.

- **#144883 — gateway event-loop/profile-scope stall, P1, open.** Relevant to Orion and
  Chat because slow profile file reads can trip the liveness watchdog and interrupt
  in-flight work on affected multi-profile paths. The disposable runtime candidate must
  either prove COMPANION does not exercise the affected path or qualify an explicit,
  reviewable mitigation before production cutover.
- **#145215 — owner-forward failure for resume snapshots over 1 MiB, P1, open.** Relevant
  only if Orion's topology/session flow exercises owner forwarding. Long-session
  qualification must prove the Orion path is unaffected or fail the Chat gate.
- **#144474 — Windows LSP client-replacement regression, P2, open.** LSP itself is not a
  hard gate. This is non-blocking unless qualification shows the failure shares a broader
  process/session failure mode that reaches Orion or Chat.
- **#144455 / related cron delivery reports.** Cron delivery is not a hard gate. These are
  accepted as non-blocking unless the underlying defect crosses into gateway stability,
  session integrity, memory, or security.
- **#143512 — Hermes Desktop chained live voice does not request speech, P2, open.** This
  is not an Orion HUD blocker because Orion owns its voice orchestration and calls the
  Hermes audio API directly. Native audio and Orion HUD voice still must pass the Voice
  gate.
- **#144706 and other Hermes Desktop UI/build defects.** Desktop presentation/build
  surfaces are non-blocking for Orion unless a shared backend defect reaches a hard gate.
- **#146242 and related session-control reports.** These require targeted Chat
  qualification because Orion depends on Hermes session APIs; any reproducible session
  loss, incorrect ownership refusal, or mutation failure in Orion's exercised path is a
  blocker.
- **Profile/home/plugin isolation reports such as #146736.** These are potential Security
  or Orion blockers if COMPANION exercises the affected home/plugin path. Qualification
  must prove profile-home and credential boundaries for the actual Orion deployment.

As of the qualification decision, v0.22.5 remains the latest stable Hermes release. A
newer stable release may replace this target before cutover, but only after the same five
hard gates and compatibility-port disposition are re-evaluated against that exact release.

## Accepted installed baseline

Read-only inventory on 2026-10-30 proved:

- Hermes HEAD: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`;
- detached tag baseline: `v2026.8.27`;
- exactly 10 dirty worktree entries;
- all six modified/new source files matched the expected accepted Orion hashes;
- all four P4/P5 gateway sidecars were present and matched their manifests;
- active gateway `edge-tts` remained `7.2.7` because the old source/lock owns that version;
- COMPANION had zero cron jobs;
- COMPANION `executions.db` existed with zero rows;
- current execution columns were
  `id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error,scheduled_at,delivery_outcome,error_class`;
- Hermes health, Ollama `/api/tags`, and the accepted HUD all returned HTTP 200;
- no writes were performed by the inventory.

## Compatibility disposition

### Port: P4-04A Hermes audio gateway bridge

Disposable exact-release qualification corrected an earlier assumption: Hermes v0.22.5
contains native `/api/audio/transcribe` and `/api/audio/speak` handlers in the Hermes
**dashboard/web-server** surface (`hermes_cli/web_routers/audio.py`), but the authenticated
API-server gateway Orion uses on port 8642 still declares `audio_api: false` and exposes no
corresponding audio routes in `gateway/platforms/api_server.py`.

Orion will not add a second Hermes dashboard/web process merely to obtain voice relay. The
accepted one-gateway architecture remains authoritative. Therefore P4-04A is still a
required migration port.

The v0.22.5 port is exact-commit and narrow:

- preserve the existing Bearer-authenticated 8642 API-server boundary;
- add bounded `POST /api/audio/transcribe` and `POST /api/audio/speak` routes;
- reuse v0.22.5 `transcribe_recording()` and `text_to_speech_tool()` implementations;
- preserve multiplex profile scoping through the API server's existing `_profile_scope`;
- preserve bounded MIME/input/output limits, temporary-file cleanup, media-path validation,
  and redacted API errors;
- set `audio_api: true` while keeping `realtime_voice: false`;
- do not add another listener, voice provider, hotword service, or browser-side provider
  credential path.

Hermes v0.22.5's dependency ownership still improves this path because its source and lock
pin `edge-tts==7.3.1`, replacing the obsolete `7.2.7` dependency that currently causes the
Edge 403 failure.

### Retire: P5-03A2 session-chat approval compatibility patch

Hermes v0.22.5 contains native run-scoped approval notification/registration and
`approval.request` / `waiting_for_approval` transport in the API server. The old Orion
approval backport must not be reapplied. Orion approval behavior still requires runtime
requalification after migration.

### Retire: P6-04 old durable-run-evidence patch

Hermes v0.22.5 has a materially richer execution ledger: `scheduled_instant`, durable
`delivery_outcome`, progress tracking, process ownership, handoff/adoption fencing, and
restart recovery. The old P6-04 `scheduled_at`/delivery patch must not be reapplied.

The existing production SQLite database contains zero rows. Its legacy nullable
`scheduled_at` column can remain as an inert compatibility column while v0.22.5 adds its
new columns; no destructive schema rewrite is authorized merely for column cleanup.

This cron compatibility work is retained for data/schema cleanliness and future capability,
but cron functional delivery is not a production blocker unless its failure crosses a
hard-gate boundary.

### Port: P6-03 exact pre-repair jobs.json preservation

Upstream v0.22.5 substantially improves cron store locking, merge safety, shape repair,
and corruption handling, but an automatic repair still rewrites `jobs.json` without first
preserving the exact pre-repair bytes. Orion retains the requirement to save an exact,
durable recovery artifact before any automatic repair rewrite.

The v0.22.5 port is intentionally narrow: preserve the exact locked snapshot immediately
before `save_jobs()` performs a repair rewrite, while leaving upstream merge/locking logic
unchanged.

This port is retained as a defensive data-preservation invariant; cron scheduling itself
remains non-blocking.

### Port: P6-04A durable error classification

Upstream v0.22.5 still classifies cron errors for monitoring but does not persist
`error_class` in the execution ledger. Orion retains durable failure classification.

The v0.22.5 port extracts the current upstream classifier into a dependency-light shared
module, keeps the monitoring projection on the same classifier, adds nullable
`error_class` to the ledger, and persists it on every current v0.22.5 terminal
failure/unknown path:

- `finish_execution`;
- `recover_receipted_execution`;
- `recover_interrupted_executions`;
- `terminalize_dead_owner`;
- `give_up_execution`.

Successful executions retain `error_class = NULL`.

## Migration gates

1. **Disposable source candidate — PASS.** Exact v0.22.5 was cloned and verified; the stock 8642 API-server audio gap and separate dashboard audio implementation were confirmed; the three surviving Orion ports (P4-04A, P6-03, P6-04A) were applied and source-qualified; compile/diff checks, approval transport, `edge-tts==7.3.1`, and installed-Hermes invariance passed.
2. **Reported-issue relevance qualification — IN PROGRESS.** The startup/profile-scope risk has received targeted runtime observation: one 90-second readiness miss remains an intermittent observation, while the dedicated diagnostic reached readiness in 8.285 s and the subsequent session gate in 7.745 s. Remaining reported-issue checks are limited to paths that can cross into Orion, Chat, Memory, Voice, or Security.
3. **Disposable runtime qualification — IN PROGRESS.** Isolated gateway auth/capability/P4-04A local-validation passed; startup timing passed; isolated session CRUD/auth/persistence/profile isolation passed. P6-03/P6-04A functional runtime evidence remains unresolved because both v2 children currently fail at the shared `cron` package -> `asyncio` import boundary before P6 logic executes. The Windows asyncio/import diagnostic is the next oracle. Memory, actual model-backed Chat, and actual STT/TTS remain separately gated and are not implied by the completed sub-gates.
4. **Pre-cutover backup — NOT STARTED.** Preserve the entire accepted dirty Hermes source state, four sidecars, dependency ownership metadata, COMPANION profile/runtime state, memory/vault evidence, and database files required for rollback.
5. **Controlled cutover — NOT AUTHORIZED / NOT STARTED.** Only after the candidate is qualified, stop Orion through the accepted lifecycle, switch Hermes to the qualified exact source plus only the qualified Orion ports/mitigations, sync the managed environment, and restart Orion. Do not use a blind updater against the dirty accepted checkout.
6. **Production hard-gate requalification — NOT STARTED.** Orion lifecycle/runtime, Memory, Voice, Chat/session behavior, and Security all must pass on Windows. Cron/LSP/Desktop failures do not block unless evidence shows they cross one of those five boundaries.
7. **Closure — NOT STARTED.** Only after all five production hard gates pass may P5-03A2 and the old P6-04 implementation be treated as retired in production. P4-04A remains a qualified compatibility port until upstream exposes the required audio surface on the 8642 API server itself or Orion's architecture is separately changed and accepted.

## Current authorization boundary

The upgrade project and disposable qualification are approved. The current branch/tooling
phase is pre-install and may create disposable source/environment artifacts. It does **not**
by itself authorize a blind `hermes update`, destructive database rewrite, profile reset,
iai change, model/provider change, production cutover, or removal of rollback evidence.

The current resume point is `docs/hermes/hermes-v0225-qualification-status.md`. The next bounded oracle is `scripts/hermes_upgrade/v0225_windows_asyncio_import_diagnostic.py`; do not rerun the P6 functional harness until that diagnostic is reconciled.
