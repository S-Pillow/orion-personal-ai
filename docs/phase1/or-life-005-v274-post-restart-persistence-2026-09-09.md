# OR-LIFE-005 — v2.7.4 Post-Restart Persistence Acceptance

Date: 2026-09-09

Status: PASS

## Scope

Validate the installed Orion v2.7.4 candidate across a real Windows Restart before any post-restart Start action.

## Evidence

- Pre-restart boot identity: `2026-09-09T01:04:23.5000000-04:00`
- Post-restart boot identity: `2026-09-09T02:51:57.5000000-04:00`
- Boot identity changed: yes
- Hermes health after login: false
- Ollama health after login: false
- Ollama process count after login: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent
- Installed publication directory persisted: `C:\Users\spill\AppData\Local\Orion\operator\versions\2.7.4-candidate1`
- All 10 published files retained identical SHA-256 hashes across restart:
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
- Desktop Start/Stop shortcut target/arguments/working-directory contract persisted unchanged.
- Scheduled Tasks persisted:
  - `Hermes_Gateway_companion`: Ready, one LogonTrigger, disabled
  - `iai-mcp-daemon`: Ready, one LogonTrigger, disabled

## Acceptance interpretation

The real Windows Restart preserved installed source, configuration, shortcut publication, task registrations, and the required manual-off policy. No Orion/Hermes/Ollama runtime was started at login and no lifecycle metadata was present.

This satisfies the persistence/manual-off portion of OR-LIFE-005 for the installed v2.7.4 candidate. The restart path is not fully closed until an immediate post-restart installed Start -> health verification -> Stop cycle is accepted.

## Safety

No files were modified by the acceptance probe, no runtime was started, and no Scheduled Task configuration was changed.
