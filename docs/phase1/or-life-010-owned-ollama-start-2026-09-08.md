# OR-LIFE-010 owned Ollama start evidence — 2026-09-08

Status: START OWNERSHIP HALF PASS / STOP HALF PENDING

## Preconditions
- Hermes manual-off configured.
- iai daemon task retained/enabled with LogonTrigger disabled.
- Ollama Startup shortcut removed from the user's Startup folder.
- Pre-existing Ollama processes stopped.
- Ollama API confirmed unavailable before Start Orion.

## Start Orion result
The installed Start Orion launcher was executed from `%LOCALAPPDATA%\Orion\operator\Start-Orion.ps1` with Ollama fully off.

Observed:
- `Ollama: starting`
- `Ollama: ready`
- Hermes COMPANION started through supported direct spawn.
- Hermes COMPANION became ready.
- `ORION READY`
- Hermes API healthy.
- launcher exit code 0.

## Ownership state verification
`%LOCALAPPDATA%\Orion\operator\launcher-session.json` existed after startup.

Recorded values:
- `ollamaStartedByOrion = true`
- tracked Ollama PID: `1404`
- tracked Ollama PID alive: `true`

## Disposition
The Start Orion ownership contract is satisfied for this run: Orion started Ollama because it was absent and correctly recorded ownership of that specific process. Do not mark the full ownership cycle accepted until Stop Orion proves it stops Hermes and the Orion-owned Ollama instance, clears session state, and leaves no unrelated process kill.

Intent Preservation Check: PRESERVED. The launcher is one-shot and no resident supervisor was introduced.
