# DC-02 Markdown-Only Native iai Ingestion Adapter

Date: 2026-10-27

## Purpose

DC-02 restores the authoritative Obsidian Markdown corpus to the canonical native iai store without reintroducing a broad directory watcher.

The implementation boundary is intentionally narrow:

- Orion owns source admission, immutable transaction snapshots, synchronization state, recovery metadata, store ownership, semantic-store identity, and apply serialization.
- pinned `iai-pme==3.3.0` owns Markdown extraction, chunking, embeddings, deduplication, native `doc:` tags, graph weaving, shared document ownership, supersession/fade behavior, recall self-test, and persistence.
- the source vault is read-only.
- the adapter is operator-run only.
- this PR is source/review work only; it does not merge, deploy, touch the real vault/store, or run bootstrap.

## Supported entry point

The only supported transaction entry point is:

`scripts/dc02/orion_vault_markdown_ingest.py`

Implementation is split by invariant:

- `orion_vault_ingest_model.py` — immutable data model, schema versions, and one Windows-portable source-name grammar.
- `orion_vault_ingest_fs.py` — fail-closed filesystem admission, crash-durable metadata writes, immutable staging, and the one advisory lock primitive.
- `orion_vault_ingest_state.py` — checkpoint, owner, planning, and pending-journal state machine primitives.
- `orion_vault_ingest_runtime.py` — pinned iai 3.3.0 runtime loading, live native-store DB verification, native report acceptance, CLI arguments, and result envelopes.
- `orion_vault_ingest_contract.py` — cross-module invariants: vault/store separation, semantic-store topology, semantic DB file identity, and persisted checkpoint validity.
- `orion_vault_markdown_ingest_core.py` — import-only compatibility/re-export surface. Direct execution fails closed.

There is no executable legacy sidecar and no secondary apply CLI.

## Rebuilt transaction invariants

The earlier live-path prototype was replaced rather than patched further. The rebuilt transaction is organized around these invariants:

1. **Validated source names** — a source name is admitted once through one canonical grammar before it may enter planning, state, pending recovery, vendor tagging, or fade operations.
2. **Immutable staging** — iai studies private staged `.md` files, never the mutable live vault path.
3. **Fixed metadata namespace** — state, pending, owner, and lock have fixed locations under the canonical store root; there is no custom `--state-file`.
4. **One pinned store root and one Orion apply lock** — the supplied store root is canonicalized once at transaction entry and that immutable path is used throughout the run.
5. **One physical semantic DB identity** — state, pending recovery, owner metadata, and the live native store are bound to the actual `brain.sqlite3` file instance, not just its pathname.
6. **Explicit pending-journal state machine** — recovery is absent, active, or completed according to checkpoint identity plus file-map digest.

The objective is to remove whole bug classes rather than accumulate edge-case guards around a mutable live-path transaction.

## Source-name contract

Every admitted Markdown source gets one canonical vault-relative POSIX `source_name` that is also representable on the Windows vault host.

Admission rejects, among other invalid forms:

- empty, absolute, noncanonical, `.` or `..` paths;
- literal backslashes;
- non-Markdown suffixes;
- Windows-forbidden characters `< > : " \\ | ? *`;
- ASCII control characters;
- path components ending in a space or period;
- Windows reserved device stems such as `CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, and `LPT1`-`LPT9`, including Windows-recognized superscript forms;
- non-strict-UTF-8/surrogate source identity;
- full source-path case-fold collisions in one admitted inventory.

The same source-name validator is reused by checkpoint, pending recovery, native tag ownership, and fade paths. Generated state/pending metadata revalidates snapshot size, mtime, SHA-256, source name, and tag before serialization.

## Filesystem admission

An admitted source must be:

- recursively contained below the resolved vault root;
- `.md` case-insensitively;
- a regular file;
- not a symlink/junction/reparse point;
- not a multi-link/hardlinked source;
- strict UTF-8;
- no larger than 2,000,000 bytes by default.

The corpus defaults to a 5,000-file limit.

Reads use one opened lexical vault pathname. POSIX adds `O_NONBLOCK` so a FIFO/socket/device named `*.md` cannot hang before the opened-handle regular-file check. Where available, `O_NOFOLLOW` protects the final component. File type, link count, size, device/inode identity, mtime, final byte count, and pathname identity are checked around the read. Recursive enumeration errors and directory reparse/containment violations fail closed.

## Immutable staging

Planning is by SHA-256; mtime-only touches do not trigger semantic restudy.

For every new or content-changed note:

1. Orion reopens the live source through the same strict admission boundary.
2. Bytes, size, mtime, relative name, and SHA-256 must still match the admitted snapshot.
3. The configured temp root must be outside both the vault and canonical store.
4. Exact admitted bytes are written to a private staged `.md` file and fsynced.
5. The staged file receives the source mtime and is reverified by size, mtime, and SHA-256.

All required staging completes before pending recovery is written and before native `MemoryStore` opens.

Pinned iai receives:

- the immutable staged `path=` for new/changed notes;
- the original vault-relative `source_name`;
- `session_id="vault-study"`;
- `critic=None`.

For deleted sources, Orion uses native `study_document(text="", source_name=...)` semantics.

Once staging succeeds, the frozen snapshot defines the in-flight semantic transaction. A later edit to the live vault is intentionally handled by the next run rather than invalidating semantic work already applied from the staged snapshot.

## Native iai 3.3.0 contract

Orion does not implement a parallel semantic engine. iai 3.3.0 remains authoritative for extraction, chunking, embeddings, dedup, shared document ownership, native tags, supersession, graph work, recall self-test, and persistence.

Whitespace-only, zero-byte, and sub-capture-floor Markdown remain native iai behavior.

For the exact native `iai_mcp.study.study_document` primitive, successful checkpoint commit requires:

- zero skipped chunks;
- zero character truncation;
- zero chunk truncation;
- real non-negative integer counters;
- `inserted + reinforced + skipped == chunks_total`;
- `recall_tested == min(5, inserted + reinforced)`;
- `recall_verified == recall_tested`.

Pinned iai `_doc_tag()` remains the ownership authority. Current, historical, and active-pending ownership collisions fail closed.

## Canonical store, topology, and read-only vault separation

The supplied `--store-root` is canonicalized exactly once at transaction entry. That pinned `Path` is then used for metadata paths, ownership identity, staging boundaries, topology checks, lock acquisition, native store open, and checkpoint serialization. A lexical store-root symlink/junction cannot be retargeted mid-run to split the metadata/lock namespace from semantic work.

Vault and canonical store roots must be disjoint in both directions. A store inside the vault or a vault inside the store fails before metadata creation/lock acquisition. The resolved semantic DB is independently refused if it lies inside the vault.

The semantic store path is:

`<canonical-store>/hippo/brain.sqlite3`

`<canonical-store>/hippo` itself must be a real non-reparse directory. A redirected `hippo` symlink/junction/reparse point is rejected before `brain.sqlite3` is accepted. This prevents two apparent store roots from reaching one semantic DB while using different Orion locks and recovery journals.

The DB, lock, state, pending, and owner files must be regular non-reparse, single-link files when they exist.

## Semantic DB file identity and live-store binding

Pathname binding alone is insufficient: replacing/restoring `brain.sqlite3` while leaving Orion metadata in place must not allow the replacement DB to inherit an old checkpoint, and sampling only before native open/after native close is insufficient if the pathname is swapped during `MemoryStore` construction and restored during close.

DC-02 therefore persists a semantic DB file identity consisting of:

- canonical resolved DB path;
- filesystem device identifier (`st_dev`);
- filesystem file identifier (`st_ino`; on Python 3.12 Windows this is the file index when available).

The identity is captured through an opened regular single-link DB handle and verified against the current pathname. A missing/zero file identifier fails closed.

Successful state, pending recovery, and owner metadata all carry the identity. Apply captures it after acquiring the Orion lock and validates persisted metadata against it. The same identity is checked at four boundaries:

- immediately before native store open;
- **while the native `MemoryStore` is open and before the first study/fade call**;
- after a clean native store close;
- immediately before successful checkpoint write, including a no-op apply.

The while-open verifier uses the pinned iai 3.3.0 `MemoryStore.db` / `HippoDB` seam. It requires the live writer connection and bound `_db_path` to match the checkpoint-owned DB. For the stdlib driver it also queries `PRAGMA database_list` through that exact writer connection. On POSIX, Orion additionally confirms that the process has an open regular-file descriptor whose `(st_dev, st_ino)` matches the expected semantic DB while the native store is live. A mismatch closes the store and leaves pending recovery active before semantic study begins.

Replacing the DB therefore invalidates prior ownership/checkpoint metadata even when source files are unchanged. A replacement during native open cannot pass through to `study_document` merely because the original pathname is restored on close. Normal in-place DB writes retain file identity and do not invalidate the binding.

This source-only schema change has not been deployed, so no production DC-02 metadata requires migration.

## Fixed metadata namespace and schemas

There is no `--state-file` option.

DC-02 exclusively uses:

- state: `<canonical-store>/orion/vault-markdown-ingest-state.json`
- pending: `<canonical-store>/orion/vault-markdown-ingest-pending.json`
- owner: `<canonical-store>/orion/vault-markdown-ingest-owner.json`
- lock: `<canonical-store>/orion/vault-markdown-ingest.apply.lock`

Current schemas:

- successful state: **v4**;
- pending recovery: **v4**;
- store owner: **v3**.

Successful state records runtime identity, vault/store identity, semantic DB identity, successful UTC timestamp, checkpoint ID, and per-source snapshot/tag metadata.

A persisted state file must contain a non-null timezone-aware successful timestamp. `successful_run_utc: null` is valid only for the synthetic in-memory empty state before any checkpoint exists. Broken persisted aliases are treated as persisted and fail closed rather than being reinterpreted as “no state”.

Store owner binds one vault + canonical store + semantic DB file identity + `vault-study` session + iai 3.3.0.

## One Orion apply lock

Apply uses exactly one store-local advisory lock:

`<canonical-store>/orion/vault-markdown-ingest.apply.lock`

- POSIX: nonblocking `flock`;
- Windows: nonblocking one-byte `msvcrt.locking`.

The opened lock handle is verified as a regular single-link file before Windows can write its backing lock byte.

The lock covers metadata classification, source inventory, staging, journal creation, native work, checkpoint commit, and cleanup. Plan-only does not create or acquire it.

This lock serializes Orion adapter processes only. It does not exclude unrelated native iai `AccessMode.SHARED` clients. The first real bootstrap therefore requires the normal iai daemon/Hermes writer to be stopped for the maintenance window.

## Explicit pending-journal state machine

Before any mutating native store open, Orion writes a crash-durable metadata-only pending journal containing:

- vault/store/session/iai identity;
- semantic DB file identity;
- base checkpoint identity;
- fresh target checkpoint identity;
- SHA-256 of base and target file maps;
- affected source names and their native `doc:` tags.

No note body is stored in the journal.

### Absent

No pending file exists. Planning begins from the successful checkpoint.

### Active

The successful state's checkpoint identity equals the journal base identity and its file-map digest equals the journal base digest.

Every affected pending path is forced through reconciliation even if current source content has reverted to the successful checkpoint. Pending ownership tags remain available for newly studied sources that disappear before retry.

Base and target file maps may be identical. Base and target checkpoint IDs must remain distinct, so equal maps cannot falsely establish completion.

### Completed

The successful state's checkpoint identity equals the journal target identity and its file-map digest equals the journal target digest.

Completed recovery is cleared before any checkpoint rewrite or new semantic cycle. Semantic work is not replayed and obsolete pending ownership does not block a new source.

Any other identity/digest relationship fails closed.

## Apply ordering

For one apply transaction:

1. canonicalize and pin the store root;
2. validate vault/store separation and store topology;
3. acquire the one Orion store lock;
4. revalidate metadata/store topology and capture semantic DB file identity;
5. load/validate state and owner against that DB identity;
6. admit the current Markdown inventory and native document tags;
7. load/classify pending recovery against the same DB identity;
8. clear a completed journal before further apply work;
9. build/reconcile the plan;
10. freeze every new/changed source into immutable private staging;
11. recheck planned deletions are absent;
12. durably write pending recovery with the pinned DB identity;
13. claim store ownership if needed;
14. revalidate topology and DB file identity;
15. open native `MemoryStore`;
16. verify the **live native store/writer connection** is bound to the expected DB file instance;
17. study staged new files, staged changed files, then fade deleted sources;
18. require clean native store close;
19. revalidate topology and DB file identity;
20. revalidate DB identity again before checkpoint write, including no-op applies;
21. atomically commit state with the pending target checkpoint identity;
22. claim owner after state for a first no-mutation apply if needed;
23. clear pending recovery;
24. remove staged files and release the Orion lock.

POSIX metadata replacement fsyncs the destination directory. Newly created metadata directories are durably fsynced through their parent chain. Windows replacement uses `MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)`.

## Crash/retry behavior

- failure before pending creation: no semantic store mutation has occurred;
- failure after pending but before/during store open: pending remains active;
- failure in the while-open DB identity probe: native store is closed, no study/fade call is made, and pending remains active;
- failure after one or more study/fade calls: pending remains active and all affected paths are forced through reconciliation;
- failure after successful state commit but before pending deletion: pending is completed and a retry clears it without semantic replay;
- a newly studied source deleted before retry retains its pending `doc:` ownership tag and is faded;
- equal base/target file maps remain active until the target checkpoint ID is actually committed;
- a semantic DB file replacement invalidates state/pending/owner identity rather than allowing the new DB to inherit old source completion.

## Operator modes

### Plan only

```powershell
$Python = "$env:LOCALAPPDATA\hermes\profiles\companion\iai\venv\Scripts\python.exe"

& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me"
```

Optional inventory guard:

```powershell
& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me" `
  --expected-files <confirmed-plan-count>
```

Plan-only validates the source and any existing Orion metadata. It does not create the metadata namespace or lock, open the semantic store, write a checkpoint, or clear recovery state.

### Apply

```powershell
& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me" `
  --expected-files <confirmed-plan-count> `
  --apply
```

The first real full-vault bootstrap remains separately authorized and **MODERATE memory**. The vault remains read-only and the normal iai daemon/Hermes writer must be stopped for that maintenance window.

## Known vendor boundaries

Orion intentionally does not claim guarantees not exposed by iai 3.3.0:

- some internal supersession/tag-update operations log additive failures without a dedicated fatal report field;
- a first Orion bootstrap has no authoritative historical Orion inventory from which to infer ownership of arbitrary pre-existing unmanaged `doc:` tags;
- native `AccessMode.SHARED` is not an exclusive maintenance lock.

These remain bootstrap/runtime calibration boundaries rather than reasons to implement a second semantic engine.

## Source acceptance

Before the source/review cycle is complete:

- rebuilt DC-02 invariant tests must pass on Ubuntu and Windows;
- broader source suites must remain green;
- prior bug classes must remain represented as regression/invariant tests, including enumeration failure, FIFO/special files, source portability, immutable staging, store-root retargeting, redirected `hippo`, vault/store overlap, hardlink aliases, DB replacement identity, **DB swap during native open/live-store binding**, store-open failure, partial native mutation, reverted sources, new-then-deleted recovery, equal-map recovery, completed-journal cleanup/no replay, and real cross-process lock contention;
- a fresh independent review must evaluate the final frozen exact head rather than an older prototype or intermediate rebuilt commit.

Runtime bootstrap remains out of scope until separately approved.
