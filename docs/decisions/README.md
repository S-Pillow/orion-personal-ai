# Architecture Decisions

Use this directory for durable Orion architecture and implementation decisions.

## Controlling baseline

As of 2026-08-29, the controlling architecture is **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)** and the native-Windows execution sequence.

Decision records must clearly distinguish:

- current controlling decisions
- superseded/historical decisions
- installed-runtime evidence
- upstream/version-context evidence
- unresolved hypotheses

A decision marked **SUPERSEDED / HISTORICAL** remains useful evidence but must not be applied to the current runtime without explicit reauthorization.

Current examples:

- `ADR-0001-s6-cap-kill-lifecycle.md` — **historical** Docker/s6 decision
- `phase4-upstream-fork-strategy.md` — **historical** earlier Jarvis/Phase-4 execution strategy; the iai compatibility-fork concept remains useful
- `source-reproducibility-and-rebuild.md` — **current**, updated for native Windows

Do not promote an unverified hypothesis into canonical architecture simply because it appears in upstream documentation or a diagnostic transcript.
