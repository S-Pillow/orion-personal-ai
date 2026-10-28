# DC-02 Markdown-Only Native iai Ingestion Adapter

Date: 2026-10-27

## Purpose

DC-02 restores the authoritative Obsidian Markdown corpus to the canonical native iai store without reintroducing a broad watcher.

This is an operator-run maintenance adapter. The source vault is read-only. This PR is source/review only: no merge, deploy, real vault/store access, or full-vault bootstrap occurs here.

## Ownership boundary

Orion owns source admission, immutable staging, plan/checkpoint state, pending recovery, store ownership metadata, canonical store-root pinning, vault/store separation, one Orion transaction lock, and semantic DB file identity at persisted/inter-run and checked transaction boundaries.

Pinned `iai-pme==3.3.0` owns Markdown extraction/chunking, embeddings, deduplication, native `doc:` ownership, graph work, shared ownership, supersession/fade behavior, recall self-test, native Hippo locking, native derived-index persistence, and semantic-store persistence.

Orion does not implement a second semantic engine and does not infer the OS descriptor of iai's private writer connection.

## Supported entry point

The only supported transaction entry point is:

`scripts/dc02/orion_vault_markdown_ingest.py`

Implementation modules:

- `orion_vault_ingest_model.py` — immutable model, schemas, portable source-name grammar;
- `orion_vault_ingest_fs.py` — admission, staging, durable metadata writes, Orion lock;
- `orion_vault_ingest_state.py` — checkpoint/planning/pending state machine;
- `orion_vault_ingest_runtime.py` — pinned iai runtime and native report acceptance;
- `orion_vault_ingest_contract.py` — store topology, vault separation, DB file identity, persisted-state contract;
- `orion_vault_markdown_ingest_core.py` — import-only re-export surface; direct execution fails closed.

There is no second apply CLI and no executable legacy sidecar.

## Frozen transaction invariants

1. **Validated source names** — one canonical source-name grammar before planning, state, recovery, native tagging, or fades.
2. **Immutable staging** — iai studies private staged Markdown, never mutable live-vault paths.
3. **Fixed metadata namespace** — state, pending, owner, and lock live under one canonical store root.
4. **Pinned canonical store root** — `--store-root` is canonicalized once and reused for the whole transaction.
5. **One Orion transaction lock** — one store-local lock serializes Orion metadata/journal/checkpoint work.
6. **Persisted semantic DB identity** — state, pending, and owner bind to `brain.sqlite3` file identity between successful runs and at checked transaction boundaries.
7. **Native EXCLUSIVE maintenance semantics** — semantic mutation opens iai with `AccessMode.EXCLUSIVE` and `persist_index=True`.
8. **Explicit pending-journal state machine** — recovery is absent, active, or completed according to checkpoint identity plus file-map digest.

## Source admission and staging

Admitted Markdown must be contained, regular, single-link, non-reparse, strict UTF-8, within configured size/count bounds, and representable under Windows vault naming rules. Admission rejects literal backslashes, noncanonical paths, Windows-forbidden/control characters, trailing dot/space, reserved device stems, invalid Unicode identity, and case-fold collisions.

POSIX source opens use `O_NONBLOCK` where available so FIFO/socket/device entries named `*.md` cannot hang before opened-handle regular-file validation. Recursive enumeration errors fail closed.

Planning is SHA-256 based; mtime-only changes do not trigger semantic restudy.

For every new/changed source Orion reopens it through the same admission boundary, verifies it still matches the admitted snapshot, and copies exact bytes to a private fsynced staged `.md` outside both vault and store. Original mtime is preserved and staged size/mtime/digest are reverified.

All staging completes before pending recovery is written and before native `MemoryStore` opens. Pinned iai receives the staged path, original vault-relative `source_name`, `session_id="vault-study"`, and `critic=None`. Deleted paths use native `study_document(text="", source_name=...)` semantics.

Once staging succeeds, the frozen snapshot defines the in-flight transaction; later live-vault edits belong to the next run.

## Native report acceptance

For exact pinned `study_document`, successful checkpoint commit requires zero skipped chunks, zero character/chunk truncation, non-negative integer counters, `inserted + reinforced + skipped == chunks_total`, `recall_tested == min(5, inserted + reinforced)`, and `recall_verified == recall_tested`.

Whitespace-only, zero-byte, and sub-floor Markdown remain native iai semantics. Pinned `_doc_tag()` remains the ownership authority; current, historical, and active-pending collisions fail closed.

## Canonical store and metadata

Fixed paths:

- state: `<canonical-store>/orion/vault-markdown-ingest-state.json`
- pending: `<canonical-store>/orion/vault-markdown-ingest-pending.json`
- owner: `<canonical-store>/orion/vault-markdown-ingest-owner.json`
- Orion lock: `<canonical-store>/orion/vault-markdown-ingest.apply.lock`
- semantic DB: `<canonical-store>/hippo/brain.sqlite3`

Schemas remain state v4 / pending v4 / owner v3.

Vault and store roots must be disjoint in both directions. `<store>/hippo` must be a real non-reparse directory. Existing metadata, lock, and semantic DB files must be regular non-reparse single-link files.

The pinned runtime also guards iai's environment precedence: pinned iai 3.3.0's lower-level Hippo resolver gives `IAI_MCP_STORE` precedence over an explicit path. Therefore, if `IAI_MCP_STORE` is present at native open, it must canonicalize to the already-pinned Orion store root. A conflicting value fails before `MemoryStore` construction so Orion metadata/locking cannot target one store while Hippo opens another.

## Maintenance threat model

Mutating `--apply` is supported only during a quiescent maintenance window.

Required operator conditions:

- stop the normal iai daemon/Hermes writer before apply;
- do not run another maintenance command against the same store concurrently;
- do not rename, unlink, replace, restore, hardlink, synchronize, or externally overwrite live semantic-store files while apply is running;
- use a filesystem with functioning normal local lock semantics.

For semantic mutation DC-02 opens:

`MemoryStore(..., access_mode=AccessMode.EXCLUSIVE, persist_index=True)`

The native Hippo EXCLUSIVE lock is the authority for excluding other compliant iai clients. If another compliant client still owns the store, native open fails and the pending journal remains active for retry.

`persist_index=True` is intentional. In pinned iai 3.3.0, `persist_index=False` is used by non-owning SHARED/read-only clients so a stale in-memory index cannot overwrite the owner's on-disk derived index. DC-02's EXCLUSIVE maintenance store is the index-owning writer, so clean close persists native derived recall state.

Out of scope by design:

- a rogue process that bypasses iai/Hippo locking and overwrites store files;
- rename/unlink/replace of an open DB underneath the native connection;
- a filesystem with broken advisory-lock behavior.

SQLite documents these conditions as unsafe/undefined and cannot defend against a rogue external writer. Orion therefore does not claim an impossible instruction-by-instruction physical-file guarantee around an opaque vendor connection.

## Semantic DB file identity

DC-02 persists canonical resolved DB path, `st_dev`, and `st_ino` / Windows file index where available.

Identity is captured from an opened regular single-link DB handle and detects replacement/restoration between successful runs and at transaction boundaries. It is checked after Orion lock acquisition, immediately before native open, after clean native close, and before successful checkpoint write, including no-op apply.

Normal in-place native writes retain identity. Replacing the DB between runs invalidates prior state/owner/pending metadata rather than letting another file inherit source completion.

DC-02 deliberately performs no while-open writer-descriptor proof. The removed `/proc/self/fd` + `PRAGMA database_list` heuristic could be satisfied by an unrelated descriptor and overstated what the supported Python/iai APIs can prove.

## Serialization layers

The Orion advisory lock serializes Orion source inventory, staging, journal creation, semantic apply coordination, checkpoint commit, and cleanup. POSIX uses nonblocking `flock`; Windows uses nonblocking one-byte `msvcrt.locking`. Plan-only does not acquire it.

Semantic mutation separately uses native iai `AccessMode.EXCLUSIVE`, the supported store-level exclusion mechanism for compliant iai clients. Orion does not replace it with an inferred native lock or process-wide descriptor scan.

## Pending-journal state machine

Before any mutating native open, Orion durably writes pending recovery containing runtime/vault/store identity, DB file identity, base and fresh target checkpoint IDs, base/target file-map digests, and affected source names with native ownership tags.

- **absent** — no pending journal;
- **active** — successful state matches pending base checkpoint and base digest;
- **completed** — successful state matches pending target checkpoint and target digest;
- anything else fails closed.

Active recovery forces every possibly-mutated path through reconciliation even if source bytes later revert. Pending-only tags are retained for newly studied sources that disappear before retry. Base and target checkpoint IDs remain distinct even when file maps are equal.

Completed recovery clears before any new checkpoint rewrite or semantic cycle and never replays semantic work.

## Apply ordering

1. pin canonical store root;
2. validate vault/store separation and topology;
3. acquire Orion transaction lock;
4. capture/validate semantic DB identity;
5. load state/owner;
6. admit source inventory and native tags;
7. classify pending recovery;
8. clear completed recovery;
9. build/reconcile plan;
10. stage all new/changed sources immutably;
11. recheck planned deletion absence;
12. write pending recovery durably;
13. claim owner if needed;
14. revalidate topology + DB identity;
15. verify `IAI_MCP_STORE`, if set, resolves to the pinned root;
16. open native EXCLUSIVE, index-owning `MemoryStore`;
17. apply native studies/fades;
18. require clean native close;
19. revalidate topology + DB identity;
20. recheck DB identity before checkpoint write;
21. atomically commit state with target checkpoint ID;
22. claim owner after state for first no-op apply if needed;
23. clear pending;
24. clean staging and release Orion lock.

Failure before target checkpoint commit leaves pending active. Failure after target checkpoint commit but before pending deletion yields completed recovery and cleanup without replay.

## Research basis

The corrected boundary follows the storage layers' supported contracts:

- SQLite, **How To Corrupt An SQLite Database File**: external overwrite cannot be defended against; unlink/rename of an open DB is unsafe/undefined: <https://www.sqlite.org/howtocorrupt.html>.
- SQLite locking documentation: EXCLUSIVE locking is the mechanism for preventing other compliant processes from accessing the DB: <https://www.sqlite.org/pragma.html#pragma_locking_mode>.
- pinned iai 3.3.0: `MemoryStore` defaults to `AccessMode.EXCLUSIVE` and `persist_index=True`; Hippo owns its native store lock.
- pinned iai 3.3.0: non-owning SHARED/read-only call sites use `persist_index=False`, and native tests state that normal store close persists the healthy in-memory index.
- pinned iai 3.3.0: Hippo's lower-level `_resolve_root()` gives `IAI_MCP_STORE` precedence over an explicit path, which is why DC-02 validates that environment binding before construction.
- pinned iai maintenance CLI: mutating maintenance refuses a running daemon and instructs the operator to stop it first.

Upstream iai also snapshots the whole `hippo` directory for several destructive migrations/maintenance operations. That is useful precedent for a separately authorized backup strategy, but DC-02 does not replace the existing pending-journal reconciliation protocol with snapshot rollback in this ticket.

Native HNSW/derived-index persistence remains vendor-owned. iai's boot-integrity path rebuilds a stale derived index from the semantic DB; DC-02 does not add a second recovery journal for derived index files.

## Source acceptance

Before source/review closure:

- DC-02 invariant tests pass on Ubuntu and Windows;
- broader source suites remain green;
- runtime regression proves EXCLUSIVE + index-owning native open;
- conflicting `IAI_MCP_STORE` fails before native construction;
- store-open failure leaves active recovery;
- prior admission/staging/recovery/topology/DB-identity regressions remain green;
- unsupported live writer-descriptor probing remains absent;
- a fresh independent review evaluates the final frozen exact head against this maintenance contract.

The first real full-vault bootstrap remains separately authorized, is **MODERATE memory**, keeps the vault read-only, and requires the normal iai daemon/Hermes writer stopped for the maintenance window.
