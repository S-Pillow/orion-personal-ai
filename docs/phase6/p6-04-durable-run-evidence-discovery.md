# P6-04 Durable Per-Run Reminder Evidence - Discovery Plan

Status: **READ-ONLY DISCOVERY PREPARED / IMPLEMENTATION NOT AUTHORIZED**

Accepted Hermes pin: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

## Objective

Close OR-REM-009 without creating a second scheduler, retry queue, delivery engine,
or competing run ledger.

For each scheduled execution Orion ultimately needs authoritative, bounded evidence for:

- Hermes job ID;
- Hermes execution ID / stable run correlation ID;
- scheduled time;
- claim/start/finish time;
- execution outcome;
- delivery state/outcome;
- error/failure classification when applicable;
- complete / failed / unknown terminal interpretation.

The browser must consume this evidence later; it must not manufacture it.

## Known accepted-pin facts entering discovery

The accepted Hermes `cron/executions.py` ledger currently persists:

`id, job_id, source, process_id, pid, process_started_at, status, claimed_at, started_at, finished_at, error`

It therefore already provides a durable execution identifier, exact job correlation,
claim/start/finish timestamps, terminal status, and error text.

Two OR-REM-009 fields are not currently durable in that row:

1. the scheduled fire time for the execution;
2. the terminal delivery outcome.

The accepted source already passes `delivery_outcome` into
`finish_execution(...)`, but `finish_execution` currently uses it only for the
best-effort monitoring projection. Monitoring hashes the job identifier and is telemetry,
not the authoritative per-run ledger.

The scheduler also has the due job's scheduling fields before dispatch. Discovery must
identify the narrowest stable seam where the exact scheduled fire time can be attached to
the execution record without changing due computation or dispatch behavior.

## Discovery questions

1. What exact live `executions.db` schema is present under COMPANION after P6-03?
2. Are there any existing additive columns, migrations, side tables or durable event stores
   at the accepted pin that already capture scheduled time or delivery outcome?
3. At which exact call site is `create_execution()` invoked for built-in scheduler runs?
4. What schedule field/value still represents the fire being claimed at that moment?
5. Does `claim_job_for_fire(..., return_job=True)` preserve the original due instant or
   only the advanced `next_run_at`?
6. At which terminal paths is `delivery_outcome` known before `finish_execution()`?
7. Are interrupted/ownership-lost paths missing a delivery outcome by design, and should
   they durably record an explicit `unknown`/not-attempted state instead of inventing one?
8. Can an additive, backward-compatible Hermes ledger extension solve both missing fields
   while preserving existing APIs and scheduler semantics?
9. What schema migration behavior is safe for an already-existing profile-local SQLite DB?
10. Can the full change be qualified against a disposable copied ledger with zero live job
    creation and zero provider/network use?

## Preferred design order

1. Reuse/extend Hermes' existing `executions.db` ledger.
2. Add only additive schema fields and narrow function parameters if required.
3. Keep `executions.id` as the stable run identifier.
4. Capture scheduled time before any scheduler advancement can destroy its meaning.
5. Persist delivery outcome in the same terminal transaction that persists execution status
   where feasible.
6. Preserve `unknown` when interruption prevents a truthful delivery conclusion.
7. Keep monitoring as a projection of durable truth, not the durable authority.
8. Use an Orion sidecar only if the Hermes ledger cannot be extended safely; any sidecar
   must be evidence-only and unable to fire, retry, suppress or advance work.

## Read-only discovery gate

Run:

`scripts/phase6/Invoke-P6-04-ReadOnlyDiscovery.ps1`

The gate must:

- verify the Orion prep branch and clean worktree;
- verify the accepted Hermes HEAD and expected P6-03 compatibility state;
- inspect accepted pinned source without editing it;
- inspect COMPANION `executions.db` through SQLite `mode=ro`;
- print schema/indices and row count only, not run payload/content;
- print bounded source evidence for execution creation, scheduled-time flow,
  terminal delivery-outcome flow and monitoring projection;
- perform no reminder creation, scheduler tick, provider call, gateway restart or runtime
  state mutation.

## Stop conditions

Stop before design/implementation if:

- Hermes pin or installed compatibility state drifted;
- live execution schema differs materially from the accepted source assumptions;
- an existing durable field/store already solves the gap but has not yet been qualified;
- scheduled-time meaning is ambiguous at the proposed capture point;
- adding evidence would alter due computation, dispatch, retry or delivery semantics;
- discovery requires a live reminder merely to understand the source contract.

Implementation remains separately authorized after discovery evidence is interpreted.


## Discovery result - 2026-10-01

Status: **READ-ONLY DISCOVERY PASSED / DESIGN GAP CONFIRMED / IMPLEMENTATION NOT YET AUTHORIZED**

Observed production state:

- Orion head `73354824b54faa5142562fb118483cb3532e6c30`;
- Hermes head `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`;
- P6-03 patched `cron/jobs.py` SHA-256 unchanged;
- COMPANION `executions.db` present;
- executions row count `0`;
- live schema columns:
  `id, job_id, source, process_id, pid, process_started_at, status, claimed_at, started_at, finished_at, error`;
- no durable `scheduled_at` column;
- no durable `delivery_outcome` column;
- discovery performed no network calls, scheduler ticks, job creation, provider calls,
  gateway restart, or COMPANION cron mutation.

Accepted-source findings:

1. `create_execution()` persists a stable execution ID plus job correlation and
   claim time before executor/provider dispatch.
2. `finish_execution()` already accepts `delivery_outcome`, but only forwards it
   to the best-effort monitoring projection after the terminal ledger transaction.
3. Normal terminal scheduler paths compute one of:
   `failed`, `not_configured`, `delivered`, `suppressed_acked`, or
   `suppressed`, then pass it to `finish_execution()`.
4. Several early/interrupted/ownership-loss terminal paths call `finish_execution()`
   without a delivery outcome. A durable implementation must represent those cases
   truthfully rather than infer delivery success.
5. Built-in ticker flow obtains `due_jobs = get_due_jobs()` before
   `advance_next_runs(...)`. The in-memory due-job record therefore retains the
   fire time that made the job due even though persistent `next_run_at` is advanced
   before execution.
6. Built-in `create_execution(job_id, source="builtin")` currently occurs before
   the worker calls `claim_job_for_fire(..., return_job=True)`, so the original
   due-job value is available at the exact execution-row creation seam.
7. `claim_job_for_fire` advances recurring `next_run_at` in persisted state and
   returns that updated claimed job. Capturing scheduled time after that call would
   therefore be semantically wrong for recurring jobs.
8. Monitoring hashes the job ID and carries delivery outcome only as telemetry, so it
   cannot satisfy authoritative per-run correlation on its own.

### Design conclusion

The narrowest authoritative solution is an additive extension of Hermes'
`cron/executions.py` ledger, not an Orion sidecar.

Proposed additive fields:

- `scheduled_at TEXT`
- `delivery_outcome TEXT`

Proposed API change:

- `create_execution(job_id, *, source, scheduled_at=None)`
- `finish_execution(..., delivery_outcome=None)` persists the already-existing
  argument into the ledger before monitoring projection.

For the built-in ticker path, pass the due job's pre-advance `next_run_at` into
`create_execution(... scheduled_at=...)`.

For direct/manual execution paths, `scheduled_at` must remain null unless the caller
has an authoritative scheduled instant. Do not synthesize one from claim time.

For terminal paths where delivery state cannot be known, persist null rather than
inventing a delivery outcome. Orion can project such rows as delivery-state unknown
where relevant.

### Migration requirement

Because `CREATE TABLE IF NOT EXISTS` does not add columns to an existing SQLite table,
implementation must include an idempotent additive migration in
`_initialize_schema()` that inspects `PRAGMA table_info(executions)` and executes
bounded `ALTER TABLE executions ADD COLUMN ...` statements only for missing columns.

The migration must preserve existing rows and indexes and must not rebuild/drop the table.

### Required implementation qualification

Before any installed-source application:

- disposable new-database schema test;
- disposable old-schema migration test with preserved existing row;
- create/read round trip with scheduled_at;
- terminal completion round trip with each known delivery outcome;
- null delivery outcome for interrupted/unknown paths;
- terminal immutability preserved;
- recover_interrupted_executions preserves scheduled_at and leaves delivery_outcome null;
- list/latest APIs return additive fields without breaking existing callers;
- scheduler built-in path captures pre-advance due time;
- direct path leaves scheduled_at null unless explicitly supplied;
- monitoring receives the same durable delivery outcome;
- no scheduler ownership, due computation, retry, dispatch, delivery, job CRUD or
  jobs.json semantics change;
- no network/provider calls;
- no live COMPANION job creation.

Next authorization unit:
**P6-04 source-controlled compatibility implementation and disposable qualification**.
