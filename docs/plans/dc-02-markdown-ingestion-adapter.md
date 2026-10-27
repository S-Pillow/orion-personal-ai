# DC-02 Markdown-Only Native iai Ingestion Adapter

Date: 2026-10-27

## Purpose

Restore the authoritative Obsidian Markdown corpus to the canonical native iai store without reintroducing a broad directory watcher.

The implementation boundary is deliberately narrow:

- Orion owns source admission, immutable transaction snapshots, synchronization state, recovery metadata, store ownership, semantic-store topology validation, and apply serialization.
- pinned `iai-pme==3.3.0` owns Markdown extraction, chunking, embeddings, deduplication, `doc:` tags, graph weaving, shared document ownership, supersession/fade behavior, recall self-test, and persistence.
- the vault is read-only;
- the adapter is operator-run only;
- this PR does not run a real bootstrap, merge, deploy, or change Hermes/Ollama/runtime services.

## Implementation layout

Supported CLI:

`scripts/dc02/orion_vault_markdown_ingest.py`

The implementation is split by invariant:

- `scripts/dc02/orion_vault_ingest_model.py` — immutable data model and the single Windows-portable source-name grammar;
- `scripts/dc02/orion_vault_ingest_fs.py` — fail-closed filesystem admission, crash-durable metadata writes, immutable staging, semantic-DB boundary checks, and the one apply lock;
- `scripts/dc02/orion_vault_ingest_state.py` — successful checkpoint, store ownership, planning, and the explicit pending-journal state machine;
- `scripts/dc02/orion_vault_ingest_runtime.py` — pinned iai 3.3.0 loading, native report acceptance, apply ordering, CLI argument parsing, and result envelope;
- `scripts/dc02/orion_vault_ingest_contract.py` — cross-module fail-closed contract for semantic-store topology and persisted checkpoint validity;
- `scripts/dc02/orion_vault_markdown_ingest_core.py` — import-only compatibility/re-export surface used by tests and the public coordinator.

Direct execution of the compatibility core fails closed. There is no secondary legacy apply program or executable source sidecar.

## Design reset

The transaction core was rebuilt after review exposed that the earlier live-path design accumulated too many independent race and path invariants. The rebuilt design has five primary invariants:

1. **validated source names** — one admission grammar is used before a source name may enter planning, state, pending recovery, vendor tagging, or fade operations;
2. **immutable staging** — native iai studies private staged `.md` snapshots, never the live vault path;
3. **fixed metadata namespace** — state, pending recovery, owner, and the single apply lock have fixed names under `<store-root>/orion/`;
4. **one store-wide apply lock** — Orion apply processes are serialized through one OS advisory lock, with semantic-store topology constrained so one physical DB cannot acquire multiple Orion lock namespaces;
5. **explicit journal state machine** — a pending journal is absent, active, or completed according to checkpoint identity plus file-map digest.

The goal is to remove whole classes of bugs instead of adding a new guard for each discovered edge case.

## Native iai 3.3.0 contract

Orion calls `iai_mcp.study.study_document()` with:

- `session_id="vault-study"`;
- `critic=None`;
- the original vault-relative `source_name`;
- a staged Markdown `path=` for new/changed files;
- `text=""` for paths absent from the admitted snapshot.

For Markdown, iai 3.3.0 reads the supplied path as UTF-8 text, then owns chunking and all semantic behavior. Orion does not implement a parallel chunker or semantic store.

The staged file preserves the admitted bytes and original source mtime, so iai's text extraction and note-age semantics remain native while the vendor no longer reopens a mutable vault path.

Whitespace-only, zero-byte, and sub-12-character documents are therefore left to pinned iai's native `chunk_text()` / empty-document behavior. Orion does not manufacture a different semantic interpretation for those files.

Orion still treats the native report as a fail-closed acceptance signal. Skipped/truncated chunks, inconsistent native chunk accounting, incomplete recall sampling, or recall misses prevent successful checkpoint commit.

Pinned iai's `_doc_tag()` remains the ownership authority. Current, historical, and active-recovery tag collisions fail closed before semantic mutation.

## Source-name contract

Every admitted Markdown source receives one canonical vault-relative POSIX name. That name must also be representable on the actual Windows vault host.

Admission rejects:

- empty, absolute, noncanonical, `.` or `..` paths;
- literal backslashes;
- non-Markdown suffixes;
- Windows-forbidden characters `< > : " \\ | ? *`;
- ASCII control characters;
- path components ending in a space or period;
- Windows reserved device stems such as `CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, and `LPT1`-`LPT9` (including the Windows-recognized superscript digit forms);
- non-strict-UTF-8/surrogate source identity;
- case-fold collisions within one inventory.

The same validator is used when loading checkpoint and pending metadata. The adapter therefore cannot successfully persist a source name that a later invocation refuses to load.

## Filesystem admission

A source is admitted only when it is:

- recursively below the resolved vault root;
- `.md` case-insensitively;
- a regular file;
- not a symlink/reparse point;
- not a multi-link/hardlinked file;
- strict UTF-8;
- no larger than 2,000,000 bytes by default.

The complete inventory is capped at 5,000 Markdown files by default.

Reads use one opened lexical vault pathname with `O_NOFOLLOW` where available and `O_NONBLOCK` on POSIX. The opened handle is verified as a regular, single-link file before reading, so a FIFO/socket/device named `*.md` cannot block admission. Size, inode/device identity, link count, mtime, and final byte count are checked across the read, and the pathname is rechecked against the opened-handle identity afterward.

Recursive enumeration errors abort the inventory. Traversed reparse directories and containment escapes fail closed.

## Immutable staging

Planning uses SHA-256. Mtime-only changes do not cause semantic restudy.

For every new or content-changed source in an apply:

1. Orion reopens the live source through the same strict admission boundary;
2. the bytes, size, mtime, relative name, and SHA-256 must still match the admitted snapshot;
3. before any temporary directory is created, Orion verifies that the configured system temp root is not inside the vault or canonical store; those exact bytes are then written to a private temporary `.md` file whose resolved location is verified outside both boundaries;
4. the staged file's mtime is set to the admitted source mtime;
5. staged size, mtime, and SHA-256 are reverified.

**All staging completes before the pending journal is written or `MemoryStore` is opened.**

Once staging succeeds, that immutable snapshot defines the semantic transaction. If the live vault changes afterward, the in-flight transaction still applies the frozen snapshot and commits that snapshot's checkpoint. The next adapter run detects the newer live digest and applies it as a subsequent transaction.

This intentionally replaces the previous before-study/after-study/final-inventory fence. A post-freeze live edit is not allowed to invalidate semantic work that has already been safely frozen and applied.

For a path planned as deleted, absence is checked once more before the new pending journal is written. A later reappearance belongs to the next snapshot/run.

## Fixed metadata namespace and semantic-store topology

There is no `--state-file` option in the rebuilt design.

For a canonical store root, DC-02 exclusively uses:

- state: `<store-root>/orion/vault-markdown-ingest-state.json`
- pending: `<store-root>/orion/vault-markdown-ingest-pending.json`
- owner: `<store-root>/orion/vault-markdown-ingest-owner.json`
- lock: `<store-root>/orion/vault-markdown-ingest.apply.lock`

The native semantic DB remains:

`<store-root>/hippo/brain.sqlite3`

Removing arbitrary state placement eliminates state/store pairing ambiguity and the earlier class of state/pending/owner/lock path-overlap bugs.

Existing metadata, lock, owner, and semantic DB files must be regular non-reparse files with a single filesystem link. The opened lock handle repeats the regular-file/link-count check before Windows writes its locking byte.

The canonical store root is resolved before metadata paths are derived. In addition, `<canonical-store>/hippo` itself must be a real directory: a symlink, junction, or other reparse-point `hippo` is rejected before `brain.sqlite3` is accepted. This enforces **one physical semantic DB -> one Orion metadata namespace + one Orion apply lock** and prevents two apparent store roots from reaching the same DB through redirected `hippo` directories while holding independent locks and journals.

Canonical aliases of the store root itself still collapse through canonical-path resolution.

## State schema v3

The successful state records:

- schema version;
- `session_id` and pinned iai version;
- resolved vault root and canonical store root;
- successful UTC timestamp;
- successful checkpoint identity;
- per-source size, mtime, SHA-256, and native `doc:` tag.

An on-disk state file must contain a non-null timezone-aware successful timestamp. `successful_run_utc: null` is valid only in the synthetic in-memory empty state returned when no checkpoint has ever been persisted. Broken persisted aliases are detected with `lexists` and fail closed instead of being interpreted as “no state”.

This PR has not deployed a prior DC-02 runtime state. A stale prototype schema fails closed rather than being silently migrated.

## Store owner schema v2

The fixed owner marker binds the canonical semantic store to:

- one resolved vault root;
- one canonical store root;
- `session_id="vault-study"`;
- iai 3.3.0.

A state-file path is no longer part of owner identity because state location is fixed by the store root.

For the first mutating apply, pending recovery is made durable first, then ownership is claimed, then the native store may be opened. For a no-mutation first apply, successful state is committed before ownership is claimed.

If an owner exists while both state and pending recovery are missing, apply fails closed rather than interpreting the store as a fresh bootstrap.

## One apply lock

Apply uses exactly one store-local advisory lock:

`<store-root>/orion/vault-markdown-ingest.apply.lock`

- POSIX: nonblocking `flock`;
- Windows: nonblocking one-byte `msvcrt.locking`.

The lock is held across semantic-store topology validation, state/owner/pending classification, source inventory, staging, journal creation, native store work, checkpoint commit, and pending cleanup.

Plan-only never creates or acquires the lock.

The lock serializes Orion adapter writers. It does **not** serialize unrelated native iai SHARED clients. The first real bootstrap must therefore run with the normal iai daemon/Hermes writer stopped.

## Pending schema v3 and explicit recovery state machine

Before any mutating native store open, Orion writes a crash-durable pending journal containing:

- vault/store/session/iai identity;
- base checkpoint identity;
- fresh target checkpoint identity;
- SHA-256 of the base and target file maps;
- affected source names and their native `doc:` tags.

No note body is stored in the journal.

Journal classification is deterministic:

### Absent

No pending file exists. Planning starts from the successful checkpoint.

### Active

The successful state's checkpoint identity equals the journal's **base** identity and its file-map digest equals the journal's base digest.

Every affected journal path is forced through reconciliation even if its current digest has reverted to the successful checkpoint.

Active recovery carries both affected paths **and their native ownership tags**. This is required for a newly studied source that disappears before retry: the source may never have existed in the successful state, but its pending `doc:` tag is still required for an empty-document fade.

A retry writes a new pending target for the newly admitted snapshot. Base and target file maps are allowed to be identical; base and target **checkpoint identities must remain distinct**, so equal maps cannot imply completion.

### Completed

The successful state's checkpoint identity equals the journal's **target** identity and its file-map digest equals the journal target digest.

Completed recovery is cleared before any checkpoint rewrite or new semantic cycle. It does not reserve obsolete pending `doc:` ownership and semantic work is not replayed.

Any other identity/digest relationship fails closed.

## Apply ordering

For one admitted snapshot:

1. acquire the single Orion store lock;
2. validate the fixed metadata namespace and semantic-store topology;
3. load/validate successful state and owner metadata;
4. scan and validate the Markdown inventory and source-name grammar;
5. classify pending recovery;
6. clear a completed journal before further apply work;
7. build/reconcile the plan;
8. freeze every new/changed source into immutable private staging;
9. recheck planned deletions are absent;
10. write the new pending journal durably;
11. claim store ownership if necessary;
12. revalidate `hippo` topology and `hippo/brain.sqlite3`;
13. open native `MemoryStore`;
14. study staged new files, then staged changed files, then fade deleted paths with `text=""`;
15. require a clean store close;
16. atomically commit state with the pending target checkpoint identity;
17. claim owner after state for a first no-mutation apply;
18. clear pending recovery;
19. remove temporary staged files and release the Orion lock.

On POSIX, metadata temp files are fsynced and atomic replacement fsyncs the destination directory. Newly created metadata directories are fsynced through their parent chain. Windows replacement uses `MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)`.

## Crash/retry behavior

- failure before pending creation: no semantic store mutation has occurred;
- failure after pending but before/during store open: pending remains active;
- failure after one or more study/fade calls: pending remains active and all affected paths are forced through reconciliation;
- failure after successful state commit but before pending deletion: the journal is completed and the next apply clears it without semantic replay;
- newly studied then deleted before retry: its tag is recovered from pending and it is faded even though it never existed in the successful state;
- equal base/target file maps during recovery remain active until the target checkpoint identity is actually committed.

## Native report acceptance

For the pinned native `iai_mcp.study.study_document` function, successful checkpoint commit requires:

- no skipped chunks;
- no character truncation;
- no chunk truncation;
- `inserted + reinforced + skipped == chunks_total`;
- `recall_tested == min(5, inserted + reinforced)`;
- `recall_verified == recall_tested`.

For a native zero-chunk document, the expected recall sample is zero and the vendor's native empty/supersession behavior is preserved.

## Known vendor boundaries

Orion intentionally does not claim guarantees the iai 3.3.0 public primitive does not expose:

- internal supersession/tag operations catch and log some failures without a dedicated fatal report field;
- first Orion bootstrap has no historical Orion inventory from which to infer ownership of arbitrary pre-existing unmanaged `doc:` tags;
- `AccessMode.SHARED` is not an exclusive multi-process maintenance lock.

Those are bootstrap/runtime calibration boundaries, not reasons to implement a second semantic engine in Orion.

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

Plan-only validates the vault plus any existing state/pending/owner metadata. It does not create the metadata directory or lock, open the semantic store, write a checkpoint, or clear recovery state.

### Apply

```powershell
& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me" `
  --expected-files <confirmed-plan-count> `
  --apply
```

The first real full-vault bootstrap remains a separate explicitly authorized operator action and remains **MODERATE memory**. The normal iai daemon/Hermes writer must be stopped for that maintenance window. The vault remains read-only.

A quiescent vault is still recommended for bootstrap so the operator knows one run represents one coherent human-visible corpus snapshot. Unlike the previous implementation, however, a post-freeze edit does not corrupt the transaction: it is simply detected as a change on the next run.

## Non-goals

This PR does not:

- run or authorize the real bootstrap;
- merge or deploy itself;
- add a watcher, service, or Scheduled Task;
- change Hermes hooks/injectors;
- change Ollama/models;
- migrate SQLite/Lilli;
- implement custom embeddings, retrieval, chunking, or semantic supersession;
- write the source vault.

## Source acceptance

Before the source/review cycle can be considered complete:

- the rebuilt invariant tests must pass on Ubuntu and Windows;
- prior bug classes must be represented as invariant/regression tests, including directory enumeration failure, FIFO/special files, portable source names, apply-time rejection of a POSIX-only backslash source before journal/owner/store open, current/historical/pending tag collisions, immutable staged paths, staging-temp boundary enforcement, store-open failure, partial semantic mutation, reverted sources, new-then-deleted recovery, equal-map recovery, completed-journal cleanup, hardlink alias rejection, redirected `hippo`/semantic-DB alias rejection, persisted-checkpoint timestamp validity, and real cross-process lock contention;
- a fresh independent code review must evaluate the rebuilt exact head rather than an older prototype commit.

Exact-head source verification at the latest code head before this documentation-only alignment was Orion source-tests run **#82**, PASS on Ubuntu and Windows, including DC-02 and every broader source step.

Runtime bootstrap remains out of scope until separately approved.
