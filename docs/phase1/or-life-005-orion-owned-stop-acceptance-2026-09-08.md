# OR-LIFE-005 Orion-owned full stop acceptance — 2026-09-08

Status: PASS

## Context
This test followed the fully-off Ollama start path in which Start Orion launched Ollama itself and recorded launcher ownership (`ollamaStartedByOrion=true`, tracked PID 1404).

## Stop verification
After invoking the desktop Stop Orion control:

- Hermes API listening: False
- Hermes gateway status: no gateway process detected
- iai MCP wrapper count: 0
- launcher session state exists: False
- Ollama API available: False
- remaining Ollama process count: 0

The retained `Hermes_Gateway_companion` Scheduled Task remained registered and Ready; this is expected because manual-off mode disables its LogonTrigger rather than uninstalling the task.

## Disposition
The Orion-owned Start/Stop resource cycle is accepted: Orion can start the local model provider for its own session and release both Hermes and that owned Ollama instance on Stop Orion without leaving the local AI runtime running.

This does not require the iai daemon itself to disappear immediately; iai remains under its vendor idle/HIBERNATION lifecycle.

Intent Preservation Check: PRESERVED. No Orion supervisor or alternate lifecycle service was introduced.
