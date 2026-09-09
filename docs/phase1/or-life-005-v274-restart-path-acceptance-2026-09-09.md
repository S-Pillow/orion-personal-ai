# OR-LIFE-005 v2.7.4 Restart Path Acceptance — 2026-09-09

Status: **PASS**

## Scope

Validate the installed Orion v2.7.4-candidate1 lifecycle across a real Windows restart and immediate post-restart Start/Stop cycle.

## Pre-restart state

- Orion clean-off.
- Hermes health: false.
- Ollama health: false.
- Ollama process count: 0.
- launcher-session.json absent.
- active-operation.json absent.
- Installed publication present at `C:\Users\spill\AppData\Local\Orion\operator\versions\2.7.4-candidate1`.
- Desktop Start/Stop shortcuts present and previously validated.
- Hermes and iai LogonTriggers disabled.
- Pre-restart boot identity captured as `2026-09-09T01:04:23.5000000-04:00`.

## Post-restart persistence acceptance

Observed boot identity after restart: `2026-09-09T02:51:57.5000000-04:00`.

Boot identity changed: true.

Post-login manual-off state:

- Hermes health: false.
- Ollama health: false.
- Ollama process count: 0.
- launcher-session.json absent.
- active-operation.json absent.

Installed publication persistence:

- Version directory remained present.
- Hashes remained unchanged for all 10 published files:
  - `orion.py`
  - `protocol.py`
  - `win_process.py`
  - `hermes_worker.py`
  - `Invoke-Orion.ps1`
  - `Start-Orion.ps1`
  - `Stop-Orion.ps1`
  - `Recover-Orion-After-Restart.ps1`
  - `Test-Orion-Preflight.ps1`
  - `orion-config.json`
- Start shortcut unchanged.
- Stop shortcut unchanged.
- `Hermes_Gateway_companion` task remained registered, Ready, one LogonTrigger, enabled false.
- `iai-mcp-daemon` task remained registered, Ready, one LogonTrigger, enabled false.

Result: `OR-LIFE-005 POST-RESTART PASS`.

## Immediate post-restart Start/Stop acceptance

Installed Start was invoked from the installed v2.7.4 publication.

Start result:

- Output: `ORION READY`.
- Exit code: 0.
- Hermes healthy: true.
- Ollama healthy: true.
- Ollama process count: 1.
- launcher-session.json present.
- active-operation.json absent.

Result: `POST-RESTART START PASS`.

Installed Stop was then invoked from the same installed publication.

Stop result:

- Output included `Owned Ollama: stopped`.
- Output included `ORION STOPPED; iai remains vendor-managed.`
- Exit code: 0.
- Hermes healthy: false.
- Ollama healthy: false.
- Ollama process count: 0.
- launcher-session.json absent.
- active-operation.json absent.
- Hermes and iai LogonTriggers remained disabled.

Result: `OR-LIFE-005 RESTART PATH PASS`.

## Acceptance interpretation

The installed Orion v2.7.4-candidate1 publication survives a real Windows restart unchanged, preserves manual-off policy across login, and can subsequently restore a healthy runtime with installed Start and return to clean-off with installed Stop.

This closes the **restart** path of OR-LIFE-005.

The **logoff/logon** path remains to be accepted separately before OR-LIFE-005 is fully closed.
