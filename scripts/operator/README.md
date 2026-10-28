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
- On the current Orion Windows workstation, Orion-started Ollama is launched with the process-local `OLLAMA_LLM_LIBRARY=rocm_v7_1` selection. This bypasses unsuitable backend autodetection for the AMD Radeon RX 9070 XT while leaving the parent PowerShell environment unchanged immediately after `Start-Process` returns.
- The ROCm selection applies only when Orion itself launches `ollama serve`. If Ollama is already healthy before Start Orion, the launcher does not replace, restart, or reconfigure that pre-existing provider.
- The launcher records the known Ollama library in `launcher-session.json` when it launched or inherited a prior Orion-owned session that already recorded the library. This is diagnostic provenance only; it does not transfer ownership.
- When Orion starts `ollama serve`, stdout/stderr are captured under `%LOCALAPPDATA%\Orion\operator\logs`. Startup failures distinguish process exit, port binding without a healthy API, and failure to bind, and include the selected backend when known.
- Ollama ownership remains tied to the process that this launcher started. Listener inspection is diagnostic only and does not transfer ownership to another Ollama process.
- `Stop-Orion.ps1` verifies the supported Hermes stop path by observing the loopback health endpoint go down. It may stop only the recorded Orion-owned Ollama PID and verifies that specific process exits; unrelated Ollama processes are left alone.
- Before stopping an Orion-owned Ollama process, `Stop-Orion.ps1` snapshots its descendant process tree from `Win32_Process`. After the parent exits, descendants are given time to terminate naturally. Only descendants from that pre-stop snapshot whose PID, name, executable path, and creation identity still match may be force-stopped. This prevents an Ollama-owned `llama-server.exe` runner from being orphaned without introducing a broad process-name kill.
- The scripts do not directly start or stop `iai-mcp-daemon`; iai demand-wake, idle, and HIBERNATION behavior remain iai/Hermes-owned.

## ROCm 7.1 correction evidence

The operator correction was selected from real workstation evidence rather than generic hardware assumptions:

- unrestricted Ollama 0.32.15 discovery bound `127.0.0.1:11434` but repeatedly timed out while probing unsuitable backends;
- Vulkan-only server liveness succeeded, but `qwen3.5-hermes:9b` crashed during Vulkan model loading;
- process-local `rocm_v7_1` server startup succeeded and the actual `qwen3.5-hermes:9b` model completed an `/api/generate` request on the AMD Radeon RX 9070 XT;
- the temporary diagnostic processes were cleaned up and no persistent Ollama environment or global configuration was changed.

The operator script therefore uses the same process-local ROCm selection only for Orion-owned Ollama startup. It does not rewrite user-level or machine-level Ollama environment variables or configuration.

## Owned Ollama tree cleanup evidence

The first full ROCm operator acceptance run proved Start, direct health, session ownership, environment restoration, ROCm runtime selection, and actual model inference, but it also exposed a shutdown gap: after the recorded Orion-owned `ollama.exe` PID exited, its `llama-server.exe` model runner could remain alive. The API was already down, so parent-only shutdown evidence was insufficient.

Stop Orion now treats the pre-stop descendant snapshot as part of the same Orion-owned lifecycle boundary. Descendants receive a grace period after the parent exits; any survivor is force-stopped only when its process identity still matches the captured snapshot. Unrelated `llama-server.exe` or other processes are not selected by name and remain untouched.

## Known separate gap

Orion Master PRD v2.9 states that Start Orion should open the accepted HUD after Hermes/API health is confirmed. The current operator launcher does not yet perform that HUD-open step. This lifecycle-hardening change does not silently add a HUD launch mechanism; that remains a separate bounded integration item requiring the accepted HUD entry point and verification path.

## Invariants

- No resident Orion supervisor is created.
- No Scheduled Task definitions or login persistence are changed.
- No Hermes or iai configuration is rewritten by these controls.
- The process-local ROCm library selection does not rewrite persistent Ollama configuration or user/machine environment state.
- Ollama ownership is session-scoped: if Ollama was already healthy before Start Orion, Stop Orion leaves it alone. If Start Orion launched `ollama serve`, Stop Orion may terminate only the recorded, still-matching Ollama process and identity-checked descendants captured from that owned process tree before shutdown.
- Stop Orion never performs a broad process-name kill for `ollama.exe` or `llama-server.exe`.
- Success output follows observable component health/shutdown evidence; a command exit alone is not treated as component health.
- Changes to lifecycle-affecting dependencies or integration invalidate the relevant operator-lifecycle regression evidence and require focused re-verification.
