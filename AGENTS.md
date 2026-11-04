# Orion Agent Instructions

This file is the repository-level operating guide for AI coding agents and future chat sessions working on Orion.

## Read this first

Before proposing or executing repository, runtime, deployment, migration, or operator-lifecycle changes:

1. Read this file.
2. Read the task-specific docs and current open PR/issue evidence for the work being resumed.
3. For any PowerShell harness, read `docs/agent/powershell-harness-standard.md` before writing or handing commands to an operator.
4. Treat accepted runtime state, source identity, rollback evidence, and authorization boundaries as explicit gates; do not infer them from capability alone.

## Current system hard gates

For Orion/Hermes upgrade and migration work, these five areas are hard production gates:

1. Orion lifecycle/runtime integrity.
2. Memory integrity and persistence.
3. Voice/STT/TTS/PTT behavior.
4. Chat/session reliability.
5. Security and authorization boundaries.

Cron, LSP, Hermes Desktop, optional plugins, and unrelated platform defects are not independent blockers unless their failure mode crosses into one of the five hard gates above.

## PowerShell harness rule

PowerShell harness correctness is part of qualification, not an operator-side discovery step.

A harness must fail safely before mutation and must be reviewed for PowerShell scalar/null/array behavior under `Set-StrictMode` before it is given to the operator. In particular:

- normalize native-command output with `@(...)` before `.Count`, indexing, or assumptions about collection shape;
- never call `.Trim()` on possibly empty native-command output without a null/empty guard;
- check `$LASTEXITCODE` immediately after native commands whose success matters;
- do not rely on PowerShell's automatic scalar-versus-array unwrapping;
- explicitly consider zero-result, one-result, and multi-result command output;
- place all mutation after source/state/preflight validation whenever practical;
- prefer exact process IDs, exact source identities, bounded waits, and fail-closed behavior over broad process or filesystem actions;
- never print secrets merely to prove a configuration exists;
- preserve rollback evidence before any destructive or environment-owning change.

The detailed mandatory standard is in `docs/agent/powershell-harness-standard.md`.

## Continuity expectation

Do not assume prior chat memory is available. When resuming work, reconstruct the current state from repository docs, open PRs/issues, exact commits, and read-only runtime evidence before mutating anything.
