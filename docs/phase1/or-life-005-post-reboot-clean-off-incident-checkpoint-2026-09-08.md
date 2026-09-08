# OR-LIFE-005 Post-Reboot Clean-Off Incident Checkpoint — 2026-09-08

Status: **CLEAN-OFF RESTORED / POST-REBOOT START INCIDENT BLOCKING FURTHER ACCEPTANCE**

## Current runtime state

After the anomalous post-reboot Start Orion attempt, the operator invoked the supported command:

`hermes -p companion gateway stop`

Observed result:

- Hermes stop exit code: `0`
- Hermes API on `127.0.0.1:8642`: **False**
- Ollama API on `127.0.0.1:11434`: **False**
- `%LOCALAPPDATA%\Orion\operator\launcher-session.json`: **absent**
- `%LOCALAPPDATA%\Orion\operator\launcher-session.json.tmp`: **absent**
- Operator directory contains only `Start-Orion.ps1` and `Stop-Orion.ps1`

The machine is therefore back in the intended manual-off runtime state before further investigation or changes.

## Incident narrowing

The failed post-reboot start had previously left:

- Hermes API healthy
- Ollama API unavailable
- no launcher session state file

The current `Start-Orion.ps1` writes launcher session state only after Ollama readiness, Hermes start, and Hermes health readiness. Its catch block stops Orion-owned Ollama, but does not stop a Hermes gateway started by the current invocation.

Therefore the failure occurred before the final session-state write and after, or during, the Hermes start/readiness stage. A cold-start timeout is a leading hypothesis because the script currently allows only 30 seconds for Hermes health and the operator observed severe transient system responsiveness degradation immediately after the reboot/start attempt. This timeout hypothesis is **not yet proven**.

## Resource snapshot after recovery

- Total visible RAM: 15.88 GB
- Free RAM: 8.41 GB
- no System log Event ID 2004 resource-exhaustion events in the previous hour
- no matching Ollama / out-of-memory / resource-exhaustion Application log events in the previous hour

This does not support a persistent hard-OOM condition. A transient startup paging / CPU / GPU-memory pressure event remains possible and should be measured if another controlled cold start is performed.

## Disposition

Do not continue OR-LIFE-005 acceptance, Discord testing, or logoff/logon testing until the launcher failure path is made transactional. A Start Orion failure must roll back every runtime component started by that invocation, while preserving independently pre-existing components.

Core Intent Preservation: **PRESERVED**.
