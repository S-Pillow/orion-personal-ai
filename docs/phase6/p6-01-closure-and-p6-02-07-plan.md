# Phase 6 Reminder Program — P6-01 Closure and P6-02 through P6-07 Preparation

Status: **PREPARED / NOT IMPLEMENTED**

Prepared: 2026-09-29  
Controlling PRD: ORION Master PRD v2.9  
Accepted Hermes baseline: `v2026.8.27` / package `0.20.6` / commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

## 1. Purpose

This document is the prepared execution map for Orion Phase 6 reminders after completion of P6-01 discovery.

It does **not** authorize reminder implementation, production job creation, Hermes configuration changes, service restarts, vendor upgrades, or a second scheduler.

The operating workflow remains native Windows PowerShell + Git/GitHub:

1. inspect and reconcile the current accepted state;
2. run one bounded local command block or repository test gate at a time;
3. interpret evidence before the next step;
4. implement only after the ticket's design/acceptance boundary is explicit;
5. keep GitHub as the durable record of exact source, tests, evidence, and closure.

## 2. P6-01 final architecture decision

### Scheduler owner

**Native Hermes is the authoritative scheduler.**

Orion must not add a parallel general scheduler, timer daemon, always-on worker, or scheduler-owning plugin.

The accepted Hermes scheduler already supplies:

- one-shot and recurring schedules;
- profile-local `cron/jobs.json`;
- temp-file + fsync + replace on the normal save path;
- cross-process job locking and per-job fire fencing;
- one-shot dispatch claims and duplicate suppression;
- persistent execution history in `cron/executions.db`;
- interrupted-run recovery to durable `unknown`;
- Discord, origin, local and other configured delivery targets;
- script/no-agent and monitor-backed jobs;
- gateway-owned ticking rather than a second cron daemon.

### P6-01 demonstrated gaps

The following are Orion requirements that the accepted Hermes pin does not fully close by itself:

1. **Corrupt-store preservation** — `load_jobs()` can auto-repair several malformed-but-parseable shapes by rewriting `jobs.json`; P6-01 did not find an automatic exact pre-repair byte-preservation step.
2. **Missed one-shot presentation** — one-shots more than 120 seconds late do not fire; Hermes retires them and writes an operator-visible diagnostic. Orion needs a durable, user-facing missed state and recovery choice.
3. **Per-run scheduled-time evidence** — the live `executions` table has no `scheduled_at`/`scheduled_for` column.
4. **Per-run delivery evidence** — the live `executions` table has no delivery-outcome column. Delivery outcome is passed to monitoring and the job retains only latest delivery error state.
5. **HUD projection** — no accepted Orion reminder projection exists yet.
6. **Local triggers** — the native substrate exists, but Orion-specific targeting/authorization rules are not yet defined.

## 3. Authority model for all Phase 6 work

The following authority split is frozen unless a later ticket proves it insufficient:

| Concern | Authority |
|---|---|
| Schedule computation / due detection | Hermes |
| Dispatch claim / duplicate suppression | Hermes |
| Scheduler process / ticker | Hermes gateway |
| Job definition persistence | Hermes |
| Execution attempt ledger | Hermes |
| Discord delivery | Hermes |
| Orion reminder UX | Orion HUD |
| Browser state | Presentation only; never durable reminder authority |
| Orion supplemental evidence | Evidence only; never controls firing |
| Manual-off lifecycle | Existing Orion operator controls |
| Persistent memory | iai, unchanged |
| Local trigger execution | Hermes cron script/monitor substrate if later accepted |

Any implementation that requires Orion to decide independently that a reminder is due fails this architecture gate.

## 4. P6-02 — Reminder Contract & Hermes Adapter Design

### Objective

Freeze the semantic contract before any reminder is created.

### Required design decisions

P6-02 must define:

- reminder identity and correlation to a Hermes `job_id`;
- supported MVP schedule classes (at minimum one-shot; recurring only if explicitly retained in scope);
- local timezone and absolute timestamp handling;
- create/list/pause/resume/cancel semantics;
- delivery target contract, including Discord and local/HUD visibility;
- exact state vocabulary;
- missed-reminder semantics;
- interrupted-run `unknown` semantics;
- duplicate/idempotency semantics;
- authority and persistence boundaries;
- browser reconnect behavior;
- manual-off behavior;
- which Hermes integration surface Orion will use.

### Adapter transport decision gate

The accepted Hermes pin exposes several possible surfaces:

1. `hermes cron` CLI, which delegates to the native cron implementation;
2. the Hermes `cronjob` tool implementation, which returns structured JSON internally;
3. cron dashboard REST routes such as `/api/cron/jobs` and per-job `/runs`;
4. direct import of Hermes cron modules from the pinned checkout.

The accepted gateway API on the current COMPANION runtime is **not assumed** to expose the dashboard cron CRUD routes. P6-02 must not create a second web service merely to obtain them.

Preferred decision order:

1. use an existing structured Hermes surface that works in the installed COMPANION environment without another daemon;
2. if that is unavailable, use a bounded local adapter that invokes the same pinned Hermes cron/tool code and enforces the exact accepted commit;
3. use human-formatted CLI parsing only as a last resort;
4. do not directly edit `jobs.json`.

### Proposed state vocabulary

The contract should start from these states and remove any that cannot be supported truthfully:

- `scheduled`
- `paused`
- `running`
- `completed`
- `missed`
- `failed`
- `delivery_failed`
- `unknown`
- `unavailable`

A state may be projected only from durable/current evidence. No browser cache may manufacture it.

### P6-02 acceptance gate

P6-02 closes only when:

- the adapter surface is explicitly selected;
- every state has a named authoritative source;
- mutation operations and read-only operations are separated;
- no second scheduler exists;
- no direct `jobs.json` writer exists;
- manual-off and reconnect semantics are written;
- P6-03/P6-04 dependencies are explicit.

Expected output: design/contract only. No reminder job creation.

## 5. P6-03 — Corrupt-Store Preservation & Fail-Closed Recovery

### Objective

Close OR-REM-007 without taking scheduler ownership away from Hermes.

### Key finding that shapes this ticket

A wrapper that snapshots only before Orion-initiated mutations is **not sufficient** by itself, because the Hermes scheduler can call `load_jobs()` independently and may auto-repair malformed-but-parseable state.

Therefore P6-03 must evaluate preservation at the actual Hermes load/repair boundary.

### Candidate solution order

1. identify an existing supported Hermes pre-repair/backup hook if one exists;
2. if none exists, design a narrow accepted-pin Hermes compatibility patch that preserves the exact original `jobs.json` bytes before automatic repair;
3. keep the preservation artifact profile-local and operator-inspectable;
4. use atomic creation for the preservation artifact;
5. never silently replace an unreadable/unrepairable store with empty state;
6. preserve the original before any canonical rewrite;
7. record why preservation occurred and which source file/hash it corresponds to.

A generic quick snapshot is useful recovery coverage but does not by itself prove preservation of the exact bytes that triggered an automatic repair.

### Fixture-only test matrix

Testing must use a disposable profile/root, never the live COMPANION `jobs.json`, for:

- invalid JSON;
- valid JSON with wrong top-level scalar;
- bare-list shape;
- ID-keyed map;
- invalid control character fallback;
- unreadable file simulation where feasible;
- preservation-write failure;
- repair-write failure.

Required result: original bytes remain inspectable whenever repair is attempted; unrepairable state fails closed.


### P6-03 disposable qualification result

Status: **DISPOSABLE IMPLEMENTATION QUALIFIED / PRODUCTION PATCH NOT AUTHORIZED**

Accepted qualification head: `bcec42f4a18514a7896fc6ac90f6c7a758fc7742`.

The disposable qualification archived the exact accepted Hermes commit into a
temporary source tree, patched only that temporary copy, bound a disposable
`HERMES_HOME`, and exercised the repair boundary without modifying installed
Hermes or the COMPANION profile.

Accepted evidence:

- healthy canonical `jobs.json` loaded without creating a recovery artifact;
- non-empty bare-list input was preserved byte-for-byte before canonical repair;
- ID-keyed-map input was preserved byte-for-byte before canonical repair;
- control-character fallback input was preserved byte-for-byte before canonical repair;
- invalid/unrepairable JSON remained unchanged and failed closed;
- wrong top-level scalar remained unchanged and failed closed;
- forced preservation failure blocked repair and left the original untouched;
- no external network attempt was observed;
- no scheduler was started;
- no job run was invoked;
- Orion HEAD/worktree remained unchanged;
- installed Hermes HEAD/worktree remained unchanged;
- COMPANION cron metadata remained unchanged;
- successful disposable artifacts were removed after qualification.

The qualified implementation seam is therefore:

1. preserve the exact on-disk `jobs.json` bytes immediately before an automatic
   repair rewrite;
2. publish the recovery artifact in a profile-local `cron/recovery/` location;
3. encode a bounded repair reason in the artifact filename;
4. flush and fsync the artifact contents before publication;
5. use atomic rename publication where supported;
6. on POSIX, fsync the recovery directory after publication;
7. on Windows, rely on the artifact file fsync plus rename publication because
   directory fsync is not supported through the same mechanism;
8. fail closed if preservation cannot complete;
9. do not change parse tolerance, scheduler ownership, CRUD semantics, dispatch,
   delivery, or the repair-free peek path.

The qualification does **not** authorize modifying the installed Hermes checkout
or COMPANION runtime. A source-controlled compatibility patch against the exact
accepted Hermes pin must be reviewed separately before any production mutation.

## 6. P6-04 — Durable Per-Run Reminder Evidence

### Objective

Close the P6-01 audit gaps without creating a second scheduler or retry queue.

### Required evidence

For each reminder execution Orion must be able to reconstruct:

- Hermes job ID;
- Hermes execution ID;
- scheduled time;
- actual claim/start/finish time;
- execution outcome;
- delivery state/outcome;
- error when applicable;
- a stable run correlation ID;
- whether state is complete, failed, or unknown.

### Design rule

Prefer extending/using Hermes' own execution/monitoring seams over an Orion ledger that independently decides run truth.

P6-04 research order:

1. qualify the existing Hermes monitoring emitter that receives `delivery_outcome`;
2. determine whether scheduled fire time is available at claim/dispatch time through an existing callback/event;
3. if both can be durably captured in Hermes without changing scheduler semantics, use that seam;
4. otherwise evaluate a narrow schema-compatible Hermes execution-ledger extension;
5. use an Orion sidecar only if it is explicitly evidence-only and cannot trigger/retry/suppress jobs.

An Orion evidence store must never become a due-work queue.

## 7. P6-05 — Reminder CRUD + HUD Projection

### Objective

Expose reminders through Orion while keeping Hermes authoritative.

### Backend/adapter responsibilities

- structured create/list/get/pause/resume/cancel operations;
- accepted Hermes commit/profile verification;
- strict allowlisting of fields;
- no arbitrary command/script injection through ordinary reminder text;
- exact job ID correlation;
- read-only execution-history projection;
- safe handling of missing/corrupt/unavailable authority;
- no secret-bearing job bodies returned to the browser unless required for the UI contract.

### HUD responsibilities

The HUD may show:

- reminder title/summary;
- next scheduled time;
- state;
- last run outcome;
- delivery outcome;
- missed/unknown attention state;
- safe management controls.

The browser may persist only locator/preferences suitable for presentation. Reconnect must re-query authoritative reminder state.

### Security

Mutation endpoints must retain the established Orion loopback, UI-cookie, same-origin and bounded-request controls. Reminder CRUD must not become an arbitrary Hermes proxy.

## 8. P6-06 — Live Reminder Acceptance

### Objective

Prove the integrated behavior on the installed COMPANION runtime.

### Progressive acceptance matrix

Run cheap/disposable tests before live delivery:

1. repository/unit contract tests;
2. disposable Hermes profile/store tests;
3. installed read-only qualification;
4. one bounded live one-shot reminder;
5. Discord delivery confirmation;
6. HUD projection/reconnect confirmation;
7. manual-off missed-reminder test;
8. restart/interrupted-run `unknown` test;
9. duplicate-suppression test;
10. delivery-failure test;
11. sibling/failure-isolation test;
12. corruption-preservation test using disposable state only.

### Manual-off invariant

When Orion/Hermes is intentionally stopped, no Orion-owned hidden scheduler may continue firing reminders.

On restart, Orion must report what Hermes can prove. A one-shot outside the Hermes grace window must be shown as missed/retired rather than silently marked completed.

### Delivery semantics wording

P6-06 must document the strongest semantics actually proven. Do not write “exactly once” unless the full end-to-end delivery path proves it. Prefer explicit wording such as:

- at-most-once scheduler dispatch with durable claim fencing;
- delivery may be unknown after an interruption;
- duplicate suppression is bounded to the proven Hermes claim/fence behavior.

## 9. P6-07 — Local Trigger Reuse

### Objective

Reuse Hermes trigger mechanisms without creating a second watcher framework.

### Native substrate

The accepted Hermes pin already supports:

- `no_agent=True` script-only jobs;
- pre-run scripts;
- monitor scripts;
- monitor URLs;
- script containment under the Hermes profile scripts directory;
- sanitized subprocess environment;
- scheduler-owned cadence and delivery.

### Orion rules to define before enabling

- local trigger must target an explicit existing Orion task/session/workflow;
- trigger does not create a new autonomous goal runtime;
- ordinary approval, filesystem, cloud, communication and manual-off boundaries remain in force;
- no arbitrary script path from browser/user payload;
- scripts must be allowlisted or separately created under explicit authorization;
- empty/no-change conditions should remain silent where supported;
- trigger state must use the same durable recovery/duplicate semantics as reminders.

If no concrete owner use case exists after P6-06, P6-07 may close as **supported substrate / deferred activation** rather than adding unused machinery.

## 10. Planned source layout

Likely Orion-owned implementation locations, subject to P6-02 design acceptance:

- `hud/reminder_projection.py` — pure authority-free normalization;
- `hud/reminder_adapter.py` — bounded Hermes adapter, no scheduling logic;
- `hud/orion_hud_bridge.py` — allowlisted loopback reminder endpoints;
- `hud/tests/test_reminder_projection.py`;
- `hud/tests/test_reminder_adapter.py`;
- `hud/tests/test_reminder_bridge.py`;
- `scripts/phase6/` — operator qualification and live acceptance gates;
- `docs/phase6/` — contracts, evidence and closure records.

A Hermes compatibility patch, if P6-03/P6-04 proves one necessary, must be source-controlled separately and must pin the exact accepted Hermes commit.

## 11. Risk register

| Risk | Control |
|---|---|
| Orion accidentally becomes scheduler | No due-time computation or independent dispatch in Orion |
| Direct jobs.json mutation | Prohibited; use native Hermes code/surface |
| Auto-repair destroys forensic source | P6-03 preservation at true repair boundary |
| Duplicate reminder delivery | Reuse Hermes claims/fences; test live |
| Browser shows stale completed reminder | Re-query authority on reconnect; locator-only browser persistence |
| Missed reminder silently disappears | Durable missed projection + recovery choice |
| Delivery happened but completion save failed | Preserve `unknown`/ambiguous state; no naive replay |
| Adapter depends on unqualified vendor internals | exact commit gate + compatibility tests |
| Dashboard REST requires extra service | Do not use it unless already available in accepted runtime |
| Local trigger becomes arbitrary execution API | allowlisted scripts/targets and existing approvals |
| Phase 6 changes manual-off lifecycle | explicit stop/start tests; no second daemon |
| Phase 4 or Persistent Goal Mode scope leaks in | both remain parked/deferred unless separately authorized |

## 12. Stop conditions

Stop the active ticket and report before mutation if any of the following is observed:

- installed Hermes HEAD differs from the accepted pin;
- COMPANION profile cannot be resolved exactly;
- an implementation requires a second scheduler/daemon;
- a proposed adapter must write `jobs.json` directly;
- corruption handling would discard the original source;
- a live test requires production reminder creation before explicit authorization;
- a delivery/recovery state cannot be proven from durable/current evidence;
- a required action would change Phase 4, PGM, memory ownership, lifecycle authority, or vault-action authority.

## 13. Prepared next action

Tomorrow's starting unit is **P6-02 — Reminder Contract & Hermes Adapter Design**.

Start with the read-only preflight in:

`scripts/phase6/Invoke-P6-ReadOnlyPreflight.ps1 -Ticket P6-02`

Then inspect the exact structured Hermes adapter options and freeze the contract before creating any reminder.
