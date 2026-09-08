# Ollama startup provenance — 2026-09-08

Status: OBSERVED / PRE-MUTATION

## Startup shortcut

User Startup folder contains:
`C:\Users\spill\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\Ollama.lnk`

Shortcut target:
`C:\Users\spill\AppData\Local\Programs\Ollama\ollama app.exe`

Arguments: none.

## Observed process chain

- PID 18672: `ollama app.exe`
  - Parent PID 3980
  - Executable: `C:\Users\spill\AppData\Local\Programs\Ollama\ollama app.exe`
- PID 21408: `ollama.exe`
  - Parent PID 18672
  - Executable: `C:\Users\spill\AppData\Local\Programs\Ollama\ollama.exe`
  - Command line: `ollama.exe serve`

## Interpretation

Ollama currently starts independently at Windows login through its normal Startup-folder shortcut. That means Orion's accepted Start/Stop launcher pair correctly treats this running Ollama instance as externally owned and leaves it running on Stop Orion.

For the v2.7 manual-off / gaming-resource goal, the proposed next change is to back up and remove the Ollama Startup shortcut from the active Startup folder, verify `ollama.exe` is available to the Start Orion launcher, stop the currently inherited Ollama process tree once, then prove a new Start Orion session owns the Ollama server and Stop Orion releases it.

Intent Preservation Check: PRESERVED. This does not add a supervisor or alter Hermes/iai lifecycle ownership; it changes only optional login persistence for the local model provider.