# Phase 3 — Vault Retrieval and Draft Inbox

## Status

**ACTIVE — started August 26, 2026**

Phase 2 is closed for MVP execution. Phase 3 begins under Orion Master PRD v1.1.3.

## Governing boundaries

- The complete Obsidian vault is local on Windows at `C:\Personal\Me`.
- The vault is exposed to Orion/Hermes at `/workspace` as a read-only mount.
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

Read-only inspection only. Confirm the `/workspace` mount, read-only enforcement, corpus size/shape, and available local indexing/search primitives. Identify whether a dedicated writable inbox mount already exists. Do not read note bodies beyond what is required for later controlled retrieval tests and do not write to the vault.

### P3-02 — Deterministic retrieval service

Implement a bounded local retrieval service with fixed query/result/fetch budgets, provenance-preserving structured output, and a guaranteed no-result return path. No model-driven iterative retrieval loop.

### P3-03 — Retrieval acceptance set

Define representative vault questions and expected supporting paths, then test correct-path retrieval, bounded termination, and no-result behavior.

### P3-04 — Dedicated Orion inbox

Create a separately mounted writable inbox, preserving the main vault as read-only. Implement structured draft creation only into that inbox.

### P3-05 — Controlled edit/move broker

Add approval-gated exact edits/moves with previewed diffs, rollback/recovery, and denied-action no-op proof.

## Intent preservation

**Intent status: PRESERVED.**

The Phase 3 design preserves Orion's reason for using an Obsidian vault: the user's existing notes remain the authoritative local knowledge base, readable broadly but not silently mutable. Retrieval is bounded to protect local-model reliability, while writes are constrained to a dedicated inbox or explicit approval workflow.
