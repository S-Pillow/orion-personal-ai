# Orion operator controls

These scripts implement the Orion Master PRD v2.7 manual-off operator lifecycle.

## Files

- `Start-Orion.ps1` — one-shot launcher. Ensures Ollama is available, starts Hermes profile `companion` through the supported Hermes gateway command, waits for `http://127.0.0.1:8642/health`, records whether this launcher started Ollama, and exits.
- `Stop-Orion.ps1` — one-shot shutdown. Stops Hermes profile `companion` through the supported Hermes gateway command, confirms the API is down, stops Ollama only when the current Orion launcher session owns the recorded Ollama process, and exits. iai is not killed; it remains under its vendor idle/HIBERNATION lifecycle.
- `Install-Orion-Desktop-Shortcuts.ps1` — copies the two scripts to `%LOCALAPPDATA%\Orion\operator` and creates `Start Orion` / `Stop Orion` desktop shortcuts.

## Invariants

- No resident Orion supervisor is created.
- The scripts do not directly start or stop `iai-mcp-daemon`; demand-wake remains iai/Hermes-owned.
- The scripts do not change Scheduled Task definitions or login persistence.
- The HUD is not started yet. Phase 2 will extend Start Orion to open the HUD only after backend health and will add the in-HUD Stop Orion control.
- Ollama ownership is session-scoped: if Ollama was already available before Start Orion, Stop Orion leaves it alone. If Start Orion launched `ollama serve`, Stop Orion may terminate only the recorded Ollama process.
