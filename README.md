# Orion Personal AI
Orion is a privacy-first, local-first personal AI companion built around Hermes Agent, iai persistent memory, an authoritative Obsidian vault, bounded document tooling, and an Orion-branded HUD/voice layer.
## Current status
- Phase 0 — **PASS / CLOSED**
- Phase 1 — **PASS / CLOSED**
- Phase 2 — **PASS / CLOSED — MVP memory foundation accepted**
- Phase 3 — **PASS / CLOSED — MVP vault workflow accepted**
- Phase 4 — **ACTIVE — Orion HUD / voice / orchestration integration**
  - P4-01 Revised — **PASS / CLOSED — forked upstream HUD baseline established**
  - P4-02A — **PASS / CLOSED — runtime-fit discovery complete**
  - P4-02B — **IN PROGRESS — Hermes API enablement/runtime integration**
    - P4-02B1 — v3 proved the s6 supervision boundary and rolled back cleanly; v4 profile-.env enablement pending live acceptance
The current controlling product requirements document is **Orion Master PRD v1.1.3**.
## Governing architecture
- **Hermes Agent** is the local agent runtime.
- **iai-pme 3.0.8** is Orion's canonical memory and semantic-recall engine for MVP.
- **Native iai Brain** remains the authoritative detailed memory-management UI.
- **Obsidian** remains the authoritative human-facing document vault at `C:\Personal\Me`.
- Orion's accepted Phase 3 document path provides exact source resolution, a dedicated draft inbox, native-iai-backed destination recommendations, approval-gated vault edits/moves, and exact recovery/restore.
- **eadmin2/jarvis_ai** is the upstream HUD / voice / orchestration application baseline for Phase 4.
- **CodeAbra/iai-personal-memory-engine** remains the upstream authority for iai behavior.
## Repository strategy
### `S-Pillow/orion-personal-ai`
Canonical Orion integration/control repository for project state, architecture decisions, acceptance evidence, Orion-authored provisioning/integration/build scripts, deterministic rebuild instructions, and cross-component glue.
### `S-Pillow/jarvis_ai`
Maintained Orion application fork of `eadmin2/jarvis_ai`.
- `origin`: `S-Pillow/jarvis_ai`
- `upstream`: `eadmin2/jarvis_ai`
- pinned initial upstream baseline: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- Orion adaptation branch: `orion-mvp`
- accepted P4-01 branch head: `aeb0643f8119a4d4f8b78a950194e9778eea4af2`
- upstream MIT license and attribution retained
This is where Orion HUD/voice source changes belong. The fork itself is the source archive; the application does not need to be copied wholesale into `orion-personal-ai`.
### `S-Pillow/iai-personal-memory-engine`
Maintained compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine`.
The fork exists so Orion can pin source, prepare upstream contributions, and carry a narrowly scoped compatibility patch only when necessary. It does **not** authorize Orion-specific memory semantics. Upstream iai behavior remains controlling for MVP.
Hermes remains an upstream dependency unless sustained source-level changes later justify a fork.
## Source preservation and rebuild status
Orion is intended to be reconstructable on a new machine from GitHub plus separately retained private secrets/data. Accepted implementation code must not exist only on one workstation.
Completed source-preservation work:
- **SP2 PASS** — all 11 accepted Phase 2/3 operational scripts preserved in GitHub at commit `12d12f1e665110c494ecc758dfa52b4c51e0805f`.
- **SP3 PASS** — accepted launcher, accepted Hermes ddgs Dockerfile, available M2/M5 historical build harnesses, and accepted image-lineage evidence preserved at commit `37d1b24121c68262585e0ab447e23d7c24a02ed3`.
- **SP4A PASS** — canonical rebuild-source candidate created and committed at `98aa7b73d2b14619264bcaabbbf6acadfee204e3`; generated PowerShell parsed successfully on the Windows host and no Docker/runtime mutation occurred.
- **SP4B v1 diagnostic** - rebuild reached Hermes/ddgs and iai F2, then exposed a missing acquisition-only huggingface_hub dependency; accepted Orion runtime remained unchanged. SP4B v2 carries the bounded source fix.
- **SP4B v2 PASS** - committed source rebuilt a disposable functional Orion runtime; pinned F5E hashes, iai 3.0.8/Python 3.12, `recent_thread`, and ddgs 9.14.4 passed while the accepted runtime remained unchanged.
Important paths:
- `scripts/phase2/accepted/`
- `scripts/phase3/accepted/`
- `scripts/source-preservation-accepted-manifest.md`
- `build/orion-runtime/historical/`
- `build/orion-runtime/accepted-build-lineage.md`
- `build/orion-runtime/rebuild/`
- `docs/rebuild/reproducibility-inventory.md`
- `scripts/rebuild/Prepare-Orion-Recovery-Workspace.ps1`
- `docs/rebuild/clean-machine-bootstrap.md`
The MVP source-preservation gate is **functionally closed**. SP4B v2 rebuilt the committed runtime source successfully under disposable tags, and the clean-machine recovery helper/procedure are preserved. This is functional source reproducibility, not a byte-identical Docker-image claim.
GitHub must never contain credentials, `.env` secrets, the iai encryption key, decrypted memory exports, private vault contents, or runtime data volumes.
## Accepted MVP memory baseline
The accepted iai/Hermes memory runtime uses:
- canonical container: `orion-iai-m5-c`
- image: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`
- image ID: `sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`
- persistent volume: `orion-iai-m5-data`
- COMPANION store: `/opt/data/profiles/companion/.iai-mcp`
- native iai Brain dashboard: `http://127.0.0.1:4477/`
The M5 serializer compatibility issue for `SessionStartPayload.recent_thread` is tracked upstream as `CodeAbra/iai-personal-memory-engine#156`. If upstream resolves it, Orion should prefer the upstream fix and retire the temporary local compatibility overlay.
## Accepted Phase 3 document workflow
`Obsidian vault -> native iai watch / memory -> recall + exact source resolution -> Orion inbox draft -> iai-backed destination recommendation -> explicit approval -> controlled move/edit -> recovery / restore`
Accepted boundaries:
- normal exact retrieval uses a read-only vault sidecar;
- Orion drafts are created only in `C:\Personal\Orion-Inbox`;
- drafts remain outside the authoritative vault until explicitly promoted;
- vault changes use preview + exact diff + approval token + stale-preview protection;
- successful changes create recovery evidence in `C:\Personal\Orion-Recovery`;
- iai remains separate from document write-control semantics.
## Phase 4 direction
Phase 4 adapts the proven `jarvis_ai` HUD/voice application into Orion rather than building a parallel interface.
P4-02A established that the accepted Hermes/iai container has no published ports, Hermes ports `8642` and `9119` are not listening inside the container, Windows ports `8642` and `9119` are closed, native iai Brain `4477` is open, and the resolved Hermes API route is `not-listening`.
Hermes v2026.8.18 source confirms the API adapter supports `API_SERVER_HOST` and `API_SERVER_PORT`; its defaults are `127.0.0.1:8642`. P4-02B1 therefore keeps authenticated Hermes API service on container `0.0.0.0:8642` with no Windows host publication. The Orion server will reach it through a dedicated Docker bridge network, keeping `API_SERVER_KEY` server-side.
P4-02B1 v1 exposed a StrictMode array-handling defect in the harness before mutation. v2 then discovered that the COMPANION gateway already exists as one supervised gateway process. v3 proved the remaining configuration boundary: `gateway run --replace` inside the s6-based image delegates back to the s6-supervised service, so API variables supplied only to a transient `docker exec` process do not reach the actual gateway. v3 rolled the gateway, network, and temporary secret changes back successfully. Hermes' supported profile model stores per-profile settings/secrets in the profile `.env`, so v4 applies only the four `API_SERVER_*` values to `/opt/data/profiles/companion/.env` and uses the supervised `hermes -p companion gateway restart` lifecycle. Detailed evidence is in `docs/phase4/p4-02b1-hermes-api-enablement.md`.
## Security and evidence rules
- No credentials, Discord tokens, API keys, `.env` files, decrypted memory exports, vault contents, or private runtime dumps belong in GitHub.
- Installed-runtime observations are distinguished from upstream/source claims.
- Failed harness revisions are not promoted as canonical diagnostics.
- iai remains the memory authority; Orion must not create a competing semantic-memory store.
- Existing vault edits/moves remain approval-gated and recoverable.
- Accepted operational scripts must be stored in GitHub, not left only as local artifacts.
- When code or configuration creates an accepted runtime state, documentation-only closure is not sufficient; the implementation artifact must be preserved in the appropriate repository.
## Repository structure
- `build/orion-runtime/` — accepted runtime build-source evidence and canonical rebuild candidate
- `docs/architecture/` — runtime architecture and trust-boundary notes
- `docs/decisions/` — architectural/product decisions
- `docs/rebuild/` — rebuild/source-preservation inventory and acceptance records
- `docs/phase1/` through `docs/phase4/` — phase plans, evidence, and closure records
- `scripts/diagnostics/` — accepted reusable diagnostics
- `scripts/phase2/accepted/` — preserved accepted Phase 2 operational source
- `scripts/phase3/accepted/` — preserved accepted Phase 3 operational source
- `scripts/phase4/` — Phase 4 integration/bootstrap scripts
## Current next step
1. Run **P4-02B1 v4 — profile-configured authenticated Hermes API enablement** using the delivered candidate artifact; do not promote it to the canonical accepted script until the live acceptance markers pass.
2. If P4-02B1 passes, promote the exact v4 source to `scripts/phase4/p4-02b1-enable-hermes-api.ps1`, close P4-02B1 in README/docs, and wire the Orion/Jarvis server to `http://orion-iai-m5-c:8642` over the dedicated control network for typed interaction.
3. Add voice only after the typed Hermes/HUD path is stable.