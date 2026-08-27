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
  - P4-02B — **NEXT — Hermes API enablement/runtime integration, after SP4B disposable rebuild validation**

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

Important paths:

- `scripts/phase2/accepted/`
- `scripts/phase3/accepted/`
- `scripts/source-preservation-accepted-manifest.md`
- `build/orion-runtime/historical/`
- `build/orion-runtime/accepted-build-lineage.md`
- `build/orion-runtime/rebuild/`
- `docs/rebuild/reproducibility-inventory.md`

The project is **not yet declared clean-machine reproducible**. SP4B must execute the committed rebuild candidate only against disposable `orion-rebuild-*` images/containers and verify the pinned model artifacts, iai 3.0.8, reconstructed M4 composition, and M5 `recent_thread` serializer contract while proving that the accepted live runtime remains untouched.

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

Therefore P4-02B must enable Hermes API service behavior before exposing the minimum safe route to the Orion HUD. Port publishing alone is not sufficient.

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

1. Run **SP4B v2 - disposable rebuild validation** against the patched canonical rebuild source.
2. If SP4B passes, finalize the clean-machine bootstrap/recovery procedure and close the source-preservation gate.
3. Then begin **P4-02B — Hermes API enablement/runtime integration** using the accepted `not-listening` baseline.
4. Prove typed Orion HUD interaction first; add voice only after the core Hermes/HUD path is stable.
