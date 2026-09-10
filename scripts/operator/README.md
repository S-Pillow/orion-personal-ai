# Orion operator controls

These scripts implement the accepted manual-off operator lifecycle under Orion Master PRD v2.8. Their lifecycle behavior remains the Phase 1 accepted baseline; Phase 2 builds on that baseline rather than replacing it.

## Files

- `Start-Orion.ps1` — one-shot launcher. Ensures Ollama is available, starts Hermes profile `companion` through the supported Hermes gateway command, waits for `http://127.0.0.1:8642/health`, records whether this launcher started Ollama, and exits.
- `Stop-Orion.ps1` — one-shot shutdown. Stops Hermes profile `companion` through the supported Hermes gateway command, confirms the API is down, stops Ollama only when the current Orion launcher session owns the recorded Ollama process, and exits. iai is not killed; it remains under its vendor idle/HIBERNATION lifecycle.
- `Install-Orion-Desktop-Shortcuts.ps1` — installs the accepted one-shot scripts and creates `Start Orion` / `Stop Orion` desktop shortcuts.

## Current Phase 2 relationship

- Phase 1 lifecycle acceptance remains controlling for Start/Stop ownership and manual-off behavior.
- The Phase 2A HUD bridge is a separate foreground presentation/control client during validation. It does not start, stop, supervise, install, update, or kill Hermes, Ollama, iai, Windows services, or Scheduled Tasks.
- Start Orion does not yet launch the HUD bridge. Integrating HUD launch into Start Orion is a later bounded lifecycle change and must preserve the accepted one-shot ownership model.
- The in-HUD Stop Orion control is not implemented in Phase 2A; when added later it must route through the accepted operator stop behavior rather than creating a second shutdown path.

## Invariants

- No resident Orion supervisor is created.
- The scripts do not directly start or stop `iai-mcp-daemon`; demand-wake remains iai/Hermes-owned.
- The scripts do not change Scheduled Task definitions or login persistence.
- Ollama ownership is session-scoped: if Ollama was already available before Start Orion, Stop Orion leaves it alone. If Start Orion launched `ollama serve`, Stop Orion may terminate only the recorded Ollama process.
- Phase 2 work must not weaken or bypass these accepted lifecycle boundaries.
