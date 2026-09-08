# OR-LIFE-010 full Start Orion direct-launch verification — 2026-09-08

Status: PASS for direct invocation of installed Start-Orion.ps1 after Ollama manual-off configuration.

## Preconditions
- Ollama Startup shortcut removed from Windows Startup and backed up separately.
- Ollama API was down and no Ollama processes remained before test.
- Hermes COMPANION was stopped.
- Installed operator script: `%LOCALAPPDATA%\Orion\operator\Start-Orion.ps1`.

## Invocation
The installed launcher was invoked directly through Windows PowerShell with `-NoProfile -ExecutionPolicy Bypass -File`.

Observed output:
- `=== START ORION ===`
- `Ollama: starting`
- `Ollama: ready`
- `Hermes COMPANION: starting`
- Hermes reported direct-spawn gateway start
- `Hermes COMPANION: ready`
- `ORION READY`
- `Hermes API: healthy`
- `iai: demand-wake managed by Hermes/iai`
- launcher exit code `0`

## Interpretation
The source-controlled Start Orion launcher can start Ollama from an off state, then start Hermes COMPANION through the supported Hermes lifecycle, wait for Hermes API health, and exit successfully. This is consistent with OR-LIFE-010 and does not introduce a resident supervisor.

The earlier desktop-shortcut attempt that was followed by both APIs being down is not treated as a launcher-code failure because direct invocation of the exact installed script passed immediately afterward. Desktop shortcut behavior still needs explicit re-verification if shortcut-path acceptance is required.

Next verification: inspect launcher session ownership state, then invoke the desktop Stop Orion control and verify both Hermes and the Orion-owned Ollama process are stopped and session state is removed.

Intent Preservation Check: PRESERVED.
