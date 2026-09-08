# OR-LIFE-010 Ollama manual-off configuration

Date: 2026-09-08
Status: ACCEPTED PRE-START STATE

## Purpose
Align the local model provider with Orion v2.7 manual-off operator intent so the complete local AI runtime can be stopped when Orion is not needed.

## Pre-change evidence
- Windows Startup shortcut existed at `C:\Users\spill\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\Ollama.lnk`.
- Shortcut target: `C:\Users\spill\AppData\Local\Programs\Ollama\ollama app.exe`.
- Running process chain before change:
  - `ollama app.exe`
  - child `ollama.exe serve`
- `ollama.exe` CLI discoverable at `C:\Users\spill\AppData\Local\Programs\Ollama\ollama.exe`.

## Change applied
- Backed up the Startup shortcut to `C:\Users\spill\Documents\Orion-Startup-Backups\20260908-023324\Ollama.lnk`.
- Removed `Ollama.lnk` from the Windows Startup folder.
- Stopped the inherited login-started `ollama app.exe` and `ollama.exe serve` processes.

## Verification
- Startup shortcut present: False.
- Backup shortcut present: True.
- Ollama API `127.0.0.1:11434/api/tags` available: False.
- Remaining Ollama process count: 0.

## Disposition
Manual-off local-model precondition passes. Do not manually start Ollama before the next OR-LIFE-010 launcher acceptance. Next test: Start Orion must start Ollama itself and record ownership; Stop Orion must then stop that Orion-owned Ollama process in addition to Hermes.

Intent Preservation Check: PRESERVED. No resident supervisor or parallel lifecycle system was introduced.