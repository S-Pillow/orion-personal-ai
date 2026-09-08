# OR-LIFE-005 Windows Restart Evidence — 2026-09-08

Status: **RESTART HALF PASS / LOGOFF-LOGON STILL OPEN**

## Pre-restart checkpoint

Preserved separately before reboot at commit `9c254cd838416a6f6202aa89b1f9c86d2dcbfd87`.

Observed before restart:

- wrapper lifecycle: `HIBERNATION`
- Brain DB present, size `438272` bytes
- daemon process rows: `0`
- iai MCP wrapper count: `0`
- Hermes gateway task last result: `0`
- iai daemon task last result: `0`

## Post-restart evidence

Windows boot time: `2026-09-08 00:49:54` local.

### iai state before recall

- lifecycle: `WAKE`
- Brain DB present, size `442368` bytes
- daemon process rows: `2` (expected Windows venv launcher + base-Python child pattern; previously verified as one logical daemon)
- MCP wrapper count: `1`
- `wake.signal`: absent
- `.daemon.port`: present
- `.daemon.token`: present

### Windows tasks

- `Hermes_Gateway_companion` last run: `2026-09-08 00:50:37`, result `0`
- `iai-mcp-daemon` last run: `2026-09-08 00:51:24`, result `267009` (`0x41301`, Task Scheduler status meaning task currently running, not a failure code)

### Hermes/API

- `http://127.0.0.1:8642/health` returned HTTP `200`

### Store integrity

Read-only SQLite `PRAGMA quick_check` against `~/.iai-mcp/hippo/brain.sqlite3` returned:

`ok`

### Memory survival

Read-only iai recall of known marker `ORION_CAPTURE_FRESH_GATEWAY_20260829`:

- JSON parse: true
- source: `daemon`
- count: `5`
- exact known marker found: true

This proves canonical memory remained readable after a real Windows restart and the daemon-backed retrieval path was healthy.

## Restart verdict

**OR-LIFE-005 restart half: PASS.**

Proven:

- Windows reboot completed normally
- COMPANION Scheduled Task ran unattended
- Hermes loopback API returned unattended
- iai daemon/task returned
- canonical store survived
- SQLite integrity check passed
- known persisted memory survived and was recalled through the live daemon
- no observed store corruption

## Separate startup artifact finding

A legacy Docker-era scheduled task also started after logon:

- task: `Orion Host Idle Bridge`
- process: PowerShell running `C:\HermesAgent\bin\Orion-Host-Idle-Bridge.ps1`
- output path: `C:\HermesAgent\data\orion-runtime\host-idle.json`
- PID path: `C:\HermesAgent\data\orion-runtime\host-idle-bridge.pid`
- interval: `15` seconds

This belongs to the scrapped pre-v2.6 Docker architecture and is not part of the current native-Windows Orion design. Treat cleanup as a separate maintenance item after exact startup provenance is captured; do not conflate it with the successful OR-LIFE-005 restart result.

A second visible blank CMD window was observed after logon but has not yet been positively identified. Preserve it until its process/task provenance is captured.

## Remaining OR-LIFE-005 work

- identify the second blank CMD startup window
- perform independent Windows logoff/logon acceptance
- verify no memory/store/configuration corruption after logoff/logon

Intent preservation: **PRESERVED**.
