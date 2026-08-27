# Orion Reproducibility Inventory

**Status: ACTIVE — August 27, 2026**

This document tracks whether Orion can be rebuilt on a new machine from GitHub plus intentionally external private material.

## Source repositories

- `S-Pillow/orion-personal-ai` — Orion integration/control source, scripts, docs, rebuild instructions.
- `S-Pillow/jarvis_ai` — Orion HUD/voice application fork.
- `S-Pillow/iai-personal-memory-engine` — iai compatibility/tracking fork.

## Preserved and reproducible source

### Application / orchestration

- Phase 4 HUD upstream baseline and exact pin.
- Orion HUD `orion-mvp` branch at `aeb0643f8119a4d4f8b78a950194e9778eea4af2`.
- P4-01 accepted fork-adoption implementation in `scripts/phase4/`.
- P4-02A corrected runtime-discovery implementation in `scripts/phase4/p4-02a-runtime-fit-discovery-v2.ps1`.
- Phase 1–4 architecture and acceptance records.
- iai upstream source through the maintained fork.

### Accepted Phase 2 / Phase 3 operational code

SP2 preserved all 11 accepted local Phase 2/3 implementation artifacts in GitHub at commit `12d12f1e665110c494ecc758dfa52b4c51e0805f`.

Canonical paths now include:

- `scripts/phase2/accepted/Orion-Phase2-Erase-Isolation-Closeout.ps1`
- `scripts/phase3/accepted/Orion-Phase3-Create-Vault-Retrieval-Sidecar-v2.ps1`
- `scripts/phase3/accepted/Orion-Phase3-P3-02A-Native-Iai-Vault-Watch.ps1`
- `scripts/phase3/accepted/Orion-Phase3-P3-02B-Exact-Vault-Resolver.ps1`
- `scripts/phase3/accepted/Orion-Phase3-P3-03-Vault-Memory-Acceptance.ps1`
- `scripts/phase3/accepted/Orion-Phase3-P3-04-Create-Inbox-Draft.ps1`
- `scripts/phase3/accepted/Orion-Phase3-P3-04-Provision-Dedicated-Inbox-v3.ps1`
- `scripts/phase3/accepted/Orion-Phase3-P3-05-Controlled-Vault-Broker-v2.ps1`
- `scripts/phase3/accepted/Orion-Phase3-P3-05-Provision-And-Accept-Controlled-Broker-v3.ps1`
- `scripts/phase3/accepted/Orion-Phase3-P3-06-Vault-Destination-Recommender.ps1`
- `scripts/phase3/accepted/Orion-Phase3-P3-06-Vault-Destination-Recommender-Acceptance.ps1`

Their accepted SHA-256 identities are recorded in `scripts/source-preservation-accepted-manifest.md`.

### Accepted runtime build-source evidence

SP3 preserved the available accepted runtime build-source evidence at commit `37d1b24121c68262585e0ab447e23d7c24a02ed3`.

Preserved exact source:

- `build/orion-runtime/historical/Start-Hermes.accepted.ps1`
- `build/orion-runtime/historical/Dockerfile.hermes-ddgs.accepted`
- `build/orion-runtime/historical/PH2-IAI-M2-v3.0.8-disposable-native-hermes-hook-wiring.ps1`
- `build/orion-runtime/historical/PH2-IAI-M5-serializer-fix-build-v2.ps1`

The build lineage is recorded in `build/orion-runtime/accepted-build-lineage.md`.

The historical `PH2-IAI-M4-source-reviewed-final.ps1` file was not present locally and is not claimed preserved.

## Remaining source-reproducibility gaps

The accepted custom runtime image is:

`orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`

Accepted image ID:

`sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`

The source situation is now substantially better, but Orion is **not yet declared clean-machine reproducible**. Remaining work:

- create one canonical fresh-machine build/provision implementation from the preserved evidence;
- reconstruct the M4 composition step because its historical source script is missing;
- convert the F5E embedding-model acquisition/assembly lineage into a clean canonical rebuild unit;
- resolve stronger package/wheel provenance where needed for deterministic rebuild confidence;
- validate the complete source rebuild in disposable images/containers without changing the accepted live runtime;
- write the final clean-machine bootstrap/recovery procedure.

SP4 is the next rebuild unit: produce the canonical non-live rebuild implementation, then validate it against disposable targets before promoting it as Orion's recovery mechanism.

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
