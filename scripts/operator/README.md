# Orion operator controls

These scripts implement the accepted manual-off operator lifecycle under Orion Master PRD v2.9. They are one-shot Windows operator controls, not a resident supervisor, and they preserve vendor ownership of Hermes and iai lifecycle behavior.

## Files

- `Start-Orion.ps1` — one-shot launcher. Ensures Ollama is available, starts Hermes profile `companion` through the supported Hermes gateway command, waits for direct loopback API health, records whether this launcher started Ollama, and exits.
- `Stop-Orion.ps1` — one-shot shutdown. Stops Hermes profile `companion` through the supported Hermes gateway command, confirms the API is down using the same direct loopback probe, stops Ollama only when the current Orion launcher session owns the recorded Ollama process, and exits. iai is not killed; it remains under its vendor idle/HIBERNATION lifecycle.
- `Install-Orion-Desktop-Shortcuts.ps1` — installs the one-shot scripts and creates `Start Orion` / `Stop Orion` desktop shortcuts using `-ExecutionPolicy Bypass` for the launcher process only.

## Current lifecycle behavior

- Orion remains manual-off by default. These controls do not install login persistence or create an Orion lifecycle supervisor.
- Local loopback health checks bypass configured HTTP proxies explicitly. This prevents host proxy settings from turning a healthy `127.0.0.1` Ollama or Hermes endpoint into a false failure.
- `Start-Orion.ps1` polls observable health instead of relying on a fixed sleep. The default Ollama health window is 60 seconds and remains configurable through `-OllamaHealthTimeoutSeconds`.
- When Orion starts `ollama serve`, stdout/stderr are captured under `%LOCALAPPDATA%\Orion\operator\logs`. Startup failures distinguish process exit, port binding without a healthy API, and failure to bind.
- Ollama ownership remains tied to the process that this launcher started. Listener inspection is diagnostic only and does not transfer ownership to another Ollama process.
- `Stop-Orion.ps1` verifies the supported Hermes stop path by observing the loopback health endpoint go down. It may stop only the recorded Orion-owned Ollama PID and verifies that specific process exits; unrelated Ollama processes are left alone.
- The scripts do not directly start or stop `iai-mcp-daemon`; iai demand-wake, idle, and HIBERNATION behavior remain iai/Hermes-owned.

## Known separate gap

Orion Master PRD v2.9 states that Start Orion should open the accepted HUD after Hermes/API health is confirmed. The current operator launcher does not yet perform that HUD-open step. This lifecycle-hardening change does not silently add a HUD launch mechanism; that remains a separate bounded integration item requiring the accepted HUD entry point and verification path.

## Invariants

- No resident Orion supervisor is created.
- No Scheduled Task definitions or login persistence are changed.
- No Hermes, Ollama, or iai configuration is rewritten by these controls.
- Ollama ownership is session-scoped: if Ollama was already healthy before Start Orion, Stop Orion leaves it alone. If Start Orion launched `ollama serve`, Stop Orion may terminate only the recorded, still-matching Ollama process.
- Success output follows observable component health/shutdown evidence; a command exit alone is not treated as component health.
- Changes to lifecycle-affecting dependencies or integration invalidate the relevant operator-lifecycle regression evidence and require focused re-verification.
