# OR-LIFE-005 v2.7.4 Transition 4D — Installed Start/Stop Acceptance

Date: 2026-09-09
Status: PASS

## Scope

Controlled post-install end-to-end acceptance of the installed Orion v2.7.4 candidate lifecycle using the published scripts under:

`%LOCALAPPDATA%\Orion\operator\versions\2.7.4-candidate1`

This test verified installed Start behavior, runtime health, launcher-session establishment, installed Stop behavior, owned Ollama cleanup, lifecycle-metadata cleanup, and preservation of manual-off task policy.

## Preconditions

Observed before Start:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent
- `Hermes_Gateway_companion` LogonTrigger enabled: false
- `iai-mcp-daemon` LogonTrigger enabled: false

## Installed Start acceptance

The installed `Start-Orion.ps1` was invoked from the versioned publication with the installed `orion-config.json`.

Observed result:

- output: `ORION READY`
- Start exit code: 0
- Hermes health: true
- Ollama health: true
- Ollama process count: 1
- `launcher-session.json`: present
- `active-operation.json`: absent
- both Hermes and iai LogonTriggers remained disabled

Result: START ACCEPTANCE PASS.

## Installed Stop acceptance

The installed `Stop-Orion.ps1` was invoked from the same versioned publication.

Observed result:

- output: `Owned Ollama: stopped`
- output: `ORION STOPPED; iai remains vendor-managed.`
- Stop exit code: 0

Final clean-off verification:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent
- both Hermes and iai LogonTriggers remained disabled

## Acceptance interpretation

Transition 4D passed. The installed v2.7.4 lifecycle successfully controlled the live Orion workflow end to end:

- installed Start brought Hermes and Ollama online;
- launcher session ownership was established;
- no unresolved active-operation record remained;
- installed Stop stopped Hermes and the Orion-owned Ollama instance;
- clean-off state was restored;
- manual-off login policy remained unchanged.

No manual lifecycle cleanup was required.
