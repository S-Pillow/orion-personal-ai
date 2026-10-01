# Resume Prompt - Orion Phase 6

Use this prompt to resume the Orion Personal AI project cleanly.

---

We are resuming the Orion Personal AI project.

Repository: `S-Pillow/orion-personal-ai`

Start by reconciling GitHub and the installed Hermes state. Do not guess from memory.

## Current durable checkpoint

- Phase 5 is closed through P5-03C.
- Phase 4 live voice acceptance remains parked by owner decision. Do not resume or redesign voice unless explicitly requested.
- Persistent Goal Mode remains deferred/discussion-only.
- Accepted Hermes pin remains:
  - tag `v2026.8.27`
  - package `0.20.6`
  - commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- Native Hermes is the authoritative reminder scheduler. Do not add a second scheduler, daemon, timer service, or scheduler-owning plugin.
- Phase 6 prep branch:
  `prep/phase6-p6-02-p6-07`
- PR #54 remains the Phase 6 preparation/integration PR.

## P6-02

P6-02 transport qualification is complete.

The selected transport is a bounded Orion adapter over the native structured
`tools.cronjob_tools.cronjob()` implementation, explicitly bound to the
COMPANION `HERMES_HOME`.

Do not use direct `jobs.json` writes or human-formatted CLI parsing as the primary adapter.

## P6-03 current state

P6-03 source-controlled compatibility work is substantially complete.

The installed Hermes checkout still has Git HEAD:

`5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

The qualified local P6-03 compatibility patch has been applied to installed:

`cron/jobs.py`

Installed patched SHA-256:

`3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5`

The source-application run passed the full revised disposable fixture suite against
the installed patched source.

Verified fixture coverage includes:

- healthy store;
- bare-list repair;
- ID-keyed-map repair;
- control-character repair;
- combined ID-map + control-character repair;
- race re-check proving repair re-reads under Hermes' existing jobs lock;
- invalid JSON;
- wrong top-level scalar;
- unreadable-store simulation;
- preservation-write failure;
- repair-write failure.

The patch preserves the exact byte sequence that produced the repair decision,
records its SHA-256 in the recovery artifact name, and fails closed if preservation
cannot complete.

Production source application backup:

`C:\Users\spill\AppData\Local\hermes\orion-compat-backups\p6-03-20260930-074533\cron-jobs.py.original`

Manifest:

`C:\Users\spill\AppData\Local\hermes\orion-compat-backups\p6-03-20260930-074533\manifest.json`

P6-03 live activation is complete. The first start-only activation reached Hermes' native Windows start path; the Orion wrapper then failed during post-start verification because a helper parameter named `$Pid` collided with PowerShell's automatic `$PID` variable. The helper was corrected without issuing a second start. A separate read-only reconciliation then proved the COMPANION gateway is running, the scheduler ticker heartbeat is newer than the gateway process start, the cron job count remains 0, and the accepted Hermes/P6-03 source state is unchanged.

P6-03 is therefore closed.

## Prepared live-activation work

The following are prepared ahead of time:

1. `docs/phase6/p6-03-live-activation-plan.md`
2. `scripts/phase6/Invoke-P6-03-LiveActivationDiscovery.ps1`
3. `scripts/phase6/Invoke-P6-03-LiveActivation.ps1`

The read-only discovery gate must run before restart authorization.

Discovery must identify the exact COMPANION gateway ownership:

- profile-scoped Windows Scheduled Task;
- Startup-folder fallback;
- manual/unsupervised process;
- Windows service;
- or an ambiguous/unexpected state.

The prepared generic activation script supports only:

- `windows-scheduled-task`
- `windows-startup`

If discovery shows any other mode, do not force that script. Prepare a
mode-specific activation unit instead.

The activation script also refuses to restart if COMPANION `cron/jobs.json`
contains any jobs, to avoid accidentally exercising real reminder work during
the activation gate.

The eventual restart uses Hermes' own accepted Windows lifecycle implementation,
`hermes_cli.gateway_windows.restart()`, not ad hoc taskkill/start commands.

After restart, acceptance requires:

- a new live gateway PID;
- unchanged accepted Hermes Git HEAD;
- unchanged expected Hermes dirty-file set;
- unchanged P6-03 patch SHA-256;
- COMPANION jobs still absent/empty;
- a fresh COMPANION ticker heartbeat after restart, establishing that the new
  post-patch gateway reached scheduler operation.

Restart itself still requires explicit owner authorization.

## Files to read first

Read these files from the prep branch before proposing work:

1. `docs/phase6/p6-01-closure-and-p6-02-07-plan.md`
2. `docs/phase6/p6-02-reminder-contract-adapter-research.md`
3. `docs/phase6/p6-03-production-application-plan.md`
4. `docs/phase6/p6-03-live-activation-plan.md`
5. `scripts/phase6/Invoke-P6-03-LiveActivationDiscovery.ps1`
6. `scripts/phase6/Invoke-P6-03-LiveActivation.ps1`

## Resume workflow

Our proven workflow is native Windows PowerShell + Git/GitHub. There is no Builder Agent.

1. Reconcile the exact PR #54 head and CI state.
2. Confirm the local Orion prep branch is clean and at that head.
3. Treat P6-03 as closed; do not rerun discovery/start/restart unless new evidence requires it.
4. Begin P6-04 with read-only discovery of Hermes execution/monitor seams for durable per-run reminder evidence.
5. Preserve Hermes as scheduler owner and do not change delivery or CRUD semantics while discovering evidence gaps.
6. Keep GitHub as the durable acceptance record.

Do not create a real COMPANION reminder during P6-03 activation.
Do not begin P6-04 until P6-03 closure is recorded.
Do not touch Phase 4 voice or Persistent Goal Mode unless separately requested.

---
