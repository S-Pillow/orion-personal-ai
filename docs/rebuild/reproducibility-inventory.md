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
## Functional source-reproducibility closure
SP4B v2 passed. The committed source functionally rebuilt the Orion runtime under disposable tags while the accepted live runtime remained unchanged.
Validated rebuilt final image ID:
`sha256:d783e158062d865b1893306a0b835c576ee6e77a16e29ff41bb59354cade847e`
Validated contracts:
- pinned F5E model revision and accepted artifact hashes: PASS;
- iai-pme 3.0.8 under isolated Python 3.12: PASS;
- reconstructed combined runtime: PASS;
- M5 `recent_thread` serializer compatibility: PASS;
- ddgs 9.14.4: PASS;
- accepted `orion-iai-m5-c` container and `orion-iai-m5-data` volume unchanged: PASS;
- accepted container restart: none.
The rebuilt Docker image is not claimed byte-identical to the historical accepted image. The accepted MVP claim is functional source reproducibility for the validated contracts.
Recovery source:
- `scripts/rebuild/Prepare-Orion-Recovery-Workspace.ps1`
- `docs/rebuild/clean-machine-bootstrap.md`
- `docs/rebuild/sp4b-v2-disposable-rebuild-closure.md`

## External private recovery material
A source rebuild intentionally does not include user data or secrets. Recovery separately requires securely retained copies of items such as:
- API/provider credentials;
- Discord credentials;
- iai encryption key and/or a valid native iai backup containing it;
- Obsidian vault data;
- private runtime backups and memory exports as appropriate.
These must never be committed to the public source repositories.
## Completion condition
For MVP, Orion's source-preservation gate is functionally closed: implementation source and rebuild logic are in GitHub, SP4B v2 completed a disposable functional rebuild, and the recovery helper/procedure are preserved. A future clean-hardware smoke may add confidence but is not required to resume Phase 4.
