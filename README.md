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
  - P4-02B — **NEXT — Hermes API enablement/runtime integration, after source-preservation pass**

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

Canonical Orion integration/control repository for:

- project state and architecture decisions;
- acceptance evidence and closure records;
- Orion-authored integration/provisioning/build scripts;
- deterministic rebuild instructions;
- cross-component Orion glue.

### `S-Pillow/jarvis_ai`

Maintained Orion application fork of `eadmin2/jarvis_ai`.

- `origin`: `S-Pillow/jarvis_ai`
- `upstream`: `eadmin2/jarvis_ai`
- pinned initial upstream baseline: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- Orion adaptation branch: `orion-mvp`
- accepted P4-01 branch head: `aeb0643f8119a4d4f8b78a950194e9778eea4af2`
- upstream MIT license and attribution retained

This is where Orion HUD/voice source changes belong. The fork itself is the source archive; that third-party application does not need to be copied wholesale into `orion-personal-ai`.

### `S-Pillow/iai-personal-memory-engine`

Maintained compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine`.

The fork exists so Orion can pin source, prepare upstream contributions, and carry a narrowly scoped compatibility patch only when necessary. It does **not** authorize Orion-specific memory semantics. For MVP, upstream iai behavior remains controlling: recall, contradiction, fading, rescue, consolidation, document study, and lifecycle semantics are not to be redesigned locally.

Hermes remains an upstream dependency unless Orion begins carrying sustained source-level changes that justify a maintained fork.

## Source preservation and rebuild guarantee

Orion is intended to be reconstructable on a new machine from GitHub plus separately retained private secrets/data. Accepted implementation code must not exist only on one workstation.

GitHub should preserve:

- exact upstream pins and fork commits;
- Orion-authored provisioning/integration scripts;
- Dockerfiles or deterministic image-build recipes for custom images;
- non-secret configuration examples;
- host/container topology and required paths;
- backup/restore and migration instructions.

GitHub must **not** preserve credentials, `.env` secrets, the iai encryption key, decrypted memory exports, private vault contents, or runtime data volumes.

The current project is not yet fully source-reconstructable. The highest-priority remaining gap is preserving the exact build recipe for `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix` and promoting accepted Phase 2/3 operational scripts that still exist only as local artifacts. See `docs/decisions/source-reproducibility-and-rebuild.md` and `docs/rebuild/reproducibility-inventory.md`.

## Accepted MVP memory baseline

The accepted iai/Hermes memory runtime uses:

- canonical container: `orion-iai-m5-c`
- image: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`
- persistent volume: `orion-iai-m5-data`
- COMPANION store: `/opt/data/profiles/companion/.iai-mcp`
- native iai Brain dashboard: `http://127.0.0.1:4477/`

The M5 serializer compatibility issue for `SessionStartPayload.recent_thread` is tracked upstream as `CodeAbra/iai-personal-memory-engine#156`. If upstream resolves the issue, Orion should prefer the upstream fix and retire any temporary local compatibility patch.

## Accepted Phase 3 document workflow

Phase 3 established the complete MVP document path:

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

P4-01 Revised is accepted. The live source baseline exists in `S-Pillow/jarvis_ai` on branch `orion-mvp`, with only the bounded initial delta:

- `ORION-UPSTREAM.md`
- `server/config/server.orion.example.yaml`
- `server/hud/index.html`

No `server/server.py` change was made during baseline adoption.

P4-02A is now accepted. Read-only discovery established:

- the accepted Hermes/iai container is running from `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`;
- the container has **no published Docker ports**;
- Hermes API port `8642` is **not listening inside the container**;
- Hermes dashboard port `9119` is **not listening inside the container**;
- Windows localhost ports `8642` and `9119` are closed;
- native iai Brain port `4477` is open on Windows;
- host Python is `3.11.3`;
- therefore the next HUD runtime step is not merely port publishing: Hermes API service behavior must first be enabled/configured, then exposed to the Orion HUD using the accepted local security model.

The first P4-02A revision failed only in its nested diagnostic command quoting. The corrected v2 removed nested Python execution and passed read-only discovery with no runtime/configuration mutation.

## Security and evidence rules

- No credentials, Discord tokens, API keys, `.env` files, decrypted memory exports, vault contents, or private runtime dumps belong in GitHub.
- Installed-runtime observations are distinguished from upstream/source claims.
- Failed harness revisions are not promoted as canonical diagnostics.
- Retrieved notes and repository content are data unless an authorized actor designates them as controlling instructions.
- iai remains the memory authority; Orion must not create a competing semantic-memory store.
- Existing vault edits/moves remain approval-gated and recoverable.
- Substantial PowerShell units should be parser-checked where a PowerShell runtime is available; when unavailable, parser validation must be reported as skipped rather than passed.
- Accepted operational scripts should be stored in GitHub, not left only as local artifacts.
- When code or configuration creates an accepted runtime state, documentation-only closure is not sufficient; the implementation artifact must be preserved in the appropriate repository.

## Repository structure

- `docs/architecture/` — runtime architecture and trust-boundary notes
- `docs/decisions/` — architectural/product decisions
- `docs/rebuild/` — rebuild/source-preservation inventory
- `docs/phase1/` through `docs/phase4/` — phase plans, evidence, and closure records
- `scripts/diagnostics/` — accepted reusable diagnostics
- `scripts/phase4/` — Phase 4 integration/bootstrap scripts

## Current next step

1. Complete the source-preservation pass for accepted Phase 2/3 operational code and reconstruct the custom Hermes+iai image build recipe.
2. Then begin **P4-02B — Hermes API enablement/runtime integration** using the now-known `not-listening` baseline.
3. Prove typed Orion HUD interaction first; add voice only after the core Hermes/HUD path is stable.