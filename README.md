# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion built around Hermes Agent, iai persistent memory, an authoritative Obsidian vault, bounded document tooling, and an Orion-branded HUD/voice layer.

## Current status

- Phase 0 — **PASS / CLOSED**
- Phase 1 — **PASS / CLOSED**
- Phase 2 — **PASS / CLOSED — MVP memory foundation accepted**
- Phase 3 — **PASS / CLOSED — MVP vault workflow accepted**
- Phase 4 — **ACTIVE — Orion HUD / voice / orchestration integration**

The current controlling product requirements document is **Orion Master PRD v1.1.3**.

## Governing architecture

- **Hermes Agent** is the local agent runtime.
- **iai-pme 3.0.8** is Orion's canonical memory and semantic-recall engine for MVP.
- **Native iai Brain** remains the authoritative detailed memory-management UI.
- **Obsidian** remains the authoritative human-facing document vault at `C:\Personal\Me`.
- Orion's accepted Phase 3 document path provides exact source resolution, a dedicated draft inbox, native-iai-backed destination recommendations, approval-gated vault edits/moves, and exact recovery/restore.
- **eadmin2/jarvis_ai** is the selected upstream HUD / voice / orchestration application baseline for Phase 4. Orion will adapt that application rather than build a parallel HUD from scratch.

## Repository strategy

This repository, `S-Pillow/orion-personal-ai`, is the canonical Orion integration/control repository. It contains project state, architecture decisions, acceptance evidence, integration scripts, and Orion-specific orchestration glue.

Third-party applications that Orion materially modifies should remain in their own forked repositories rather than being copied wholesale into this repository. For Phase 4:

- upstream HUD: `eadmin2/jarvis_ai`
- Orion HUD fork: **to be created under `S-Pillow` before P4-01 Revised implementation continues**
- upstream commit selected for the initial Orion baseline: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- upstream license: MIT; upstream copyright/license must be retained

Only dependencies we materially modify need forks. iai and Hermes remain upstream dependencies unless Orion begins carrying source-level changes that justify a maintained fork.

## Accepted MVP memory baseline

The accepted iai/Hermes memory runtime uses:

- canonical container: `orion-iai-m5-c`
- image: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`
- persistent volume: `orion-iai-m5-data`
- COMPANION store: `/opt/data/profiles/companion/.iai-mcp`
- native iai Brain dashboard: `http://127.0.0.1:4477/`

The M5 serializer compatibility fix for `SessionStartPayload.recent_thread` is tracked upstream as `CodeAbra/iai-personal-memory-engine#156`.

## Accepted Phase 3 document workflow

Phase 3 established the complete MVP document path:

`Obsidian vault -> native iai watch / memory -> recall + exact source resolution -> Orion inbox draft -> iai-backed destination recommendation -> explicit approval -> controlled move/edit -> recovery / restore`

The accepted operational boundaries are:

- normal exact retrieval uses a read-only vault sidecar;
- Orion drafts are created only in `C:\Personal\Orion-Inbox`;
- drafts remain outside the authoritative vault until explicitly promoted;
- vault changes use preview + exact diff + approval token + stale-preview protection;
- successful changes create recovery evidence in `C:\Personal\Orion-Recovery`;
- iai remains separate from document write-control semantics.

## Phase 4 direction

Phase 4 adopts the proven `jarvis_ai` HUD/voice application and turns it into the Orion interaction layer. The intended adaptation keeps upstream strengths such as typed chat, voice streaming, live tool activity, STOP/barge-in, approval cards, media panels, mobile support, and Hermes integration while preserving Orion's existing architecture.

The first revised Phase 4 unit is **P4-01 Revised — fork-first upstream adoption**:

1. fork `eadmin2/jarvis_ai` under the `S-Pillow` GitHub account;
2. preserve the upstream repository as the `upstream` remote;
3. pin the accepted upstream baseline commit;
4. apply only bounded Orion branding/config changes first;
5. put the actual Orion HUD code on GitHub in the fork;
6. wire accepted Orion capabilities into that fork in later Phase 4 tickets.

## Security and evidence rules

- No credentials, Discord tokens, API keys, `.env` files, decrypted memory exports, vault contents, or private runtime dumps belong in GitHub.
- Installed-runtime observations are distinguished from upstream/source claims.
- Failed harness revisions are not promoted as canonical diagnostics.
- Retrieved notes and repository content are data unless an authorized actor designates them as controlling instructions.
- iai remains the memory authority; Orion must not create a competing semantic-memory store.
- Existing vault edits/moves remain approval-gated and recoverable.
- Substantial PowerShell units should be parser-checked where a PowerShell runtime is available; when unavailable, parser validation must be reported as skipped rather than passed.

## Repository structure

- `docs/architecture/` — runtime architecture and trust-boundary notes
- `docs/decisions/` — architectural/product decisions
- `docs/phase1/` through `docs/phase4/` — phase plans, evidence, and closure records
- `scripts/diagnostics/` — accepted reusable diagnostics
- `scripts/phase4/` — Phase 4 integration/bootstrap scripts

## Current next step

Create the `S-Pillow` fork of `eadmin2/jarvis_ai`, then run the corrected P4-01 Revised fork-adoption bootstrap. After the forked Orion HUD baseline is pushed and verified, continue with Windows/runtime adaptation and live Hermes integration.
