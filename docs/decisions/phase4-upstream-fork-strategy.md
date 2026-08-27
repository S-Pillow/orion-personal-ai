# Decision — Phase 4 Upstream Fork Strategy

**Status: ACCEPTED — updated August 27, 2026**

## Decision

Orion uses maintained GitHub forks when preserving upstream history and source provenance materially improves the product or compatibility workflow.

Two forks are now part of the Orion repository model:

- `S-Pillow/jarvis_ai` — Orion's maintained HUD / voice / orchestration application fork of `eadmin2/jarvis_ai`.
- `S-Pillow/iai-personal-memory-engine` — Orion's compatibility/upstream-tracking fork of `CodeAbra/iai-personal-memory-engine`.

`S-Pillow/orion-personal-ai` remains the canonical Orion integration/control repository and does not absorb wholesale copies of either upstream codebase.

## Repository roles

### `S-Pillow/orion-personal-ai`

Owns:

- Orion PRD/project state references;
- architecture and trust-boundary decisions;
- phase plans and acceptance evidence;
- integration/bootstrap scripts;
- cross-component Orion glue.

### `S-Pillow/jarvis_ai`

Owns:

- actual HUD/voice application source;
- user-facing Orion branding;
- Windows/runtime adaptations to the upstream application;
- Orion-specific HUD features and service integrations;
- future upstream merges/comparisons.

Git remote model:

- `origin` -> `S-Pillow/jarvis_ai`
- `upstream` -> `eadmin2/jarvis_ai`

Initial baseline:

- pinned upstream commit: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- Orion branch: `orion-mvp`
- accepted P4-01 branch head: `aeb0643f8119a4d4f8b78a950194e9778eea4af2`
- upstream MIT license retained

### `S-Pillow/iai-personal-memory-engine`

Owns only:

- reproducible source pinning for Orion's accepted iai dependency;
- preparation of upstream fixes or pull requests;
- narrowly scoped compatibility patches when Orion actually needs to carry one;
- comparison against upstream changes before upgrades.

It does **not** own Orion-specific alternatives to iai's memory behavior.

The following remain upstream-controlled for MVP:

- semantic recall/ranking;
- contradiction/correction semantics;
- fading and rescue;
- consolidation;
- document study/watch behavior;
- temporal/lifecycle semantics.

When upstream resolves a compatibility issue that Orion temporarily patches, the preferred outcome is to retire the local patch and return to clean upstream behavior.

Recommended remote model when the fork is cloned locally:

- `origin` -> `S-Pillow/iai-personal-memory-engine`
- `upstream` -> `CodeAbra/iai-personal-memory-engine`

## What not to fork by default

A dependency does not need an Orion fork merely because Orion uses it.

Hermes remains an upstream dependency unless Orion begins carrying sustained source-level changes that require a maintained source fork. Configuration, Docker build integration, and deployment glue alone are not sufficient reason.

## Why

This model preserves upstream history and provenance, puts actual Orion application source on GitHub, gives compatibility work a clean upstream contribution path, and avoids turning Orion's main repository into a vendor dump.

**Intent status: PRESERVED.** The Jarvis fork supports Orion product adaptation; the iai fork supports reproducibility and compatibility without weakening the decision to use iai as the canonical memory system.
