# Decision — Orion Source Preservation and Rebuild Policy

**Status: ACCEPTED — August 27, 2026**

## Decision

Orion must be reconstructable from GitHub plus explicitly documented external secrets/data. Accepted implementation code must not exist only on one workstation.

The project therefore uses three complementary source locations:

1. `S-Pillow/orion-personal-ai` for Orion-authored integration code, provisioning scripts, deployment/build recipes, architecture, evidence, and rebuild instructions.
2. `S-Pillow/jarvis_ai` for the actual Orion HUD/voice application source derived from `eadmin2/jarvis_ai`.
3. `S-Pillow/iai-personal-memory-engine` for a controlled compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine` when Orion needs source-level compatibility work or upstream contributions.

Third-party source should not be duplicated wholesale into `orion-personal-ai` when it already exists in a maintained fork. The fork is the code repository. Orion-authored glue and reproducibility instructions belong in `orion-personal-ai`.

## Rebuild contract

A fresh-machine rebuild should be possible without access to the original development workstation except for intentionally external private material.

GitHub should preserve:

- exact upstream repository and commit pins;
- Orion fork branches and commits;
- Dockerfiles or image-build scripts for any custom image Orion depends on;
- Orion-authored PowerShell/Python scripts used to provision accepted runtime components;
- non-secret example configuration;
- host/container topology and required paths;
- accepted migration/upgrade steps;
- backup/restore procedures;
- version and compatibility notes.

GitHub must not preserve:

- API keys, Discord tokens, passwords, `.env` files containing secrets;
- the iai encryption key;
- decrypted memory exports;
- private vault content;
- runtime data volumes or private backups.

Those remain external recovery material and must be documented separately from source.

## Fork rules

### `S-Pillow/jarvis_ai`

This is an application fork. Orion-specific HUD/voice source changes belong here. The original `eadmin2/jarvis_ai` remains `upstream`.

### `S-Pillow/iai-personal-memory-engine`

This is a compatibility/tracking fork. Upstream iai semantics remain authoritative for Orion MVP. The fork may carry a narrowly scoped compatibility patch or upstream contribution when necessary, but must not become a separate Orion memory design.

### Hermes

Hermes remains upstream-only until Orion is carrying source-level changes that cannot be represented as configuration, build instructions, or integration glue. A custom image alone is not sufficient reason to fork Hermes; unrecoverable source divergence would be.

## Current rebuild gap

As of this decision, Orion has reproducible source for the forked HUD baseline and substantial architecture/evidence, but the repository is not yet a complete fresh-machine rebuild package.

The highest-priority remaining source-preservation gap is the exact build recipe for the accepted custom Hermes + iai image `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`, including the narrow `recent_thread` serializer compatibility change and all image-layer installation steps. Accepted Phase 2/3 operational scripts that still exist only as local artifacts must also be promoted into `orion-personal-ai`.

This gap must be closed before Orion is treated as independently reconstructable.

## Operational rule going forward

When a ticket changes production/runtime behavior, its accepted implementation artifact must be committed to the appropriate GitHub repository before or at closure. Documentation-only closure is not sufficient when code or configuration was required to produce the accepted state.

**Intent status: PRESERVED.** This policy preserves the upstream-first architecture while making Orion recoverable, forkable, and maintainable as a real software project.