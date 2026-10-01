# P6-03 Live Activation Plan

Status: **PREPARED AHEAD / DISCOVERY NOT YET RUN / RESTART NOT AUTHORIZED**

Prepared: 2026-09-30  
Accepted Hermes pin: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`  
Installed P6-03 `cron/jobs.py` SHA-256: `3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5`

## Current durable state

P6-03 source application is complete and accepted. The installed Hermes checkout
retains the accepted Git HEAD and carries the qualified local compatibility
modification to `cron/jobs.py`.

The source application did not restart the gateway. Therefore a currently running
COMPANION gateway may still have pre-patch Python modules in memory.

The read-only discovery script is already prepared and CI-qualified:

`scripts/phase6/Invoke-P6-03-LiveActivationDiscovery.ps1`

It must be run before choosing a restart path.

## Activation authority

Live activation is a separate mutation boundary.

The activation unit may:

- restart the already-running COMPANION Hermes gateway through the accepted Hermes
  Windows lifecycle implementation;
- allow ordinary gateway runtime files, logs, PID/state records and ticker heartbeat
  files to change as a natural result of that restart.

The activation unit must not:

- change the Hermes Git HEAD;
- edit any additional Hermes source file;
- change the P6-03 patched `cron/jobs.py`;
- create, edit or delete reminder jobs;
- add/remove/reconfigure Scheduled Tasks or Startup persistence;
- upgrade Hermes;
- clean/reset/stash existing compatibility artifacts;
- run a corruption test against COMPANION;
- begin P6-04.

## Discovery decision

The discovery result determines the supervisor mode.

The ahead-of-time activation script supports only:

- `windows-scheduled-task`
- `windows-startup`

If discovery reports a manual/unsupervised gateway, ambiguous persistence, a
Windows service, missing PID evidence, or any unexpected mode, stop and prepare a
mode-specific activation unit instead of forcing the generic restart path.

## Pre-restart safety gate

Before restart, the activation script must prove:

1. Orion is on the Phase 6 prep branch with a clean worktree.
2. Installed Hermes HEAD is the accepted pin.
3. Installed Hermes worktree contains exactly the accepted P4/P5 artifacts plus
   the P6-03 `cron/jobs.py` modification.
4. Installed `cron/jobs.py` has the accepted P6-03 SHA-256.
5. COMPANION profile resolves exactly.
6. The expected persistence/supervisor mode matches current Windows evidence.
7. A live COMPANION gateway PID exists.
8. COMPANION `cron/jobs.json` is either absent or canonical and contains zero
   jobs. Any non-empty or malformed store blocks activation so the restart cannot
   accidentally exercise real reminder work during this gate.

## Restart path

For an accepted Scheduled Task or Startup-backed native Windows gateway, use the
accepted Hermes implementation:

`hermes_cli.gateway_windows.restart()`

with:

- installed Hermes venv Python;
- `HERMES_HOME` bound to the COMPANION profile;
- `HERMES_PROFILE=companion`;
- working directory bound to the accepted Hermes checkout.

This preserves Hermes lifecycle ownership. Orion does not kill/start the gateway
with ad hoc process commands.

The accepted Hermes Windows restart path drains/stops the known gateway, waits for
absence, escalates only through Hermes' own bounded implementation if necessary,
then starts through Hermes' canonical detached Windows launch path and verifies a
running gateway.

## Post-restart acceptance

Activation passes only when:

- a new live COMPANION gateway PID is present;
- the PID differs from the pre-restart gateway PID;
- the installed Hermes HEAD is unchanged;
- the installed Hermes dirty-file set is unchanged from the expected P6-03 state;
- patched `cron/jobs.py` retains the qualified SHA-256;
- COMPANION `jobs.json` remains absent/empty;
- a fresh COMPANION cron ticker heartbeat is observed after the restart, proving
  the newly started gateway reached scheduler operation after the patched source
  was already installed;
- no reminder/job was created by the activation script.

A fresh heartbeat plus a post-patch process start establishes the bounded live
activation claim. It does not require corrupting COMPANION state.

## Failure and rollback boundary

A failed restart is not a source rollback trigger by itself. The already-qualified
source patch remains installed unless evidence shows the patch caused the failure.

If the new gateway does not become healthy:

1. preserve the restart/discovery output;
2. do not repeatedly restart;
3. inspect gateway status/log evidence read-only;
4. decide separately whether to retry restart or restore P6-03 source from the
   existing external backup.

The source rollback backup remains:

`%LOCALAPPDATA%\hermes\orion-compat-backups\p6-03-20260930-074533\cron-jobs.py.original`

Source rollback plus a subsequent restart requires separate authorization.

## Discovery result - 2026-09-30

Status: **REGISTERED SCHEDULED TASK / GATEWAY CURRENTLY STOPPED**

Read-only discovery passed with the following production evidence:

- Orion head: `ce71de44db050f7ea8e8f2bb7edee4778662ea5c`;
- installed Hermes HEAD: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`;
- installed P6-03 `cron/jobs.py` SHA-256: `3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5`;
- COMPANION task name: `Hermes_Gateway_companion`;
- Scheduled Task present and state `Ready`;
- last task result `0`;
- no Startup-folder fallback present;
- no COMPANION gateway PID file present;
- no live gateway process detected;
- no Windows service parent/supervisor detected;
- `gateway_state.json` reports `stopped`, updated `2026-09-29T08:19:47.281639+00:00`;
- Orion, Hermes and COMPANION cron metadata remained unchanged;
- no restart was performed.

This means the generic restart path is **not applicable** to the current state because
there is no live gateway PID to restart. The correct bounded activation for the observed
state is a **start-only** operation through Hermes' native Windows lifecycle implementation,
while preserving the registered Scheduled Task as the persistence/supervisor mechanism.

Prepared next gate:

`scripts/phase6/Invoke-P6-03-LiveActivationStart.ps1`

It is intentionally limited to the exact discovered state: Scheduled Task present, Startup
fallback absent, gateway stopped, no live PID, and COMPANION cron store empty/absent. It uses
`hermes_cli.gateway_windows.start()`, not ad hoc process creation. Running it still requires
separate explicit owner authorization.
