# P6-02 Reminder Contract and Hermes Adapter Design — Prepared Research

Status: **DESIGN CANDIDATE / NO IMPLEMENTATION**

Date: 2026-09-29  
Accepted Hermes source pin: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

## 1. Research summary

P6-01 read-only discovery and source review established that the accepted Hermes pin already owns the scheduler and has enough native scheduling machinery to serve as Orion's reminder engine.

Relevant Hermes source surfaces at the accepted pin:

- `cron/jobs.py` — job persistence, schedule parsing, due scanning, dispatch claims, missed one-shot retirement and diagnostics;
- `cron/scheduler.py` — execution and delivery orchestration;
- `cron/executions.py` — durable execution-attempt ledger;
- `cron/incidents.py` — durable recurring failure incidents;
- `tools/cronjob_tools.py` — structured agent-facing cron lifecycle operations;
- `hermes_cli/cron.py` — standalone CLI layer that delegates to the same cron implementation;
- `hermes_cli/subcommands/cron.py` — create/list/edit/pause/resume/run/remove/status/runs/incidents parser;
- `hermes_cli/web_routers/cron.py` — dashboard REST CRUD and run-history routes;
- `gateway/platforms/api_server.py` — accepted COMPANION gateway API; P6-01 found only the cron fire path here, not general dashboard CRUD.

## 2. Important transport finding

The dashboard exposes structured routes such as:

- `GET /api/cron/jobs`
- `GET /api/cron/jobs/{job_id}`
- `GET /api/cron/jobs/{job_id}/runs`
- `POST /api/cron/jobs`
- `PUT /api/cron/jobs/{job_id}`
- pause/resume/trigger/delete routes

But these belong to the Hermes dashboard/web-server surface, not automatically to the currently accepted COMPANION gateway API at `127.0.0.1:8642`.

Therefore P6-02 must not assume those routes are available in the Orion runtime and must not start a second dashboard server merely to gain reminder CRUD.

## 3. Candidate adapter surfaces

### Candidate A — structured Hermes cron tool call in a bounded local adapter

The Hermes CLI itself delegates into `tools.cronjob_tools.cronjob`, which returns structured JSON internally.

Advantages:

- same native validation/mutation path Hermes already uses;
- structured result rather than terminal formatting;
- no direct `jobs.json` writes;
- no second scheduler;
- exact accepted source pin can be checked before use.

Risks:

- this is a source-level integration seam, not a separately versioned public API;
- Orion must run it in the correct COMPANION profile environment;
- vendor import/dependency changes could break it after an upgrade.

Required control:

- hard gate on accepted Hermes commit;
- explicit profile/home resolution;
- fail closed if import or structured response contract differs;
- source-level regression tests pinned to the accepted Hermes version.

### Candidate B — Hermes CLI subprocess

Use `hermes cron ...`.

Advantages:

- clearly user-facing supported interface;
- native scheduler semantics;
- profile/lifecycle behavior already understood by Hermes.

Risks:

- current CLI output is human-formatted;
- parsing terminal output is brittle;
- no JSON switch was observed in the accepted parser for list/runs/status.

Disposition:

- acceptable for operator diagnostics;
- poor primary application adapter unless a machine-readable mode is later found.

### Candidate C — Hermes dashboard REST

Advantages:

- structured HTTP API;
- already supports CRUD and per-job run history;
- natural fit for a local UI.

Risks:

- not proven to be present on the accepted COMPANION gateway;
- requiring the dashboard server to remain running would introduce a new runtime dependency and potentially violate the manual-off/minimal-runtime posture.

Disposition:

- use only if P6-02 proves it is already available inside the accepted runtime without a new service.

### Candidate D — direct `cron.jobs` / `cron.executions` imports

Advantages:

- structured Python data;
- direct access to native store logic;
- no terminal parsing.

Risks:

- easier to accidentally bypass tool-level validation;
- direct mutation calls could create an Orion-specific path that diverges from Hermes' own user-facing semantics.

Disposition:

- reasonable for read-only inspection/tests;
- mutation should prefer the same structured path used by Hermes CLI/tooling.

## 4. Recommended P6-02 transport hypothesis

The leading candidate to qualify is **Candidate A**: a bounded local adapter that invokes the accepted Hermes `cronjob` implementation in the accepted COMPANION profile and returns a narrowed Orion schema.

This is only a hypothesis until the ticket proves:

- correct profile targeting;
- no hidden gateway/service startup;
- no direct store editing;
- no model/LLM invocation for CRUD itself;
- stable structured fields for create/list/update/pause/resume/remove;
- deterministic errors;
- no secret leakage;
- exact behavior when the gateway is manually off.

If Candidate A fails those checks, P6-02 must choose another native Hermes surface rather than creating a scheduler.

## 5. Proposed Orion reminder contract

### Public reminder identity

Orion should expose a stable reminder record such as:

```json
{
  "reminder_id": "orion-reminder:<hermes-job-id>",
  "hermes_job_id": "<native-id>",
  "title": "Dentist appointment",
  "schedule_kind": "once",
  "scheduled_for": "2026-10-01T09:00:00-04:00",
  "timezone": "America/New_York",
  "state": "scheduled",
  "delivery_targets": ["discord"],
  "next_run_at": "2026-10-01T09:00:00-04:00",
  "last_execution_id": null,
  "last_outcome": null,
  "delivery_state": null,
  "attention": null
}
```

The exact shape is not frozen yet. It must remain a projection of Hermes truth, not an independent job record.

### ID rule

Prefer deterministic derivation from the Hermes `job_id`; do not create a second unrelated durable scheduler ID unless required for evidence correlation.

### Name/metadata rule

If Orion needs to distinguish its reminders from unrelated Hermes cron jobs, use a bounded, reversible metadata convention that does not alter scheduling semantics.

Options to qualify:

- reserved name prefix;
- prompt metadata envelope;
- existing native metadata field if Hermes supports one.

Do not overload the reminder text with opaque state that must later be parsed to recover authority.

## 6. Schedule contract

For MVP, P6-02 should prefer a deliberately narrow schedule surface:

### One-shot reminders

Required.

Accept:

- relative delays resolved to an explicit absolute time before persistence; or
- explicit local datetime with timezone.

Persist/project the exact resolved time.

### Recurring reminders

Decision needed.

Hermes supports recurring cron/interval jobs, but Orion should include them only if the owner wants them in the first Phase 6 acceptance slice. If retained, recurring state must not obscure missed-slot semantics.

### Timezone

The contract must define:

- source timezone;
- DST handling;
- display timezone;
- what happens if Windows timezone changes after creation.

Do not let browser locale silently become scheduler authority.

## 7. Reminder state model

Recommended state/source mapping:

| Orion state | Minimum authoritative evidence |
|---|---|
| `scheduled` | Hermes job exists, enabled, future next run |
| `paused` | Hermes job exists and disabled/paused |
| `running` | current execution is durably claimed/running |
| `completed` | terminal execution completed and reminder semantics satisfied |
| `missed` | Hermes missed-one-shot retirement evidence / qualified structured equivalent |
| `failed` | terminal execution failed |
| `delivery_failed` | execution result exists but delivery outcome failed |
| `unknown` | Hermes marks interrupted attempt unknown or state is ambiguous |
| `unavailable` | authoritative source cannot be read/qualified |

Rules:

- approval acknowledgement is not execution success;
- job absence alone is not completion;
- browser storage cannot resurrect any terminal or pending state;
- historical output text must not be parsed as authority unless P6-02 explicitly qualifies a stable machine-readable diagnostic contract.

## 8. Missed one-shot contract

Hermes currently uses `ONESHOT_GRACE_SECONDS = 120`.

A one-shot beyond the grace window is retired without firing when no dispatch/fire claim exists, and Hermes writes a diagnostic containing:

- job ID;
- job name;
- scheduled run time;
- grace window;
- removal time;
- explanation.

P6-02 must decide how Orion obtains that fact without brittle prose parsing.

Preferred order:

1. find/qualify an existing structured missed-run field or event;
2. if none exists, add a narrow structured evidence emission in P6-04 or a Hermes compatibility patch;
3. avoid interpreting Markdown diagnostic prose as the long-term machine contract.

Owner-facing behavior:

- show **Missed**;
- state that it did not run;
- offer an explicit reschedule/run-now choice only through a later authorized action;
- never auto-replay merely because the system came back online.

## 9. Manual-off contract

When Stop Orion/manual-off is active:

- no Orion process schedules independently;
- no hidden Orion timer fires;
- any Hermes reminder behavior is exactly the accepted Hermes/manual-off behavior;
- after restart, Orion reconstructs state from durable Hermes evidence;
- an interrupted run may be `unknown`;
- an old one-shot beyond grace may be `missed`;
- neither is automatically converted into completed or retried.

## 10. Security contract

The Orion bridge must preserve existing controls:

- loopback-only listener;
- UI-cookie requirement;
- same-origin checks for reminder mutations;
- bounded request body;
- allowlisted endpoints;
- exact ID validation;
- no browser access to Hermes API credentials;
- no arbitrary Hermes proxy;
- no arbitrary shell/script path through ordinary reminder CRUD.

The adapter must redact or omit:

- provider credentials;
- environment secrets;
- unrelated cron prompts/jobs if Orion scope is intentionally limited to Orion-owned reminders;
- local file paths not required for UI.

## 11. Proposed bridge API shape

Subject to P6-02 acceptance:

Read-only:

- `GET /api/orion/reminders`
- `GET /api/orion/reminders/{id}`
- `GET /api/orion/reminders/{id}/runs`

Mutation:

- `POST /api/orion/reminders`
- `POST /api/orion/reminders/{id}/pause`
- `POST /api/orion/reminders/{id}/resume`
- `DELETE /api/orion/reminders/{id}`

No generic `/api/orion/cron/*` passthrough.

## 12. P6-02 proof plan

Before implementation, run these gates:

1. accepted Hermes HEAD/profile/worktree verification;
2. source-level adapter-surface inspection;
3. disposable profile test of Candidate A structured list with no jobs;
4. disposable create/list/pause/resume/remove round trip;
5. prove no LLM/provider call occurs for CRUD;
6. prove no second process remains resident;
7. prove COMPANION `jobs.json` remains untouched during disposable tests;
8. document exact structured fields and errors;
9. only then freeze production adapter design.

No live COMPANION reminder should be created during the design ticket.

## 13. P6-03/P6-04 dependencies

P6-02 may define the semantic contract before these are implemented, but P6-05 production CRUD/HUD must not claim full reminder acceptance until:

- P6-03 closes corrupt-store preservation; and
- P6-04 closes scheduled-time + delivery-outcome audit.

## 14. Open questions to resolve tomorrow

1. Does the accepted COMPANION environment permit a structured local call into `tools.cronjob_tools.cronjob` without starting an agent session or provider?
2. What exact environment/profile variables are required to bind that call to `profiles\companion`?
3. Does `cronjob(action="list")` return enough machine-readable state for HUD projection?
4. Is there already a structured missed-one-shot event/field outside the Markdown diagnostic?
5. Can Hermes' monitoring emitter be reused to persist `delivery_outcome` without a second ledger?
6. Where is scheduled fire time still available at execution-claim time?
7. Does a narrow compatibility patch offer a cleaner P6-03/P6-04 result than an Orion sidecar?

These are P6-02/P6-04 discovery questions, not excuses to expand scope.


## 15. Additional pinned-source research: monitoring and dashboard runtime

### Monitoring telemetry is not the missing durable audit ledger

The accepted Hermes pin's `agent/monitoring/cron_health.py` confirms that terminal execution state can be projected with a delivery outcome. The known outcomes are:

- `delivered`
- `failed`
- `suppressed`
- `suppressed_acked`
- `not_configured`

However, the monitoring projection deliberately hashes the Hermes job ID into a content-free key and emits telemetry rather than extending the durable `executions.db` row.

Implication for P6-04:

- the monitoring seam is valuable proof that exact delivery outcome is available at terminal execution time;
- it is **not sufficient by itself** for OR-REM-009 because Orion needs durable, exact per-run correlation to the actual Hermes job/execution;
- P6-04 should inspect the terminal execution call site and favor a narrow durable Hermes ledger extension or equally authoritative structured persistence over treating telemetry as the audit record;
- an Orion sidecar remains a fallback only if it cannot fire, retry, suppress, advance, or otherwise influence scheduling.

### Hermes dashboard REST is a separate runtime surface

The accepted Hermes `hermes_cli/web_server.py` is a separate FastAPI dashboard process (documented as `python -m hermes_cli.main web`, normally on port 9119).

The dashboard also contains Desktop-specific cron ticking behavior: when `HERMES_DESKTOP=1`, the dashboard backend can start a cron ticker because the Desktop topology may not have a gateway doing it.

Implication for P6-02:

- do **not** add/start the Hermes dashboard merely to obtain its structured cron CRUD endpoints;
- doing so would add a new runtime dependency and, in some topologies, another scheduler-capable process;
- Candidate C remains acceptable only if the already-accepted Orion runtime is proven to expose/reuse those routes without adding a second service or scheduler owner;
- otherwise prefer the bounded structured native cron/tool seam in the existing COMPANION environment.

This strengthens Candidate A as the first surface to qualify tomorrow, while still leaving the decision contingent on local proof.
