# Orion Reproducibility Inventory

**Status: ACTIVE — updated 2026-08-29**

This inventory tracks whether the **current native-Windows Orion architecture** can be reconstructed from GitHub plus intentionally external private material.

## Controlling baseline

Controlling requirements: **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**.

Current implementation order:

1. native Windows Hermes Phase 0
2. native iai Phase 1
3. HUD only after Phase 1 acceptance
4. vault-actions and later capabilities afterward

Historical Docker/s6/Jarvis material remains preserved but does not count as current v2.6 acceptance.

## Source repositories

- `S-Pillow/orion-personal-ai` — current Orion integration/control source, scripts, docs, and evidence
- `S-Pillow/iai-personal-memory-engine` — iai compatibility/upstream-tracking fork; candidate home for a narrowly scoped Windows compatibility patch if approved
- `S-Pillow/jarvis_ai` — historical/possible-future HUD fork; inactive until native Phase 1 passes

## Current preserved source

### Native Phase 0 — source-preservation PASS

Accepted source:

- `scripts/phase0/Orion-Phase0-Hermes-Native-AcceptedBaseline.ps1`

SHA-256:

`e64cdfc471754547671259e8ae09d0167dc9e8dbcf359b1effb6a1da09086e85`

This artifact preserves:

- accepted Hermes tag/package/commit
- named `companion` profile
- local model/provider configuration
- API enablement and secret-presence checks without exposing secret values
- Windows Scheduled Task persistence
- authenticated API verification
- Ollama model/context verification
- bounded rollback behavior
- explicit prohibition on `hermes update`

Accepted Phase 0 runtime snapshot:

- Hermes tag `v2026.8.27`
- package `0.20.6`
- commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- profile `companion`
- task `Hermes_Gateway_companion`
- loopback API `127.0.0.1:8642`
- model `qwen3.5-hermes:9b`
- verified context `65536`

Phase 0 source preservation is therefore closed.

### Native Phase 1 — source-preservation OPEN

Current stock state:

- dedicated Python 3.11 venv established
- `iai-pme==3.0.8` installed
- crypto initialization passed
- native Rust embedder passed
- Windows Scheduled Task registration succeeded
- stock daemon startup fails on Windows because startup references `signal.SIGHUP`, which Windows Python does not expose

No Orion patch has yet been accepted. Therefore there is no Phase 1 compatibility code to preserve yet.

Before Phase 1 can close, any accepted compatibility change and any Orion-owned setup/verification/rollback source must be committed to the appropriate repository.

## Historical Docker-era source

The following source remains intentionally preserved for provenance and legacy recovery:

- `build/orion-runtime/`
- `docs/phase2/`
- `docs/phase3/`
- `docs/phase4/`
- `scripts/phase2/`
- `scripts/phase3/`
- `scripts/phase4/`
- `scripts/rebuild/`

Earlier SP2/SP3/SP4A/SP4B evidence demonstrated functional source reproducibility for the former Docker implementation. That evidence remains valid for that historical runtime only; it does not establish current native-Windows reproducibility beyond the pieces separately accepted under v2.6.

The historical image/rebuild evidence is now explicitly labeled frozen/historical in:

- `build/orion-runtime/accepted-build-lineage.md`
- `build/orion-runtime/rebuild/README.md`

## External private recovery material

A source rebuild intentionally excludes private material. Recovery separately requires securely retained copies of applicable items such as:

- API/server credentials
- Discord credentials
- iai encryption key or accepted backup containing it
- Obsidian vault data when later phases make it authoritative
- intentionally retained private runtime backups/exports

These must never be committed to GitHub.

## Current completion condition

At the 2026-08-29 checkpoint:

- **Phase 0 native source reproducibility: PASS**
- **Phase 1 native source reproducibility: INCOMPLETE / BLOCKED ON STOCK IAI WINDOWS COMPATIBILITY**
- **full v2.6 clean-machine recovery: NOT YET CLAIMED**

The next reproducibility milestone is to resolve the iai Windows daemon blocker, preserve the accepted Phase 1 implementation source, then extend clean-machine recovery around the accepted native architecture.
