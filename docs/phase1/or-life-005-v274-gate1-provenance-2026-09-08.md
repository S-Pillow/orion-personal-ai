# OR-LIFE-005 v2.7.4 Gate 1 Provenance — 2026-09-08

Status: **GATE 1A/1B/1C PASS; NATIVE PRIMITIVES/PREFLIGHT NEXT**

Candidate ZIP: `Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip`
SHA-256: `fd2268aa79883dae2f0fa2b3371de022c3e54be72c85a566be01c893f79d54be`
Extraction directory used by operator: `C:\Users\spill\Downloads\Orion-v274-gate1-20260908-053419`

## Gate 1A — Windows PowerShell 5.1 parse

All package PowerShell entry points parsed successfully under Windows PowerShell 5.1.26100.9278:
- Discover-Orion.ps1
- Install-Orion.ps1
- Invoke-Orion.ps1
- Recover-Orion-After-Restart.ps1
- Start-Orion.ps1
- Stop-Orion.ps1
- Test-Orion-Preflight.ps1
- Test-PowerShell-Parse.ps1

## Gate 1B — read-only discovery

- Hermes command: `C:\Users\spill\AppData\Local\hermes\bin\hermes.exe`
- Ollama command: `C:\Users\spill\AppData\Local\Programs\Ollama\ollama.exe`
- COMPANION directory exists.
- `Hermes_Gateway_companion`: Ready, LogonTrigger disabled.
- `iai-mcp-daemon`: Ready, LogonTrigger disabled.
- Initial guessed Hermes venv locations were absent; no mutation was performed.

## Gate 1C — installed Hermes provenance

Scheduled Task action:
- executable: `wscript.exe`
- script: `C:\Users\spill\AppData\Local\hermes\profiles\companion\gateway-service\Hermes_Gateway_companion.vbs`

Generated gateway command establishes the actual installed runtime contract:
- `HERMES_HOME=C:\Users\spill\AppData\Local\hermes\profiles\companion`
- `VIRTUAL_ENV=C:\Users\spill\AppData\Local\hermes\hermes-agent\venv`
- `PYTHONPATH=C:\Users\spill\AppData\Local\hermes\hermes-agent`
- Python: `C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`
- invocation: `python.exe -m hermes_cli.main --profile companion gateway run`

Pinned source candidate:
- `C:\Users\spill\AppData\Local\hermes\hermes-agent\hermes_cli\gateway_windows.py`
- source root therefore `C:\Users\spill\AppData\Local\hermes\hermes-agent`

Other Python found under Hermes root:
- iai venv: `C:\Users\spill\AppData\Local\hermes\profiles\companion\iai\venv\Scripts\python.exe`

The Hermes venv reports CPython 3.11.3.

## Exact candidate configuration values now supported by evidence

- `python`: `C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`
- `source`: `C:\Users\spill\AppData\Local\hermes\hermes-agent`
- `hermesHome`: `C:\Users\spill\AppData\Local\hermes`
- `ollama`: `C:\Users\spill\AppData\Local\Programs\Ollama\ollama.exe`
- `commit`: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

No Orion/Hermes/Ollama/iai lifecycle action, task change, service change, login-persistence change, or install occurred during these gates.

Core Intent Preservation: **PRESERVED**.
