# DC-02 Markdown-Only Native iai Ingestion Adapter

Date: 2026-10-27

## Purpose

DC-02 restores the authoritative Obsidian Markdown corpus to the canonical native iai store without reintroducing a broad watcher.

This is an operator-run maintenance adapter. The source vault is read-only. This PR is source/review only: no merge, deploy, real vault/store access, or full-vault bootstrap occurs here.

## Ownership boundary

Orion owns:

- fail-closed Markdown admission;
- one Windows-portable source-name grammar;
- immutable staging of new/changed Markdown;
- plan/checkpoint state;
- pending recovery journal and store ownership metadata;
- canonical store-root pinning and vault/store separation;
- one Orion transaction lock;
- semantic DB file identity at persisted/inter-run and transaction boundaries.

Pinned `iai-pme==3.3.0` owns:

- Markdown extraction and chunking;
- embeddings and deduplication;
- native `doc:` ownership and shared ownership;
- graph work and supersession/fade behavior;
- recall self-test;
- native Hippo store locking;
- native derived-index persistence;
- semantic-store persistence.

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

The transaction core is frozen around these invariants:

1. **Validated source names** — one canonical source-name grammar is applied before a path can enter planning, checkpoint state, recovery metadata, native tagging, or fade operations.
2. **Immutable staging** — iai studies private staged `.md` files, never mutable live-vault paths.
3. **Fixed metadata namespace** — state, pending, owner, and lock live under one canonical store root; there is no custom state-file path.
4. **Pinned canonical store root** — `--store-root` is canonicalized once at transaction entry and that path is used throughout the run.
5. **One Orion transaction lock** — one store-local lock serializes Orion metadata/journal/checkpoint work.
6. **Persisted semantic DB identity** — state, pending, and owner bind to the actual `brain.sqlite3` file identity between successful runs and at checked transaction boundaries.
7. **Native EXCLUSIVE maintenance semantics** — semantic mutation opens iai with `AccessMode.EXCLUSIVE` and `persist_index=True`.
8. **Explicit pending-journal state machine** — recovery is absent, active, or completed according to checkpoint identity plus file-map digest.

## Source admission

An admitted source must be:

- a contained `.md` regular file;
- not a symlink/junction/reparse point;
- not a multi-link/hardlinked file;
- strict UTF-8;
- within configured file/count bounds;
- representable under the Windows vault naming rules.

The source-name grammar rejects, among other forms:

- literal backslashes;
- absolute/noncanonical paths and `.`/`..` components;
- Windows-forbidden characters and control characters;
- trailing spaces/periods in components;
- reserved Windows device stems;
- invalid Unicode/surrogate identity;
- case-fold path collisions in one admitted inventory.

POSIX source opens use `O_NONBLOCK` where available so FIFO/socket/device entries named `*.md` cannot hang before opened-handle regular-file validation. Recursive enumeration errors fail closed.

Planning is SHA-256 based; mtime-only changes do not trigger semantic restudy.

## Immutable staging

For every new/changed source Orion reopens it through the same admission boundary and requires bytes, size, mtime, relative name, and digest to match the admitted snapshot. Exact bytes are copied to a private fsynced staged `.md` outside both the vault and canonical store, original mtime is preserved, and staged size/mtime/digest are reverified.

All staging completes before pending recovery is written and before native `MemoryStore` opens.

Pinned iai receives the staged path, original vault-relative `source_name`, `session_id="vault-study"`, and `critic=None`. Deleted paths use native `study_document(text="", source_name=...)` semantics.

Once staging succeeds, that frozen snapshot defines the in-flight semantic transaction. A later live-vault edit belongs to the next run.

## Native report acceptance

For exact pinned `study_document`, checkpoint commit requires:

- zero skipped chunks;
- zero character/chunk truncation;
- non-negative integer counters;
- `inserted + reinforced + skipped == chunks_total`;
- `recall_tested == min(5, inserted + reinforced)`;
- `recall_verified == recall_tested`.

Whitespace-only, zero-byte, and sub-floor Markdown remain native iai semantics.

Pinned iai `_doc_tag()` is the ownership authority. Current, historical, and active-pending ownership collisions fail closed.

## Canonical store and metadata

Fixed paths:

- state: `<canonical-store>/orion/vault-markdown-ingest-state.json`
- pending: `<canonical-store>/orion/vault-markdown-ingest-pending.json`
- owner: `<canonical-store>/orion/vault-markdown-ingest-owner.json`
- Orion lock: `<canonical-store>/orion/vault-markdown-ingest.apply.lock`
- semantic DB: `<canonical-store>/hippo/brain.sqlite3`

Current schemas remain:

- state v4;
- pending v4;
- owner v3.

Vault and store roots must be disjoint in both directions. `<store>/hippo` must be a real non-reparse directory. Existing metadata, lock, and semantic DB files must be regular non-reparse single-link files.

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

`persist_index=True` is intentional. In pinned iai 3.3.0, non-owning SHARED/read-only clients use `persist_index=False` so their stale in-memory index cannot overwrite the owner's on-disk index. The EXCLUSIVE DC-02 maintenance store is the index-owning writer, so clean close must persist native derived recall state along with the semantic mutation.

Out of scope by design:

- a rogue process that bypasses iai/Hippo locking and overwrites store files;
- rename/unlink/replace of an open SQLite DB underneath the native connection;
- a filesystem with broken advisory-lock behavior.

SQLite documents these conditions as unsafe/undefined and cannot defend against a rogue external writer. Orion therefore does not claim an impossible instruction-by-instruction physical-file guarantee around an opaque vendor connection.

## Semantic DB file identity

DC-02 persists:

- canonical resolved DB path;
- `st_dev`;
- `st_ino` / Windows file index where available.

Identity is captured from an opened regular single-link DB handle and used to detect replacement/restoration between successful runs and at transaction boundaries. It is checked after Orion lock acquisition, immediately before native open, after clean native close, and before successful checkpoint write (including no-op apply).

Normal in-place native writes retain identity. Replacing the DB between runs invalidates prior state/owner/pending metadata rather than letting another file inherit source completion.

DC-02 deliberately does **not** perform a while-open writer-descriptor proof. The removed `/proc/self/fd` + `PRAGMA database_list` heuristic could be satisfied by an unrelated descriptor and overstated what the supported Python/iai APIs can prove.

## Serialization layers

### Orion transaction lock

One store-local advisory lock serializes Orion source inventory, staging, journal creation, semantic apply coordination, checkpoint commit, and cleanup.

- POSIX: nonblocking `flock`;
- Windows: nonblocking one-byte `msvcrt.locking`.

Plan-only does not create/acquire the lock.

### Native iai store lock

Semantic mutation uses `AccessMode.EXCLUSIVE`. This is the supported store-level exclusion mechanism for compliant iai clients. Orion does not replace it with a second inferred native lock or process-wide descriptor scan.

## Pending-journal state machine

Before any mutating native store open, Orion durably writes pending recovery containing runtime/vault/store identity, DB file identity, base and fresh target checkpoint IDs, base/target file-map digests, and affected source names with native ownership tags.

- **absent** — no pending journal;
- **active** — successful state matches pending base checkpoint and base file-map digest;
- **completed** — successful state matches pending target checkpoint and target file-map digest;
- anything else fails closed.

Active recovery forces every possibly-mutated path through reconciliation even if source bytes later revert. Pending-only tags are retained for newly studied sources that disappear before retry. Base and target checkpoint IDs remain distinct even when base and target file maps are equal.

Completed recovery clears before any new checkpoint rewrite or semantic cycle and never replays semantic work.

## Apply ordering

For a mutating transaction:

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
15. open native EXCLUSIVE, index-owning `MemoryStore`;
16. apply native studies/fades;
17. require clean native close;
18. revalidate topology + DB identity;
19. recheck DB identity before checkpoint write;
20. atomically commit state with target checkpoint ID;
21. claim owner after state for first no-op apply if needed;
22. clear pending;
23. clean staging and release Orion lock.

Failure before target checkpoint commit leaves pending active. Failure after target checkpoint commit but before pending deletion yields completed recovery and cleanup without replay.

## Research basis

The corrected boundary follows the storage layers' own supported contracts:

- SQLite, **How To Corrupt An SQLite Database File**: external overwrite cannot be defended against; unlink/rename of an open DB is unsafe/undefined: <https://www.sqlite.org/howtocorrupt.html>.
- SQLite locking documentation: EXCLUSIVE locking is the mechanism for preventing other compliant processes from accessing the DB: <https://www.sqlite.org/pragma.html#pragma_locking_mode>.
- pinned iai 3.3.0: `MemoryStore` defaults to `AccessMode.EXCLUSIVE` and `persist_index=True`; Hippo owns its native store lock.
- pinned iai 3.3.0: its `persist_index=False` call sites are non-owning SHARED/read-only clients, and its tests state that normal store close persists the healthy in-memory index.
- pinned iai maintenance CLI: mutating maintenance refuses a running daemon and instructs the operator to stop it first.

Upstream iai also snapshots the whole `hippo` directory for several destructive migrations/maintenance operations. That is useful precedent for a separately authorized backup strategy, but DC-02 does not replace the existing pending-journal reconciliation protocol with snapshot rollback in this ticket.

## Source acceptance

Before source/review closure:

- DC-02 invariant tests pass on Ubuntu and Windows;
- all broader source suites remain green;
- the runtime regression proves EXCLUSIVE + index-owning native open;
- store-open failure leaves active recovery;
- prior admission/staging/recovery/topology/DB-identity regressions remain green;
- unsupported live writer-descriptor probing remains absent;
- a fresh independent review evaluates the final frozen exact head against this maintenance contract.

The first real full-vault bootstrap remains separately authorized, is **MODERATE memory**, keeps the vault read-only, and requires the normal iai daemon/Hermes writer stopped for the maintenance window.
