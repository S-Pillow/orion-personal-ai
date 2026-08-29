# Decision — Phase 4 Upstream Fork Strategy

**Status: SUPERSEDED / HISTORICAL — 2026-08-29**

> This decision records the earlier Jarvis/Phase-4 repository strategy. It is retained for provenance but is no longer controlling under **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**. The current implementation sequence is native Windows: complete native Hermes Phase 0, then native iai Phase 1, and only after Phase 1 acceptance resume HUD work. `S-Pillow/jarvis_ai` therefore remains a historical/possible-future HUD fork, not the active Orion implementation repository for the current phase.

## Historical decision

Orion used maintained GitHub forks when preserving upstream history and source provenance materially improved the product or compatibility workflow.

Two forks were established:

- `S-Pillow/jarvis_ai` — Orion's HUD / voice / orchestration application fork of `eadmin2/jarvis_ai`.
- `S-Pillow/iai-personal-memory-engine` — Orion's compatibility/upstream-tracking fork of `CodeAbra/iai-personal-memory-engine`.

`S-Pillow/orion-personal-ai` remained the canonical Orion integration/control repository and did not absorb wholesale copies of either upstream codebase.

## Repository roles under the historical strategy

### `S-Pillow/orion-personal-ai`

Owned:

- Orion PRD/project state references
- architecture and trust-boundary decisions
- phase plans and acceptance evidence
- integration/bootstrap scripts
- cross-component Orion glue

### `S-Pillow/jarvis_ai`

Historically owned:

- HUD/voice application source
- user-facing Orion branding
- Windows/runtime adaptations to the upstream application
- Orion-specific HUD features and service integrations
- future upstream merges/comparisons

Historical remote model:

- `origin` -> `S-Pillow/jarvis_ai`
- `upstream` -> `eadmin2/jarvis_ai`

Historical baseline:

- pinned upstream commit: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- Orion branch: `orion-mvp`
- accepted P4-01 branch head: `aeb0643f8119a4d4f8b78a950194e9778eea4af2`
- upstream MIT license retained

### `S-Pillow/iai-personal-memory-engine`

This repository role remains useful under v2.6, but only as a compatibility/upstream-tracking fork. It may own:

- reproducible source pinning for Orion's iai dependency
- preparation of upstream fixes or pull requests
- narrowly scoped compatibility patches when required
- comparison against upstream changes before upgrades

It must not become a separate Orion memory implementation. Upstream iai semantics remain controlling unless an explicit Orion decision says otherwise.

Recommended remote model:

- `origin` -> `S-Pillow/iai-personal-memory-engine`
- `upstream` -> `CodeAbra/iai-personal-memory-engine`

## Current v2.6 interpretation

- `S-Pillow/orion-personal-ai` is the active integration/control repository.
- `S-Pillow/iai-personal-memory-engine` is the appropriate place for a narrowly scoped Windows compatibility patch if Phase 1 requires one.
- `S-Pillow/jarvis_ai` is frozen as historical/possible-future HUD source until native iai Phase 1 passes.
- Hermes remains an upstream dependency unless sustained source-level divergence later justifies a fork.

The useful repository-separation principle is preserved; the old Phase-4 execution order is not.
