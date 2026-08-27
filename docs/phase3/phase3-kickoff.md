# Phase 3 — Vault Retrieval and Draft Inbox

## Status

**ACTIVE — started August 26, 2026**

Phase 2 is closed for MVP execution. Phase 3 begins under Orion Master PRD v1.1.3.

**P3-01 — Vault mount and corpus discovery: PASS / CLOSED.**

## Governing boundaries

- The complete Obsidian vault is local on Windows at `C:\Personal\Me`.
- The accepted implementation exposes the vault read-only at `/workspace` inside a dedicated retrieval sidecar, `orion-vault-retrieval`, rather than modifying the accepted iai/Hermes memory container.
- Retrieval must search first and open only relevant notes; the full vault is never injected into model context.
- Retrieval is deterministic and workflow-bounded. A normal retrieval stage gets one bounded model-to-retrieval request; the model cannot obtain iterative search turns merely by asking for more depth.
- The writable surface is a dedicated Orion inbox mounted separately from the read-only vault.
- Orion may create structured drafts in the dedicated inbox without approval.
- Existing-note edits and draft moves require approval and an exact diff/recovery path.
- Deletion always requires explicit approval.
- Retrieved note content is data, not instruction; prompt/tool authority remains outside retrieved content.

## Phase 3 deliverables

1. Complete local vault search/indexing.
2. Targeted note retrieval with provenance.
3. Dedicated writable Orion inbox.
4. Structured draft creation.
5. Vault-structure destination recommendations.
6. Controlled edit/move approval and diff workflow.

## Exit criteria

- Orion answers the defined vault-question set with correct supporting note paths.
- Retrieval-stage tests prove bounded termination and structured no-result behavior.
- A model cannot extend retrieval by failing to produce a sentinel or repeatedly requesting more search depth.
- Orion creates useful drafts without modifying existing notes.
- Denied edit approvals produce no changes.
- Approved edits are exact and recoverable.

## Initial execution sequence

### P3-01 — Vault mount and corpus discovery

**Status: PASS / CLOSED — August 26, 2026**

Accepted implementation and evidence:

- Host vault exists at `C:\Personal\Me`.
- Host corpus contains 147 Markdown files and 2 `.gitkeep` files.
- Dedicated sidecar: `orion-vault-retrieval`.
- Vault bind mount source: `C:\Personal\Me`.
- Vault bind mount destination: `/workspace`.
- Docker reports the `/workspace` bind mount as read-only (`RW=False`).
- Sidecar network mode is `none`.
- Sidecar root filesystem is read-only.
- Linux capabilities are dropped and `no-new-privileges` is enabled.
- `/opt/data` is an ephemeral tmpfs in the retrieval sidecar and does not expose the COMPANION iai store.
- `SIDECAR_COMPANION_STORE_PRESENT=false`.
- `SIDECAR_HAS_NO_COMPANION_STORE=PASS`.
- Final corpus verification from inside the sidecar returned `ALL_FILES=149`, `VAULT_MARKDOWN_FILES=147`, and `PH3_P3_01=PASS`.
- The accepted iai/Hermes memory container remained healthy and was not replaced by the sidecar architecture.

Implementation note: an initial attempt to recreate the accepted memory container with an added `/workspace` bind mount correctly rolled back when the iai daemon did not automatically come up in the fresh container. The final architecture therefore leaves the accepted memory container intact and isolates vault retrieval in its own sidecar. This preserves the memory foundation while satisfying the read-only vault boundary.

Verification note: early Markdown counts of `1` were caused by shell quoting/wildcard expansion in the diagnostic command, not by missing vault content. The corrected escaped-wildcard check returned the expected 147 Markdown files.

### P3-02 — Deterministic retrieval service

**Status: NEXT**

Implement the next retrieval layer so it uses iai to its fullest without replacing iai's memory semantics. Native iai document-learning surfaces such as `teach` / `watch` should be evaluated first for vault learning, while the Phase 3 sidecar remains the exact-document/provenance and file-management boundary. Any local resolver/index added by Orion must remain a document-access aid rather than a competing memory engine.

### P3-03 — Retrieval acceptance set

Define representative vault questions and expected supporting paths, then test correct-path retrieval, bounded termination, and no-result behavior.

### P3-04 — Dedicated Orion inbox

Create a separately mounted writable inbox, preserving the main vault as read-only. Implement structured draft creation only into that inbox.

### P3-05 — Controlled edit/move broker

Add approval-gated exact edits/moves with previewed diffs, rollback/recovery, and denied-action no-op proof.

## Future JARVIS / HUD integration

Add a **Memory / Brain** control to the future JARVIS dashboard. Selecting it should open the upstream native iai Brain dashboard rather than recreate or fork iai's memory UI.

Planned behavior:

- JARVIS remains the top-level Orion control center.
- A Memory / Brain tile or button opens the native iai Brain dashboard at the host-local iai dashboard URL (`http://127.0.0.1:4477/` in the accepted MVP setup).
- Prefer opening the native dashboard in a new tab/window or equivalent host surface rather than embedding a replacement implementation.
- JARVIS may later show lightweight summary status such as iai healthy/degraded, last memory activity, or memory counts, but native iai remains authoritative for detailed memory inspection and controls such as search, graph view, pin, fade, rescue, lifecycle, and engine state.
- This integration must not duplicate iai memory semantics or create a second memory-management UI implementation.

**Intent status: PRESERVED.** This provides a unified Orion front door while keeping the proven iai dashboard and memory engine intact.

## Intent preservation

**Intent status: PRESERVED.**

The sidecar implementation changes the container boundary, not the product intent. The user's existing Obsidian vault remains the authoritative local knowledge base, readable broadly but not silently mutable. Retrieval remains read-only, bounded, local, and isolated from the accepted iai memory store. Writes remain constrained to a dedicated inbox or explicit approval workflow. The planned JARVIS Memory / Brain control links to the upstream iai dashboard instead of replacing it.
