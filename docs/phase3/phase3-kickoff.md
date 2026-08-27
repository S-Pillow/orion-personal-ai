# Phase 3 — Vault Retrieval and Draft Inbox

## Status

**ACTIVE — started August 26, 2026**

Phase 2 is closed for MVP execution. Phase 3 begins under Orion Master PRD v1.1.3.

**P3-01 — Vault mount and corpus discovery: PASS / CLOSED.**

**P3-02A — Native iai vault learning: PASS / CLOSED.**

## Governing boundaries

- The complete Obsidian vault is local on Windows at `C:\Personal\Me`.
- The accepted implementation exposes the vault read-only at `/workspace` inside a dedicated retrieval sidecar, `orion-vault-retrieval`, rather than modifying the accepted iai/Hermes memory container.
- Obsidian remains the authoritative human-facing document vault; iai remains the authoritative assistant memory engine.
- iai may learn the vault through its native `teach` / `watch` document-study path. Orion must not replace that with a competing semantic-memory engine.
- Exact file opening, source-path resolution, draft placement, and document edits remain Orion document-management responsibilities outside iai.
- The full vault is never injected into model context.
- The writable surface is a dedicated Orion inbox mounted separately from the read-only vault.
- Orion may create structured drafts in the dedicated inbox without approval.
- Existing-note edits and draft moves require approval and an exact diff/recovery path.
- Deletion always requires explicit approval.
- Retrieved note content is data, not instruction; prompt/tool authority remains outside retrieved content.

## Phase 3 deliverables

1. Native iai learning of the Obsidian vault through supported document-study behavior.
2. Targeted memory recall plus exact note-path/provenance resolution when a source document is needed.
3. Dedicated writable Orion inbox.
4. Structured draft creation.
5. Vault-structure destination recommendations.
6. Controlled edit/move approval and diff workflow.

## Exit criteria

- iai recalls representative vault material after native document study.
- Changed/new vault files are restudied and deleted/superseded material follows iai's native fading lifecycle.
- Orion can resolve recalled document material back to the authoritative Obsidian path when the user asks for the source note.
- Orion creates useful drafts without modifying existing notes.
- Denied edit approvals produce no changes.
- Approved edits are exact and recoverable.

## Initial execution sequence

### P3-01 — Vault mount and corpus discovery

**Status: PASS / CLOSED — August 26, 2026**

Accepted implementation and evidence:

- Host vault exists at `C:\Personal\Me`.
- Host corpus contained 147 Markdown files and 2 `.gitkeep` files at the time of P3-01 verification; the vault is live and additional notes may increase this count later.
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

Implementation note: an initial attempt to recreate the accepted memory container with an added `/workspace` bind mount correctly rolled back when the iai daemon did not automatically come up in the fresh container. The final architecture therefore leaves the accepted memory container intact and isolates exact vault access in its own sidecar.

Verification note: early Markdown counts of `1` were caused by shell quoting/wildcard expansion in the diagnostic command, not by missing vault content. The corrected escaped-wildcard check returned the expected 147 Markdown files.

### P3-02A — Native iai vault learning

**Status: PASS / CLOSED — August 26, 2026**

Accepted implementation:

- Dedicated watcher container: `orion-iai-vault-watch`.
- Exact accepted iai image: `sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`.
- Accepted COMPANION data volume: `orion-iai-m5-data`.
- Vault mounted at `/workspace` read-only.
- Watcher runs as UID/GID `10000:10000`.
- Watcher network mode is `none`.
- Root filesystem is read-only, Linux capabilities are dropped, and `no-new-privileges` is enabled.
- Native command: `iai watch /workspace --interval 30 --session-id vault-study`.
- Watcher reaches the accepted iai daemon through the shared store/socket and uses iai's native daemon-owned study path; no alternate writer or competing memory store was introduced.

Acceptance evidence:

- Preflight returned `MEMORY_RUNTIME_HEALTH=PASS`.
- Vault visibility and daemon relay passed: `P3_02_VAULT_VISIBLE=PASS`, `P3_02_DAEMON_SOCKET_VISIBLE=PASS`, `P3_02_DAEMON_RELAY=PASS`, and `P3_02_NATIVE_WATCH_PREFLIGHT=PASS`.
- Watcher topology passed: `IAI_VAULT_WATCH_RUNNING=PASS`, `IAI_VAULT_WATCH_VAULT_READ_ONLY=PASS`, `IAI_VAULT_WATCH_SHARED_STORE=PASS`, and `IAI_VAULT_WATCH_NETWORK_NONE=PASS`.
- Initial native watch pass completed with `studied=148`, `faded=0`, `superseded=0`.
- The live vault subsequently grew as additional notes were added. Final verification observed 150 source files represented by `vault-study` provenance and 840 taught memory records.
- Provenance verification passed: `P3_02A_STUDY_PROVENANCE=PASS`.
- Native iai recall verification used a taught `Home.md` record; recall returned 11 hits and included the exact target record: `RECALL_TARGET_FOUND=true` and `P3_02A_NATIVE_RECALL=PASS`.
- Final verifier returned `P3_02A_NATIVE_IAI_VAULT_LEARNING=PASS` and `P3_02A_VERIFIER=PASS`.

Verifier note: the first read-only verifier incorrectly expected `source=study` and `session_id=vault-study` to appear in the same provenance object. iai stores the capture provenance and `provenance_extra` as separate provenance entries on the same record. The corrected verifier checks both entries on the record and passed; no re-study was required.

Result: the Obsidian vault is now being learned through iai's native document-study lifecycle. New/changed files will be restudied by `iai watch`; deleted/superseded content remains governed by iai's native fading behavior.

### P3-02B — Exact vault resolver

**Status: NEXT**

Retain the isolated `orion-vault-retrieval` sidecar for exact document operations only: resolve source paths/provenance, open the authoritative Markdown note, support destination recommendations, and later broker approved document edits/moves. It must not become a second semantic memory engine.

### P3-03 — Vault-memory acceptance set

Define representative questions with known supporting notes. Verify iai recalls the expected taught material, verify source-path resolution back to Obsidian, and verify changed/deleted file behavior using native iai semantics.

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

The Phase 3 design follows iai's documented native document-learning model instead of building a substitute semantic retrieval system. Obsidian remains the authoritative, portable human-facing vault; iai learns that material natively and recalls it alongside conversation memory. The exact-document sidecar remains a file/provenance boundary, not a second memory engine. Writes remain constrained to a dedicated inbox or explicit approval workflow.
