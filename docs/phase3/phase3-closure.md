# Phase 3 — Vault Retrieval and Draft Inbox Closure

**Status: CLOSED / MVP ACCEPTED — August 27, 2026**

## Closure decision

Phase 3 is accepted for Orion MVP. The vault/document workflow is now complete enough to move forward without additional Phase 3 implementation or broad retesting.

## Accepted capabilities

- P3-01: isolated read-only authoritative vault access and corpus discovery.
- P3-02A: native iai `teach/watch` learning of the Obsidian vault.
- P3-02B: deterministic exact-source resolution from iai-taught memory back to the authoritative Markdown note.
- P3-03: representative vault-memory acceptance, including recall, change restudy, supersede behavior, and deleted-note fade handling under native iai semantics.
- P3-04: dedicated writable Orion inbox outside the authoritative vault, plus structured draft creation.
- P3-05: approval-gated draft promotion, exact note edits, denial no-op behavior, recovery backups, and exact restore.
- P3-06: vault-structure destination recommendations derived from native iai recall provenance and restricted to existing authoritative-vault directories.

## End-to-end MVP model

`Obsidian vault -> native iai watch/teach -> iai recall -> exact source resolution -> Orion inbox draft -> iai-backed destination recommendation -> preview/approval -> controlled vault move/edit -> recovery/restore`

The responsibilities remain intentionally separated:

- Obsidian is the authoritative human-facing document vault.
- iai is the authoritative assistant memory and semantic-recall engine.
- Orion exact-source tooling handles deterministic file resolution only.
- Orion inbox is the bounded unapproved writable draft surface.
- Orion vault broker is the only controlled write path into the authoritative vault.
- Destination recommendation is advisory and cannot itself modify the vault.

## Exit criteria disposition

- Representative iai recall after native document study: **PASS**.
- Changed/new/deleted vault lifecycle under native iai semantics: **PASS**.
- Recall-to-authoritative-source resolution: **PASS**.
- Draft creation without modifying existing notes: **PASS**.
- Vault-structure destination recommendation: **PASS**.
- Denied edit/move approval produces no change: **PASS**.
- Approved edits/moves are exact and recoverable: **PASS**.

## MVP operational components to retain

- `Orion-Phase3-P3-02B-Exact-Vault-Resolver.ps1`
- `Orion-Phase3-P3-04-Create-Inbox-Draft.ps1`
- `Orion-Phase3-P3-05-Controlled-Vault-Broker-v2.ps1`
- `Orion-Phase3-P3-06-Vault-Destination-Recommender.ps1`

Accepted runtime services/containers include the native iai memory runtime and dashboard, `orion-iai-vault-watch`, `orion-vault-retrieval`, `orion-inbox-writer`, and `orion-vault-broker`.

## Non-blocking future work

Phase 3 closure does not require duplicating the native iai Brain UI, adding a second memory index, broad algorithm testing, or additional vault-write capability. Future JARVIS/HUD work should integrate around these accepted components, with the Memory / Brain control opening the native iai dashboard and higher-level Orion UX orchestrating the existing resolver, inbox, recommender, and approval broker.

**Intent status: PRESERVED.** The accepted architecture keeps iai canonical for memory, Obsidian canonical for human-authored documents, and Orion responsible for orchestration and controlled document actions without replacing either subsystem.