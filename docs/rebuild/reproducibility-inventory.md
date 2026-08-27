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

### Canonical rebuild source candidate

SP4A passed at commit `98aa7b73d2b14619264bcaabbbf6acadfee204e3`.

`build/orion-runtime/rebuild/` now contains one canonical rebuild-source candidate covering:

- the pinned Hermes v2026.8.18 base plus `ddgs==9.14.4`;
- isolated CPython 3.12 and iai 3.0.0 F2 construction;
- pinned BAAI/bge-small-en-v1.5 acquisition at revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`;
- verification of the accepted model artifact hashes;
- F5E model-bake assembly;
- iai 3.0.8 upgrade;
- reconstructed M4 `/opt/iai` composition into the Hermes/ddgs image;
- bounded M5 `recent_thread` serializer compatibility overlay;
- final-image verification;
- a single `build-orion-runtime.ps1` orchestration entry point.

SP4A generated the source, SHA-256 checked it, parsed the generated PowerShell with the actual Windows PowerShell parser, committed it, pushed it, and verified remote `main`. No Docker execution or runtime mutation occurred.

Closure record: `docs/rebuild/sp4a-rebuild-source-candidate-closure.md`.

## Remaining source-reproducibility gaps

The accepted custom runtime image is:

`orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`

Accepted image ID:

`sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`

Orion is **not yet declared clean-machine reproducible**. The highest-priority remaining work is SP4B:

- execute the committed rebuild candidate only against disposable `orion-rebuild-*` images/containers;
- confirm the pinned F5E model revision and three accepted artifact hashes;
- confirm the resulting iai runtime is 3.0.8 under isolated Python 3.12;
- confirm the reconstructed M4 composition carries both Hermes and `/opt/iai` correctly;
- confirm the M5 `recent_thread` serializer contract;
- prove the accepted `orion-iai-m5-c` container, `orion-iai-m5-data` volume, accepted final image ID/tag, and native iai Brain remain unchanged;
- capture the actual rebuilt image ID and package/artifact evidence;
- after SP4B, write the final clean-machine bootstrap/recovery procedure.

SP4A records known package provenance but does not claim a byte-identical dependency closure. The exact iai 3.0.8 wheel artifact hash remains to be captured during disposable validation.

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
