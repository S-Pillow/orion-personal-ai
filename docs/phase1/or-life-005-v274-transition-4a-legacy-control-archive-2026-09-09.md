# OR-LIFE-005 v2.7.4 Transition 4A — Legacy Control Archive

Date: 2026-09-09
Status: PASS
Branch: `feature/orion-start-v272-lifecycle-safety`

## Purpose

Complete the first consequential step of the one-time Orion launcher transition by backing up and removing the four legacy active invocation paths, while preserving manual-off guarantees and a verified rollback package. This step intentionally does not install v2.7.4 and does not restart Windows.

## Preconditions

Observed clean-off state before transition:

- Hermes health endpoint: false
- Ollama health endpoint: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

Legacy active invocation paths were all present before archival:

- `%LOCALAPPDATA%\Orion\operator\Start-Orion.ps1`
- `%LOCALAPPDATA%\Orion\operator\Stop-Orion.ps1`
- Desktop `Start Orion.lnk`
- Desktop `Stop Orion.lnk`

No old launcher process was running.

## Manual-off checks

Before mutation:

- `Hermes_Gateway_companion` task: Ready; one LogonTrigger; LogonTrigger disabled.
- `iai-mcp-daemon` task: Ready; one LogonTrigger; LogonTrigger disabled.
- `Orion Host Idle Bridge`: absent.
- Orion/Hermes/iai Startup-folder fallback hits: 0.

Candidate `orion.LEGACY` blockers were also checked and all absent:

- `last-start-failure.json`
- `last-stop-failure.json`
- `lifecycle-quarantine.json`
- `lifecycle-quarantine.marker`
- `start-recovery-required.marker`

Legacy-blocker probe exit: 0.

## Rollback package

A timestamped rollback package was created at:

`C:\Users\spill\Documents\Orion-Legacy-Rollback-20260909-003822`

The package contains the four legacy active entry points plus `manifest.json`. SHA-256 equality was verified between each source and backup before any active entry point was removed:

- `Start-Orion.ps1`: match
- `Stop-Orion.ps1`: match
- `Start Orion.lnk`: match
- `Stop Orion.lnk`: match

## Transition action

Removed only the four verified legacy active invocation paths:

- `%LOCALAPPDATA%\Orion\operator\Start-Orion.ps1`
- `%LOCALAPPDATA%\Orion\operator\Stop-Orion.ps1`
- Desktop `Start Orion.lnk`
- Desktop `Stop Orion.lnk`

Post-removal verification confirmed all four active paths absent.

## Final pre-restart state

After removal:

- Hermes health endpoint: false
- Ollama health endpoint: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

Result: PASS.

## Acceptance interpretation

Transition 4A successfully established a rollback-preserved state in which the old launcher cannot be invoked from its canonical script paths or desktop shortcuts. Manual-off protections remained intact, no runtime was started, no lifecycle metadata was created, and no v2.7.4 installation occurred.

The next required action is a real Windows Restart. After login, the system must be checked for manual-off state before installing v2.7.4.
