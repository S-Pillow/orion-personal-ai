# Orion Reproducibility Inventory

**Status: ACTIVE — August 27, 2026**

This document tracks whether Orion can be rebuilt on a new machine from GitHub plus intentionally external private material.

## Source repositories

- `S-Pillow/orion-personal-ai` — Orion integration/control source, scripts, docs, rebuild instructions.
- `S-Pillow/jarvis_ai` — Orion HUD/voice application fork.
- `S-Pillow/iai-personal-memory-engine` — iai compatibility/tracking fork.

## Preserved and reproducible

- Phase 4 HUD upstream baseline and exact pin.
- Orion HUD `orion-mvp` branch at `aeb0643f8119a4d4f8b78a950194e9778eea4af2`.
- P4-01 accepted fork-adoption implementation in `scripts/phase4/`.
- P4-02A corrected runtime-discovery implementation in `scripts/phase4/p4-02a-runtime-fit-discovery-v2.ps1`.
- Phase 1–4 architecture and acceptance records.
- iai upstream source through the maintained fork.

## Source-preservation work still required

The following accepted local implementation artifacts must be promoted into GitHub so they are not dependent on the original workstation:

### Phase 2

- iai MCP wiring script.
- native iai Brain dashboard provisioning script.
- accepted JSONL export helper.
- Phase 2 erase/isolation administrative helper.
- final iai core acceptance helper where useful for rebuild verification.

### Phase 3

- read-only vault retrieval sidecar provisioning.
- native iai vault-watch provisioning.
- exact vault resolver.
- Orion inbox draft creator and inbox sidecar provisioning.
- controlled vault broker and provisioning.
- vault destination recommender.

Only accepted/current revisions should be promoted as canonical source. Failed and superseded harness revisions should remain historical evidence rather than rebuild dependencies.

## Critical rebuild gap

The accepted custom image currently running Orion is:

`orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`

Its exact source build recipe is not yet preserved in GitHub. Before Orion is considered independently reconstructable, GitHub must contain the Dockerfile/build script or equivalent deterministic recipe that records:

- the pinned Hermes base/source version;
- iai 3.0.8 installation;
- the isolated iai Python environment;
- the exact `SessionStartPayload.recent_thread` compatibility change;
- any copied launcher/config files required by the accepted image;
- resulting image tag/version convention.

This is the highest-priority source-recovery item because a Docker image existing on one workstation is not a sufficient source archive.

## External private recovery material

A source rebuild intentionally does not include user data or secrets. Recovery separately requires securely retained copies of items such as:

- API/provider credentials;
- Discord credentials;
- iai encryption key and/or a valid native iai backup containing it;
- Obsidian vault data;
- private runtime backups and memory exports as appropriate.

These must never be committed to the public source repositories.

## Completion condition

Orion is considered source-reproducible when a clean Windows machine can clone the documented repositories, build/provision the accepted runtime from committed source, restore separately held private data/secrets, and reach the accepted MVP state without depending on undocumented files from the original workstation.