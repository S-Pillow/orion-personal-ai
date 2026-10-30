# Orion repository instructions for coding agents

Before changing this repository, read the root `AGENTS.md`.

For any PowerShell harness, migration script, deployment script, lifecycle script, or operator-run PowerShell block, also read and follow:

`docs/agent/powershell-harness-standard.md`

PowerShell harness correctness is part of qualification. Do not hand an operator a harness that has not been reviewed for `$null`/scalar/array native-command output, `Set-StrictMode`, immediate `$LASTEXITCODE` handling, exact targeting, fail-before-mutation ordering, rollback evidence, and secret-safe output.

For Hermes upgrade/migration work, the hard production gates are Orion, Memory, Voice, Chat, and Security. Cron, LSP, Hermes Desktop, optional plugins, and unrelated platform defects are only blockers when their failure mode crosses into one of those hard gates.

Do not assume prior chat memory is available. Reconstruct current state from repository docs, open PRs/issues, exact commits, and read-only runtime evidence before mutation.
