# DC-02 Markdown-Only Native iai Ingestion Adapter

Date: 2026-10-27

## Purpose

DC-02 restores the authoritative Obsidian Markdown corpus to the canonical native iai store without reintroducing a broad directory watcher.

The implementation boundary is intentionally narrow:

- Orion owns source admission, immutable transaction snapshots, synchronization state, recovery metadata, store ownership, semantic-store identity, and Orion apply serialization.
- pinned `iai-pme==3.3.0` owns Markdown extraction, chunking, embeddings, deduplication, native `doc:` tags, graph weaving, shared document ownership, supersession/fade behavior, recall self-test, native store locking, and persistence.
- the source vault is read-only.
- mutating apply is an operator-run maintenance operation.
- this PR is source/review work only; it does not merge, deploy, touch the real vault/store, or run bootstrap.

## Supported entry point

The only supported transaction entry point is:

`scripts/dc02/orion_vault_markdown_ingest.py`

Implementation is split by invariant:

- `orion_vault_ingest_model.py` — immutable data model, schema versions, and one Windows-portable source-name grammar.
- `orion_vault_ingest_fs.py` — fail-closed filesystem admission, crash-durable metadata writes, immutable staging, and the one Orion advisory lock primitive.
- `orion_vault_ingest_state.py` — checkpoint, owner, planning, and pending-journal state-machine primitives.
- `orion_vault_ingest_runtime.py` — pinned iai 3.3.0 runtime loading, explicit native EXCLUSIVE maintenance open, native report acceptance, CLI arguments, and result envelopes.
- `orion_vault_ingest_contract.py` — vault/store separation, semantic-store topology, semantic DB file identity, and persisted checkpoint validity.
- `orion_vault_markdown_ingest_core.py` — import-only compatibility/re-export surface. Direct execution fails closed.

There is no executable legacy sidecar and no secondary apply CLI.

## Rebuilt transaction invariants

The transaction core is frozen around these invariants:

1. **Validated source names** — a source name is admitted once through one canonical grammar before it may enter planning, state, pending recovery, vendor tagging, or fade operations.
2. **Immutable staging** — iai studies private staged `.md` files, never the mutable live vault path.
3. **Fixed metadata namespace** — state, pending, owner, and lock have fixed locations under the canonical store root; there is no custom `--state-file`.
4. **One pinned store root and one Orion apply lock** — the supplied store root is canonicalized once at transaction entry and that immutable path is used throughout the run.
5. **Persisted semantic DB identity** — state, pending recovery, and owner metadata are bound to the actual `brain.sqlite3` file identity, not only its pathname.
6. **Native EXCLUSIVE maintenance semantics** — every mutating native store open requests iai `AccessMode.EXCLUSIVE`; compliant native clients cannot coexist with the semantic write window.
7. **Explicit pending-journal state machine** — recovery is absent, active, or completed according to checkpoint identity plus file-map digest.

The objective is to keep guarantees at layers that actually expose the required primitives. Orion does not attempt to infer the OS descriptor used by an opaque native database connection.

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

The same validator is reused by checkpoint, pending recovery, native tag ownership, and fade paths. Generated state/pending metadata revalidates snapshot size, mtime, SHA-256, source name, and tag before serialization.

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

Orion does not implement a parallel semantic engine. iai 3.3.0 remains authoritative for extraction, chunking, embeddings, dedup, shared document ownership, native tags, supersession, graph work, recall self-test, store locking, and persistence.

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

## Maintenance threat model

Mutating apply is supported only during a quiescent maintenance window.

Required operator conditions:

- stop the normal iai daemon/Hermes writer before `--apply`;
- do not run another maintenance command against the same store concurrently;
- do not rename, unlink, replace, restore, hardlink, synchronize, or externally overwrite files under the live semantic store while apply is running;
- use a filesystem whose normal local locking semantics are functioning.

Orion then requests `MemoryStore(..., access_mode=AccessMode.EXCLUSIVE, persist_index=False)` for semantic mutation. iai's native Hippo lock is the authority for excluding other **compliant iai clients**. If another compliant client still owns the store, native open fails and Orion leaves the pending journal active for retry.

Out of scope by design:

- a rogue or out-of-band process that bypasses iai/Hippo locking and overwrites store files;
- renaming/unlinking/replacing an open SQLite database underneath the native connection;
- a filesystem with broken advisory-lock semantics.

These are not conditions Orion can make safe from outside an opaque vendor connection. SQLite itself documents rename/unlink of an open database as undefined and states that it cannot defend against a rogue process overwriting the database file.

## Semantic DB file identity

DC-02 persists a semantic DB file identity consisting of:

- canonical resolved DB path;
- filesystem device identifier (`st_dev`);
- filesystem file identifier (`st_ino`; on Python 3.12 Windows this is the file index when available).

The identity is captured through an opened regular single-link DB handle and verified against the current pathname. A missing/zero file identifier fails closed.

Successful state, pending recovery, and owner metadata all carry this identity. Apply uses it to detect replacement/restoration **between successful runs and at transaction boundaries**. It is checked:

- after the Orion lock is acquired and before persisted metadata is trusted;
- immediately before native EXCLUSIVE store open;
- after a clean native store close;
- immediately before successful checkpoint write, including a no-op apply.

Normal in-place native writes retain file identity. Replacing the DB between runs invalidates prior ownership/checkpoint metadata rather than allowing another file to inherit source completion.

DC-02 deliberately does **not** claim a while-open descriptor identity proof. Python's supported DB-API surface and pinned iai 3.3.0 do not expose a portable cross-driver primitive that identifies the OS descriptor belonging specifically to the active writer connection. The previous `/proc/self/fd`/`PRAGMA database_list` heuristic was removed because it could be satisfied by an unrelated descriptor and therefore overstated the guarantee.

This source-only schema remains state v4 / pending v4 / owner v3; no schema bump is required because the persisted identity representation did not change.

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

A persisted state file must contain a non-null timezone-aware successful timestamp. `successful_run_utc: null` is valid only for the synthetic in-memory empty state before any checkpoint exists. Broken persisted aliases are treated as persisted and fail closed rather than being reinterpreted as "no state".

Store owner binds one vault + canonical store + semantic DB file identity + `vault-study` session + iai 3.3.0.

## Two serialization layers

### Orion transaction lock

Apply uses exactly one store-local Orion advisory lock:

`<canonical-store>/orion/vault-markdown-ingest.apply.lock`

- POSIX: nonblocking `flock`;
- Windows: nonblocking one-byte `msvcrt.locking`.

The opened lock handle is verified as a regular single-link file before Windows can write its backing lock byte.

This lock serializes Orion's metadata classification, source inventory, staging, journal creation, native work, checkpoint commit, and cleanup. Plan-only does not create or acquire it.

### Native iai store lock

When semantic mutation is required, the pinned runtime opens `MemoryStore` with `AccessMode.EXCLUSIVE`. This is the supported store-level exclusion mechanism for iai clients. Orion does not replace it with a second inferred lock or a process-wide descriptor search.

The maintenance run still requires the daemon/Hermes writer to be stopped before apply. The EXCLUSIVE native open is the fail-closed enforcement layer if a compliant client was not actually stopped.

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

For one mutating apply transaction:

1. canonicalize and pin the store root;
2. validate vault/store separation and store topology;
3. acquire the one Orion transaction lock;
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
15. open native `MemoryStore` with `AccessMode.EXCLUSIVE`;
16. study staged new files, staged changed files, then fade deleted sources;
17. require clean native store close;
18. revalidate topology and DB file identity;
19. revalidate DB identity again before checkpoint write, including no-op applies;
20. atomically commit state with the pending target checkpoint identity;
21. claim owner after state for a first no-mutation apply if needed;
22. clear pending recovery;
23. remove staged files and release the Orion lock.

POSIX metadata replacement fsyncs the destination directory. Newly created metadata directories are durably fsynced through their parent chain. Windows replacement uses `MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)`.

## Crash/retry behavior

- failure before pending creation: no semantic store mutation has occurred;
- failure after pending but before/during native EXCLUSIVE store open: pending remains active;
- failure after one or more study/fade calls: pending remains active and all affected paths are forced through reconciliation;
- failure after successful state commit but before pending deletion: pending is completed and a retry clears it without semantic replay;
- a newly studied source deleted before retry retains its pending `doc:` ownership tag and is faded;
- equal base/target file maps remain active until the target checkpoint ID is actually committed;
- a semantic DB file replacement between runs or at checked boundaries invalidates state/pending/owner identity rather than allowing another file to inherit old source completion.

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

Before apply, stop the normal iai daemon/Hermes writer and keep the store quiescent for the maintenance window.

```powershell
& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me" `
  --expected-files <confirmed-plan-count> `
  --apply
```

The first real full-vault bootstrap remains separately authorized and **MODERATE memory**. The vault remains read-only. Native EXCLUSIVE open is expected to fail if another compliant iai client still owns the store.

## Research basis for the maintenance boundary

This threat-model correction follows the storage layers' own documented contracts rather than inventing a stronger external guarantee:

- SQLite, "How To Corrupt An SQLite Database File": a rogue process can overwrite an SQLite file and SQLite cannot defend against it; unlinking/renaming an open database is undefined and probably undesirable: <https://www.sqlite.org/howtocorrupt.html>.
- SQLite locking documentation: EXCLUSIVE mode exists when an application wants to prevent other processes from accessing the database: <https://www.sqlite.org/pragma.html#pragma_locking_mode>.
- pinned iai 3.3.0 `MemoryStore`/`HippoDB`: `MemoryStore` defaults to `AccessMode.EXCLUSIVE`, and Hippo implements its own native store lock.
- pinned iai maintenance CLI: mutating maintenance commands refuse a running daemon and tell the operator to stop it first.

Upstream iai also uses whole-store snapshots for several destructive maintenance/migration operations. That is useful operational precedent for a separately authorized backup strategy, but DC-02 does not replace its existing pending-journal reconciliation with snapshot rollback in this ticket.

## Known vendor and maintenance boundaries

Orion intentionally does not claim guarantees not exposed by iai 3.3.0 or SQLite:

- some internal supersession/tag-update operations log additive failures without a dedicated fatal report field;
- a first Orion bootstrap has no authoritative historical Orion inventory from which to infer ownership of arbitrary pre-existing unmanaged `doc:` tags;
- native EXCLUSIVE locking excludes compliant iai clients, not a rogue process that ignores locks and manipulates store files directly;
- out-of-band rename/unlink/replace of the semantic DB while it is open is an unsupported maintenance-window violation, not a condition Orion attempts to make safe.

These are runtime/maintenance boundaries rather than reasons to implement a second semantic engine or unsupported connection-descriptor introspection.

## Source acceptance

Before the source/review cycle is complete:

- rebuilt DC-02 invariant tests must pass on Ubuntu and Windows;
- broader source suites must remain green;
- prior bug classes must remain represented as regression/invariant tests, including enumeration failure, FIFO/special files, source portability, immutable staging, store-root retargeting, redirected `hippo`, vault/store overlap, hardlink aliases, inter-run DB replacement identity, native EXCLUSIVE maintenance-open failure, partial native mutation, reverted sources, new-then-deleted recovery, equal-map recovery, completed-journal cleanup/no replay, and real cross-process Orion lock contention;
- the unsupported `/proc/self/fd` / `PRAGMA database_list` live-writer identity heuristic must remain absent;
- a fresh independent review must evaluate the final frozen exact head against the corrected maintenance threat model rather than demand guarantees outside it.

Runtime bootstrap remains out of scope until separately approved.