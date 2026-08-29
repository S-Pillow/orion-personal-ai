# Decision — Orion Source Preservation and Rebuild Policy

**Status: ACCEPTED / CURRENT — updated 2026-08-29**

## Decision

Orion must be reconstructable from GitHub plus explicitly documented external secrets/data. Accepted implementation code must not exist only on one workstation.

The controlling architecture is now **native Windows** under **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**. Historical Docker/Jarvis artifacts remain preserved, but they are not the current rebuild target.

## Repository roles

### `S-Pillow/orion-personal-ai`

Current canonical integration/control repository. It owns:

- Orion PRD/project-state references
- architecture and trust-boundary decisions
- current phase plans and acceptance evidence
- Orion-authored provisioning, verification, rollback, and recovery scripts
- compatibility notes and cross-component glue

### `S-Pillow/iai-personal-memory-engine`

Compatibility/upstream-tracking fork of `CodeAbra/iai-personal-memory-engine`.

It may carry:

- exact source pinning for Orion's iai dependency
- narrowly scoped compatibility fixes required by Orion
- upstream issue/PR preparation
- comparisons against upstream changes before upgrades

It must not become an Orion-specific alternative memory engine. Upstream iai semantics remain controlling unless explicitly changed by a later architecture decision.

### `S-Pillow/jarvis_ai`

Historical/possible-future HUD application fork. It remains preserved for provenance and possible reuse, but it is not an active v2.6 implementation dependency while native Phase 1 is incomplete.

### Hermes

Hermes remains an upstream dependency unless Orion begins carrying sustained source-level changes that justify a fork. Configuration and Orion-owned recovery/verification scripts belong in `orion-personal-ai`.

## Current native rebuild contract

A fresh Windows machine should be recoverable from GitHub plus intentionally external private material.

GitHub should preserve:

- exact accepted Hermes tag/package/commit pins
- named profile and required native paths
- Orion-authored PowerShell used to configure, verify, and roll back accepted runtime state
- non-secret configuration expectations
- Windows persistence/task details
- model/provider/runtime compatibility notes
- accepted migration/upgrade steps
- backup/restore procedures
- Phase 1 compatibility patches if one is ultimately required

The accepted native Phase 0 baseline is preserved at:

`scripts/phase0/Orion-Phase0-Hermes-Native-AcceptedBaseline.ps1`

Accepted Phase 0 snapshot:

- Hermes `v2026.8.27`
- package `0.20.6`
- commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- profile `companion`
- Windows persistence task `Hermes_Gateway_companion`
- local model `qwen3.5-hermes:9b`
- runtime context `65536`

## Private recovery material

GitHub must not preserve:

- API keys
- Discord tokens
- passwords
- `.env` files containing secrets
- iai encryption keys
- decrypted memory exports
- private vault contents
- runtime data stores or private backups

Those remain separately retained recovery material.

## Historical Docker preservation

The prior Docker/s6 runtime, image lineage, rebuild scripts, Phase 2/3 operational scripts, and Jarvis Phase 4 work remain in GitHub as historical evidence.

They are intentionally retained rather than deleted because they document prior engineering decisions and may help with regression archaeology or explicitly requested legacy recovery. They must be clearly labeled historical and must not be presented as current v2.6 acceptance.

The following are historical-only unless separately revalidated:

- `build/orion-runtime/`
- `docs/phase2/`
- `docs/phase3/`
- `docs/phase4/`
- `scripts/phase2/`
- `scripts/phase3/`
- `scripts/phase4/`
- `scripts/rebuild/`

## Current source-preservation gap

Phase 0 native source preservation is closed.

Phase 1 is not yet source-complete because stock `iai-pme==3.0.8` currently fails on Windows daemon startup due to an unguarded `signal.SIGHUP` reference. No Orion compatibility patch has yet been accepted or committed.

If a patch is authorized, the accepted patch must be preserved in `S-Pillow/iai-personal-memory-engine`, and Orion-specific installation/verification/rollback source must be preserved in `S-Pillow/orion-personal-ai` before Phase 1 closure.

## Operational rule going forward

When a ticket or phase changes accepted runtime behavior, the implementation artifact that produced that state must be committed to the appropriate GitHub repository before or at closure. Documentation-only closure is not sufficient when code or configuration mutation was required.

Historical artifacts may remain in place for stable links, but current documentation must clearly distinguish historical evidence from controlling architecture.
