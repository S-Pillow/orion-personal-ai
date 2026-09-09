# OR-LIFE-005 Post-Logon Persistence Acceptance — 2026-09-09

Status: PASS

Installed Orion publication: `%LOCALAPPDATA%\Orion\operator\versions\2.7.4-candidate1`

Observed acceptance evidence after a normal Windows sign-out/sign-in cycle:

- Boot identity before logoff: `2026-09-09T02:51:57.5000000-04:00`
- Boot identity after logon: `2026-09-09T02:51:57.5000000-04:00`
- Boot identity unchanged, confirming a pure logoff/logon test rather than a restart.
- Post-logon manual-off state preserved:
  - Hermes health: false
  - Ollama health: false
  - Ollama process count: 0
  - `launcher-session.json`: absent
  - `active-operation.json`: absent
- Installed publication remained present.
- SHA-256 hashes remained unchanged for all 10 published files:
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
- Desktop Start/Stop shortcut targets, arguments, and working directories remained unchanged.
- `Hermes_Gateway_companion` persisted in Ready state with one disabled LogonTrigger.
- `iai-mcp-daemon` persisted in Ready state with one disabled LogonTrigger.
- No automatic Orion runtime activation occurred at login.

Acceptance interpretation: OR-LIFE-005 logoff/logon persistence half passed. One final post-logon installed Start -> health -> Stop cycle remains to close OR-LIFE-005 completely.
