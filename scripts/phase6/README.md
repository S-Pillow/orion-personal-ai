# Phase 6 operator scripts

These scripts support the native Windows PowerShell + Git/GitHub workflow for Orion Phase 6 reminders.

They are preparation/qualification tooling, not a second scheduler.

## Current prepared script

### Invoke-P6-ReadOnlyPreflight.ps1

Usage:

```powershell
.\scripts\phase6\Invoke-P6-ReadOnlyPreflight.ps1 -Ticket P6-02
```

Accepted ticket values:

- P6-02
- P6-03
- P6-04
- P6-05
- P6-06
- P6-07

The script:

- verifies the accepted Hermes commit;
- records Orion/Hermes worktree state before and after;
- checks Python resolution;
- inventories COMPANION cron artifacts by metadata only;
- reads only SQLite schema, never execution rows;
- does not print jobs.json reminder bodies;
- checks mutation-enabling environment variables by presence only;
- shows bounded source matches relevant to the selected ticket;
- fails if either repo is mutated during the probe.

It does **not** start/stop Hermes, create jobs, run due jobs, change configuration, or perform Git mutation.

## Planned scripts by ticket

Do not create these merely to fill out the folder. Add each only when its ticket has a concrete accepted contract.

### P6-02

Possible follow-on:

`P6-02-Disposable-Adapter-Qualification.ps1`

Purpose: qualify the selected structured Hermes adapter against an isolated profile/root without touching COMPANION.

Must prove:

- correct profile resolution;
- structured create/list/pause/resume/remove results;
- no LLM/provider call for CRUD;
- no resident extra service;
- no COMPANION cron mutation.

### P6-03

Possible follow-on:

`P6-03-Corrupt-Store-Fixture-Matrix.ps1`

Purpose: create disposable malformed jobs.json fixtures and qualify preservation/fail-closed behavior.

Must never point at the live COMPANION cron directory.

### P6-04

Possible follow-on:

`P6-04-Audit-Evidence-Fixture.ps1`

Purpose: qualify scheduled-time and delivery-outcome evidence against disposable executions.

Must prove the evidence layer cannot fire, retry, suppress, or reschedule work.

### P6-05

Likely repository tests should carry most of the proof. Add operator scripts only for installed read-only projection qualification.

### P6-06

Expected live gates should be split so consequential behavior is never hidden in one giant script:

1. read-only installed preflight;
2. separately authorized bounded reminder creation;
3. delivery observation;
4. manual-off/missed recovery;
5. restart/unknown recovery;
6. duplicate-suppression proof;
7. failure-isolation proof;
8. exact cleanup.

Each gate must print enough identity/state evidence to resume safely after interruption.

### P6-07

Possible follow-on:

`P6-07-Local-Trigger-Disposable-Qualification.ps1`

Purpose: prove an allowlisted script/no-agent/monitor job in disposable state.

It must not create arbitrary executable paths from user/browser input.

## Rule

Scripts are added when they make evidence reproducible. They do not authorize their own execution.
