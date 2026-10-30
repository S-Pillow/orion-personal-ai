# Hermes v0.22.5 Controlled Migration

Status: **PRE-INSTALL QUALIFICATION**

Prepared: 2026-10-30

## Decision

Orion will migrate the COMPANION Hermes baseline from the accepted pinned checkout
`5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (`v2026.8.27`, Hermes Agent v0.20.6)
to upstream Hermes `v0.22.5` at release commit
`bf0203a794a07aac3ff764972ab9087baa4e4f4e`.

This replaces the prior strategy of indefinitely carrying compatibility patches on the
August Hermes baseline. The migration is controlled rather than a blind `hermes update`
because the installed checkout contains accepted Orion compatibility changes.

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

### Port: P6-03 exact pre-repair jobs.json preservation

Upstream v0.22.5 substantially improves cron store locking, merge safety, shape repair,
and corruption handling, but an automatic repair still rewrites `jobs.json` without first
preserving the exact pre-repair bytes. Orion retains the requirement to save an exact,
durable recovery artifact before any automatic repair rewrite.

The v0.22.5 port is intentionally narrow: preserve the exact locked snapshot immediately
before `save_jobs()` performs a repair rewrite, while leaving upstream merge/locking logic
unchanged.

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
   ports, compile, diff-check, and prove installed Hermes remains byte-for-byte unchanged.
2. **Disposable runtime qualification** — create an isolated v0.22.5 environment and
   exercise native audio, approval source contracts, P6-03 repair preservation, P6-04A
   ledger classification, and migration of the current empty execution schema.
3. **Pre-cutover backup** — preserve the entire accepted dirty Hermes source state, four
   sidecars, dependency ownership metadata, and profile/runtime state required for rollback.
4. **Controlled cutover** — stop Orion through the accepted lifecycle, switch Hermes to the
   qualified v0.22.5 source plus only the two qualified Orion ports, sync the managed venv,
   and restart Orion.
5. **System requalification** — Hermes health/session APIs, Orion Start/Stop ownership,
   accepted HUD, iai integration, approval behavior, cron/reminder compatibility, native
   audio round-trip, then the remaining Phase 4 live PTT/TTS/OFF/barge-in acceptance.
6. **Closure** — only after all runtime gates pass may the old P4/P5/P6-04 compatibility
   patches be treated as retired in production and Phase 4 resume toward merge.

## Current authorization boundary

The migration decision is approved. The current branch/tooling phase is pre-install and
may create disposable source/environment artifacts. It does **not** by itself authorize a
blind `hermes update`, destructive cron database rewrite, profile reset, iai change,
model/provider change, or removal of rollback evidence.
