# Tomorrow Resume Prompt — Orion Phase 6

Use the following prompt to resume work cleanly:

---

We are resuming the Orion Personal AI project.

Repository: `S-Pillow/orion-personal-ai`

Start by reconciling GitHub, not by guessing from memory.

Current durable checkpoint:

- `main` was updated through PR #53 after PR #52/P5-03C merged.
- Phase 5 vault-action/reconnect work is closed through P5-03C.
- Phase 4 live voice acceptance remains parked by owner decision. Do not resume or redesign voice unless I explicitly ask.
- Persistent Goal Mode remains deferred/discussion-only. Do not implement it.
- P6-01 reminder discovery is complete.
- Accepted Hermes pin remains:
  - tag `v2026.8.27`
  - package `0.20.6`
  - commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- P6-01 architecture decision: **native Hermes owns reminder scheduling**. Do not add a second scheduler, daemon, timer service, or scheduler-owning plugin.
- P6-01 demonstrated gaps:
  1. corrupt-but-repairable jobs.json can be auto-rewritten without proven exact pre-repair preservation;
  2. one-shots more than 120 seconds late are retired with a diagnostic rather than fired;
  3. live executions.db has no scheduled-time column;
  4. live executions.db has no durable delivery-outcome column;
  5. Orion HUD reminder projection is not implemented;
  6. local triggers must reuse Hermes script/no-agent/monitor mechanisms if enabled.
- Live read-only verification confirmed the COMPANION executions table fields:
  `id, job_id, source, process_id, pid, process_started_at, status, claimed_at, started_at, finished_at, error`.
- The prep branch is:
  `prep/phase6-p6-02-p6-07`

Read these files from that branch before proposing work:

1. `docs/phase6/p6-01-closure-and-p6-02-07-plan.md`
2. `docs/phase6/p6-02-reminder-contract-adapter-research.md`
3. `scripts/phase6/Invoke-P6-ReadOnlyPreflight.ps1`

Our proven workflow is native Windows PowerShell + Git/GitHub. There is no Builder Agent. Work gate-by-gate:

1. read/reconcile exact repo and installed state;
2. give me one bounded PowerShell block at a time when local evidence is needed;
3. I run it and paste the complete output;
4. interpret before issuing the next command;
5. discovery is read-only first;
6. implementation is separately authorized;
7. test progressively;
8. GitHub is the durable record;
9. PR readiness and merge are separate boundaries.

Begin with **P6-02 — Reminder Contract & Hermes Adapter Design**, not implementation.

First task tomorrow:

- verify the prep branch still descends from current main;
- review the prepared Phase 6 plan and research;
- run or ask me to run:
  `scripts/phase6/Invoke-P6-ReadOnlyPreflight.ps1 -Ticket P6-02`
- then resolve the adapter transport decision.

The leading adapter hypothesis is a bounded structured call into the accepted Hermes cron/tool implementation because `hermes cron` delegates to the same native code, while human CLI output is brittle and the dashboard REST routes are not assumed to exist on the accepted 8642 gateway. Treat that as a hypothesis to prove, not an already accepted implementation decision.

P6-02 must freeze:

- reminder identity;
- one-shot/recurring scope;
- timezone semantics;
- create/list/pause/resume/cancel behavior;
- state vocabulary and authoritative source for each state;
- manual-off/restart/missed behavior;
- duplicate/idempotency wording;
- delivery target rules;
- browser reconnect behavior;
- exact Hermes adapter surface.

Do not create a real COMPANION reminder during P6-02 unless I separately authorize it.

After P6-02, follow the prepared P6-03 through P6-07 sequence. Do not skip the corrupt-store preservation and per-run audit gaps just to get a UI working quickly.

---
