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
