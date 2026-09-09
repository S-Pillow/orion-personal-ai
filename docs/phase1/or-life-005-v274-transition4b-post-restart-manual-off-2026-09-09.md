# OR-LIFE-005 v2.7.4 Transition 4B — Post-Restart Manual-Off Acceptance

Date: 2026-09-09
Status: PASS

## Scope

Read-only post-login verification after the required real Windows Restart following Transition 4A legacy-control archive/removal. No Orion/Hermes start action was performed before this check.

## Observed post-login runtime state

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- Hermes-related process count: 0
- iai-related process count: 0

## Legacy active entry points

All remained absent after restart:

- `%LOCALAPPDATA%\Orion\operator\Start-Orion.ps1`
- `%LOCALAPPDATA%\Orion\operator\Stop-Orion.ps1`
- Desktop `Start Orion.lnk`
- Desktop `Stop Orion.lnk`

## Lifecycle metadata

- `launcher-session.json`: absent
- `active-operation.json`: absent

## Scheduled Task manual-off state

`Hermes_Gateway_companion`:
- State: Ready
- Logon trigger count: 1
- Logon trigger enabled: false

`iai-mcp-daemon`:
- State: Ready
- Logon trigger count: 1
- Logon trigger enabled: false

## Acceptance

`TRANSITION 4B PASS`

The real Windows restart preserved manual-off state, legacy launcher entry points remained inactive, no launcher session/recovery state existed, and Hermes/iai LogonTriggers remained disabled.

## Boundary

This acceptance clears the one-time transition for real v2.7.4 installation. Orion must remain unstarted until installation/publication verification is complete.
