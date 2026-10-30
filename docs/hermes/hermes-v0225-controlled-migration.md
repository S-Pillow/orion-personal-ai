# Hermes v0.22.5 Controlled Migration

Status: **PRE-INSTALL QUALIFICATION**

Prepared: 2026-10-30

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

### Retire: P4-04A Hermes audio gateway patch

Hermes v0.22.5 natively exposes authenticated `/api/audio/transcribe` and
`/api/audio/speak` gateway routes and pins `edge-tts==7.3.1`. The old Orion audio gateway
backport must not be reapplied to the new baseline.

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

1. **Disposable source candidate** — clone exact v0.22.5, apply only the two surviving
   Orion compatibility ports, compile, diff-check, verify native audio/approval and
   `edge-tts==7.3.1`, and prove installed Hermes remains byte-for-byte unchanged.
2. **Reported-issue relevance qualification** — exercise the exact COMPANION profile and
   Windows topology against the v0.22.5 issues that could cross into Orion, Chat, Memory,
   Voice, or Security. Non-core defects may be recorded as accepted limitations.
3. **Disposable runtime qualification** — create an isolated v0.22.5 environment and
   prove the five hard gates as far as isolation permits: Hermes/API health, session/chat
   contracts, memory/profile-home boundaries, native audio, approval/security contracts,
   P6-03 repair preservation, P6-04A classification, and safe handling of the current empty
   execution schema.
4. **Pre-cutover backup** — preserve the entire accepted dirty Hermes source state, four
   sidecars, dependency ownership metadata, COMPANION profile/runtime state, memory/vault
   evidence, and database files required for rollback.
5. **Controlled cutover** — only after the candidate is qualified, stop Orion through the
   accepted lifecycle, switch Hermes to the qualified exact source plus only the qualified
   Orion ports/mitigations, sync the managed environment, and restart Orion. Do not use a
   blind updater against the dirty accepted checkout.
6. **Production hard-gate requalification** — Orion lifecycle/runtime, Memory, Voice,
   Chat/session behavior, and Security all must pass on Windows. Cron/LSP/Desktop failures
   do not block unless evidence shows they cross one of those five boundaries.
7. **Closure** — only after all five production hard gates pass may the old P4/P5/P6-04
   compatibility patches be treated as retired in production and Phase 4 resume toward
   merge.

## Current authorization boundary

The upgrade project and disposable qualification are approved. The current branch/tooling
phase is pre-install and may create disposable source/environment artifacts. It does **not**
by itself authorize a blind `hermes update`, destructive database rewrite, profile reset,
iai change, model/provider change, production cutover, or removal of rollback evidence.
