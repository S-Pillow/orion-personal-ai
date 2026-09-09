# OR-LIFE-005 v2.7.4 Transition 4C — Real Installation

Date: 2026-09-09
Status: PASS

## Scope

Real installation/publication of the accepted Orion v2.7.4 candidate after the one-time legacy transition restart. This step intentionally did not start Orion, Hermes, or Ollama.

## Preconditions

- Hermes health false.
- Ollama health false.
- Ollama process count 0.
- `launcher-session.json` absent.
- `active-operation.json` absent.
- Canonical legacy `Start-Orion.ps1` / `Stop-Orion.ps1` absent.
- Desktop `Start Orion.lnk` / `Stop Orion.lnk` absent.
- Target version `2.7.4-candidate1` absent.
- `Hermes_Gateway_companion` LogonTrigger disabled.
- `iai-mcp-daemon` LogonTrigger disabled.

## Real installer result

The accepted candidate installer was invoked with:

`Install-Orion.ps1 -ConfigPath <accepted orion-config.json> -LegacyTransitionConfirmed`

Observed:

- `Installed: C:\Users\spill\AppData\Local\Orion\operator\versions\2.7.4-candidate1`
- `Created Start Orion and Stop Orion shortcuts. No runtime was started.`
- Installer exit: 0

## Publication verification

Published directory existed and contained all expected runtime files:

- `orion.py`
- `protocol.py`
- `win_process.py`
- `hermes_worker.py`
- `Invoke-Orion.ps1`
- `Start-Orion.ps1`
- `Stop-Orion.ps1`
- `Recover-Orion-After-Restart.ps1`
- `Test-Orion-Preflight.ps1`
- `orion-config.json`

Every published file hash matched the accepted candidate source/config.

## Shortcut verification

Desktop `Start Orion.lnk` and `Stop Orion.lnk` both existed after installation.

Both shortcuts target Windows PowerShell and reference the versioned publication under:

`C:\Users\spill\AppData\Local\Orion\operator\versions\2.7.4-candidate1`

Working directories also point to that exact versioned publication.

## Installer cleanup

- Remaining staging directories: 0
- Remaining temporary link directories: 0

## Post-install manual-off verification

- Hermes health false.
- Ollama health false.
- Ollama process count 0.
- `launcher-session.json` absent.
- `active-operation.json` absent.
- Hermes LogonTrigger remained disabled.
- iai LogonTrigger remained disabled.

## Acceptance

PASS.

The accepted v2.7.4 candidate is now installed and published as the live Orion launcher package. Installation itself started no runtime and preserved manual-off policy. The next acceptance step is one controlled post-install Start -> health verification -> Stop cycle using the newly installed version.
