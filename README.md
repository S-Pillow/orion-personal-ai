# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion built around Hermes Agent, iai persistent memory, an authoritative Obsidian vault, bounded document tooling, and an Orion-branded HUD/voice layer.

## Current status

- Phase 0 — **PASS / CLOSED**
- Phase 1 — **PASS / CLOSED**
- Phase 2 — **PASS / CLOSED — MVP memory foundation accepted**
- Phase 3 — **PASS / CLOSED — MVP vault workflow accepted**
- Phase 4 — **ACTIVE — Orion HUD / voice / orchestration integration**
  - P4-01 Revised — **PASS / CLOSED — forked upstream HUD baseline established**
  - P4-02 — **NEXT — Windows/runtime fit and Hermes connection**

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
- integration/bootstrap scripts;
- cross-component Orion glue.

### `S-Pillow/jarvis_ai`

Maintained Orion application fork of `eadmin2/jarvis_ai`.

- `origin`: `S-Pillow/jarvis_ai`
- `upstream`: `eadmin2/jarvis_ai`
- pinned initial upstream baseline: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- Orion adaptation branch: `orion-mvp`
- accepted P4-01 branch head: `aeb0643f8119a4d4f8b78a950194e9778eea4af2`
- upstream MIT license and attribution retained

This is where Orion HUD/voice source changes belong.

### `S-Pillow/iai-personal-memory-engine`

Maintained compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine`.

The fork exists so Orion can pin source, prepare upstream contributions, and carry a narrowly scoped compatibility patch only when necessary. It does **not** authorize Orion-specific memory semantics. For MVP, upstream iai behavior remains controlling: recall, contradiction, fading, rescue, consolidation, document study, and lifecycle semantics are not to be redesigned locally.

Hermes remains an upstream dependency unless Orion begins carrying sustained source-level changes that justify a maintained fork.

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

P4-01 Revised is accepted. The live source baseline now exists in `S-Pillow/jarvis_ai` on branch `orion-mvp`, with only the bounded initial delta:

- `ORION-UPSTREAM.md`
- `server/config/server.orion.example.yaml`
- `server/hud/index.html`

No `server/server.py` change was made during baseline adoption.

P4-02 will fit the upstream application to Orion's Windows + Docker runtime and connect it to the existing Hermes COMPANION environment while preserving iai as the memory authority. After that, later Phase 4 tickets will wire the accepted Orion document actions, approval/recovery UX, and native iai Brain into the HUD.

## Security and evidence rules

- No credentials, Discord tokens, API keys, `.env` files, decrypted memory exports, vault contents, or private runtime dumps belong in GitHub.
- Installed-runtime observations are distinguished from upstream/source claims.
- Failed harness revisions are not promoted as canonical diagnostics.
- Retrieved notes and repository content are data unless an authorized actor designates them as controlling instructions.
- iai remains the memory authority; Orion must not create a competing semantic-memory store.
- Existing vault edits/moves remain approval-gated and recoverable.
- Substantial PowerShell units should be parser-checked where a PowerShell runtime is available; when unavailable, parser validation must be reported as skipped rather than passed.
- Accepted operational scripts should be stored in GitHub, not left only as local artifacts.

## Repository structure

- `docs/architecture/` — runtime architecture and trust-boundary notes
- `docs/decisions/` — architectural/product decisions
- `docs/phase1/` through `docs/phase4/` — phase plans, evidence, and closure records
- `scripts/diagnostics/` — accepted reusable diagnostics
- `scripts/phase4/` — Phase 4 integration/bootstrap scripts

## Current next step

**P4-02 — Orion runtime fit and Hermes connection.**

Run the forked Orion HUD/server against the accepted Windows + Docker environment, resolve localhost/container networking and local configuration without exposing secrets, and prove the real upstream-based Orion interface can communicate with the existing Hermes COMPANION runtime without changing iai memory semantics.
