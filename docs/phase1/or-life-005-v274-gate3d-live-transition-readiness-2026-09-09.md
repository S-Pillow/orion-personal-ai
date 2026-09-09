# OR-LIFE-005 v2.7.4 Gate 3D — Live Transition Readiness / Expected Installer Refusal

Date: 2026-09-09
Status: PASS
Branch: feature/orion-start-v272-lifecycle-safety
Candidate workspace: `C:\Users\spill\Downloads\Orion-v274-gate1-20260908-053419`
Candidate package version: `2.7.4-candidate1`

## Purpose

Validate that the real candidate installer refuses the current untransitioned live Orion state before publication, while preserving all existing legacy entry points, desktop shortcuts, manual-off task state, and runtime clean-off state.

This gate intentionally did not archive, replace, or remove the live legacy controls.

## Preconditions observed

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent
- Canonical live `Start-Orion.ps1`: present
- Canonical live `Stop-Orion.ps1`: present
- Desktop `Start Orion.lnk`: present
- Desktop `Stop Orion.lnk`: present
- `%LOCALAPPDATA%\Orion\operator\versions`: absent before invocation
- `Hermes_Gateway_companion` Scheduled Task: Ready; one LogonTrigger; LogonTrigger disabled
- `iai-mcp-daemon` Scheduled Task: Ready; one LogonTrigger; LogonTrigger disabled

## Before snapshot

- Start script SHA-256: `758E14E90D94E2715DD3EA1B43777322A713E0F05007364116E0B91E689BA1C8`
- Stop script SHA-256: `F724C315A2884EFFEE6C24B745C20751DFE2B8ED98DF291B24697056C18F4204`
- Version entry count: 0
- Desktop shortcuts still targeted the canonical live operator scripts under `%LOCALAPPDATA%\Orion\operator`.

## Real installer invocation

Executed the candidate `Install-Orion.ps1` with the real config and `-LegacyTransitionConfirmed` against the current live state.

Observed output:

```text
INSTALL FAILED: LEGACY_OR_ACTIVE_STATE_PRESENT
Published versions, if any, were retained. Review INSTALL.md before retrying.
```

Installer exit code: `1`

Expected safety refusal observed: true.

## No-mutation verification

After refusal:

- Start script hash unchanged: true
- Stop script hash unchanged: true
- Start shortcut unchanged: true
- Stop shortcut unchanged: true
- Version publication state unchanged: true
- No new version directory was published
- `Hermes_Gateway_companion` LogonTrigger remained disabled
- `iai-mcp-daemon` LogonTrigger remained disabled

## Final clean-off state

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

## Acceptance

PASS.

The live transition state correctly refused installation at the intended safety boundary. Legacy entry points remained intact, no version was published, desktop shortcuts were unchanged, manual-off task triggers remained disabled, and the final runtime state remained clean-off.

Gate 3D validates the refusal boundary only. It does not perform the one-time legacy transition, Windows restart, real installation, or post-install Start/Stop acceptance.
