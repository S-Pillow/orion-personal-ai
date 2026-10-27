# DC-02 Markdown-Only Native iai Ingestion Adapter

Date: 2026-10-27

## Purpose

Restore the authoritative Obsidian vault corpus to the canonical native iai
store without reintroducing the Docker-era broad directory watch.

This adapter is deliberately narrow:

- Orion owns source admission, containment, synchronization checkpointing, and
  single-apply coordination.
- iai 3.3.0 owns document extraction, chunking, embeddings, deduplication,
  document tags, graph weaving, supersession, recall self-test, and storage.
- The vault remains read-only.
- The adapter is operator-run only; it is not an always-on service.

## Research findings

### iai 3.3.0 study semantics

`iai_mcp.study.study_document()` is the correct native ingestion primitive. For
a path-backed document it:

1. extracts text using iai's normal parser dispatch;
2. uses file mtime as the note timestamp;
3. chunks through iai's normal `chunk_text()` implementation;
4. captures each chunk with content-hash idempotency and near-duplicate
   reinforcement;
5. assigns a `doc:<slug>` tag derived from `source_name`;
6. preserves provenance including filename and chunk index;
7. weaves related memories through iai's native graph path;
8. supersedes old chunks on restudy instead of hard-deleting them;
9. stamps studied/reviewed records for native replay;
10. probes the native recall path after study.

Critic-based contradiction resolution is optional. Orion does not enable it for
this adapter.

### Why stock `iai teach <vault>` / `iai watch <vault>` is not the boundary

The stock directory iterator intentionally accepts every suffix in iai's
`SUPPORTED_SUFFIXES`, not Markdown only. It also has a directory file-count
cap and its own skip rules. The Orion vault authority boundary is stricter:
only contained, non-reparse `*.md` files are admissible.

Stock `watch_scan_once()` does provide the lifecycle behavior Orion wants:
study current new/changed files first, then represent vanished files as empty
documents so their old document-owned chunks enter the native supersession
funnel. The adapter preserves that order.

### Markdown handling

In iai 3.3.0 `.md` is a plaintext suffix. The native extractor reads it as
UTF-8 text. Orion additionally requires strict UTF-8 before admission because
the current DC-02 source resolver decodes current vault notes as strict UTF-8.

### Durable ownership

The DC-02 investigation proved that `session_id` is not a reliable durable
ownership discriminator after near-duplicate reinforcement: native recall may
surface the first provenance session. The durable vault ownership signal is
the iai `doc:<slug>` tag. Therefore this adapter:

- still uses `session_id="vault-study"` for ingestion provenance and exact-key
  identity;
- does not treat that session id as sufficient ownership;
- precomputes the exact iai document tag for every admitted relative path;
- refuses the entire run if two current relative paths collide to the same doc
  tag;
- re-derives every persisted checkpoint tag through the pinned iai 3.3.0
  `_doc_tag()` implementation before trusting it;
- refuses a current path that collides with a different path from the previous
  successful checkpoint, including a vanished path that would otherwise be
  faded after the new path is studied.

The cross-generation guard matters because iai document tags are sluggified and
truncated. A path can therefore be unique in the current vault while still
colliding with a historical owner. Without the guard, the later empty-document
fade could target the same tag that was just attached to the new path. Orion
fails closed instead of guessing rename intent.

### Rename behavior

For non-colliding tags, iai's exact-key reinforcement unions `extra_tags`.
Therefore, when a renamed file has identical chunks, studying the new path first
adds the new document tag to the existing record. Fading the vanished old path
afterward then removes/disowns the old tag without incorrectly fading a record
still owned by the renamed document.

If the old and new paths map to the same iai `doc:` tag while the old ownership
is still active, the adapter refuses the run rather than performing the fade.
A completed recovery journal does not continue reserving an ownership tag after
its target checkpoint proves that the semantic work already committed.

### Why Orion also serializes `--apply`

The vendor direct-store primitive used by this adapter opens
`MemoryStore(..., access_mode=AccessMode.SHARED, persist_index=False)`. iai
3.3.0's SHARED lock permits multiple SHARED holders, so that vendor lock does
not serialize two independent Orion adapter writers. Without an Orion-level
lock, two simultaneous `--apply` processes could race the same pending journal
and successful checkpoint even though each native iai call is individually
valid.

Orion therefore owns a separate advisory apply lock next to the checkpoint. It
uses a nonblocking OS file lock (`flock` on POSIX, `msvcrt.locking` on Windows)
and holds it across state load, recovery classification, native mutations,
checkpoint commit, and pending-journal cleanup. A second apply fails closed.
Plan-only never acquires or creates this lock.

## Adapter contract

Implementation:

`/scripts/dc02/orion_vault_markdown_ingest.py`

### Source admission

A file is admitted only when all of the following are true:

- it is recursively under the resolved vault root;
- its suffix is exactly `.md` case-insensitively;
- neither it nor a traversed directory is a symlink/reparse point;
- its resolved path remains contained by the resolved vault root;
- it is a regular file;
- it is at most 2,000,000 bytes by default, matching the DC-02 current-source
  resolver ceiling;
- its bytes decode as strict UTF-8;
- the complete admitted corpus is at most 5,000 files by default, matching the
  DC-02 resolver ceiling;
- recursive directory enumeration completes without permission or I/O errors.

The adapter fails rather than silently truncating or omitting authoritative
Markdown when a source boundary cannot be proven safe. In particular, an
`os.walk` enumeration error aborts the scan; it is never converted into a
smaller inventory that could falsely produce deletion/fade work.

### Identity

`source_name` is always the vault-relative POSIX path, e.g.
`Projects/Orion/Architecture.md`.

Before any plan or apply result is accepted, the adapter asks iai 3.3.0's own
`_doc_tag()` function for every current source name and refuses collisions. If
checkpoint state exists, persisted paths are also re-derived through the same
vendor function and checked against current ownership.

### State and change detection

The default successful-run checkpoint is outside the vault:

`<IAI_MCP_STORE>/orion/vault-markdown-ingest-state.json`

The state records:

- schema version;
- `session_id`;
- resolved vault root;
- pinned iai version;
- successful-run UTC timestamp;
- successful checkpoint identity;
- per-file SHA-256, size, mtime, and iai document tag.

Content SHA-256, not mtime alone, decides whether a current note requires
restudy. This avoids reinforcing an unchanged note merely because a sync tool
touched its timestamp.

Existing state is fail-closed validated before it can define deletions. The
checkpoint advances only after the complete apply succeeds and the native store
closes cleanly. Immediately before checkpoint commit, Orion performs a complete
second Markdown inventory and requires it to match the inventory that defined
the apply. A new, removed, changed, or timestamp-touched note that appears
mid-run therefore prevents a stale successful checkpoint from being written.

### Pending mutation recovery

Native iai calls are durable individually, so a later failure in a multi-file
apply can leave the semantic store ahead of the last successful checkpoint.
Before the first native mutation, Orion atomically writes a recovery sidecar
next to the checkpoint:

`<state-file>.pending.json`

The pending journal contains metadata only: vault/session/version identity,
base and target checkpoint identities, hashes of the base and target file maps,
affected relative paths, and their vendor `doc:` tags. It never stores note
bodies.

If an apply fails after one or more iai calls, the successful checkpoint stays
unchanged and the pending journal remains. On the next run, every affected path
is forced through reconciliation regardless of whether its current content hash
now matches the old checkpoint. This covers both important rollback-shaped
cases:

- a changed file was studied successfully, then reverted before retry;
- a newly studied file was deleted before retry and therefore must be faded even
  though it never appeared in the last successful checkpoint.

For a pending-only vanished path, ownership is re-derived through iai 3.3.0's
pinned `_doc_tag()` function. Pending path/tag metadata is always validated
against the vendor function. Current-source ownership collisions are enforced
only while that journal is **active**. Once the successful checkpoint carries
the journal's target checkpoint identity and target file-map digest, the
journal is **completed**; its old paths no longer reserve `doc:` ownership.

A completed journal represents semantic work that already committed. On
`--apply`, Orion clears that completed journal before rewriting checkpoint
metadata or beginning a new mutation cycle. If that cleanup fails, the
successful checkpoint and pending journal remain byte-for-byte compatible and
the run fails without replaying semantic work. This prevents repeated cleanup
failures plus mtime-only source changes from creating an unrecoverable digest
mismatch.

Checkpoint identity, not equality of the base/target file maps alone, decides
whether a journal is active or completed. This remains unambiguous even when a
recovery run intentionally returns the corpus to the exact same file map as its
base checkpoint.

Plan-only mode reads and validates an active or completed pending journal. It
reflects active forced-reconciliation work in its plan but never writes or
clears the checkpoint, pending journal, or apply lock.

### Apply serialization

`--apply` uses a persistent lock file outside the vault:

`<state-file>.apply.lock`

The file itself is harmless coordination metadata; ownership is the live OS
advisory lock, not the file's mere existence. A process crash releases the OS
lock, so a stale lock file does not block a later operator run. The lock is
nonblocking: a concurrent apply fails with `apply_lock_unavailable` instead of
waiting or racing state.

### Apply order and source-race fences

Semantic mutation order is:

1. new files;
2. content-changed files;
3. vanished paths as empty documents.

Current files are re-snapshotted before and after each native study call. For a
planned deletion, Orion verifies that the source path is still absent both
immediately before and immediately after its empty-document fade. If it
reappears, the run fails with the pending journal left active so the next run
can restudy that source rather than checkpointing a false deletion.

After all semantic calls and a clean store close, the entire vault inventory is
re-scanned before the successful checkpoint is written. This catches unrelated
mid-run source additions/changes that per-document checks cannot see.

### Fail-closed conditions

No successful checkpoint is committed if any of these occurs:

- iai package version is not exactly 3.3.0;
- required iai study/doc-tag signatures differ from the pinned contract;
- recursive vault enumeration raises a permission or I/O error;
- unsafe/reparse path or containment failure;
- invalid UTF-8 or non-regular Markdown source;
- source file exceeds the configured limit;
- corpus exceeds the configured file limit;
- case-insensitive current path collision;
- current iai document-tag collision;
- checkpoint doc tag no longer matches iai 3.3.0 for its persisted source path;
- historical/current document-tag collision;
- state file, pending journal, apply lock, or iai store is placed inside the vault;
- state belongs to a different vault root/session/schema/iai version;
- persisted checkpoint metadata or successful-run timestamp is malformed;
- pending journal identity, digest, path, or vendor-tag metadata is malformed or
  inconsistent with the successful checkpoint;
- an **active** pending ownership tag collides with a different current source;
- canonical `hippo/brain.sqlite3` is absent for apply;
- another Orion adapter apply holds the apply lock;
- the native store cannot be opened;
- the pending recovery journal cannot be written before native mutation;
- iai reports any skipped or truncated study chunk;
- a current note changes before or while it is being studied;
- a deleted source reappears before or during its fade;
- the final vault inventory differs from the inventory that defined the apply;
- the store cannot be cleanly closed;
- the successful checkpoint cannot be written atomically.

If journal cleanup fails after the successful checkpoint has already been
written, the run reports failure but the next run recognizes the journal as
completed from its checkpoint identity plus target digest and does not replay
semantic mutations.

## Operator modes

### Plan-only (default)

This imports iai 3.3.0 for version/doc-tag compatibility and reads the vault,
successful checkpoint, and any pending recovery journal, but does not open or
mutate the semantic store and does not write or clear checkpoint, pending, or
apply-lock sidecars.

Example:

```powershell
$Python = "$env:LOCALAPPDATA\hermes\profiles\companion\iai\venv\Scripts\python.exe"

& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me"
```

Optional bootstrap guard after observing the current inventory:

```powershell
& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me" `
  --expected-files <confirmed-plan-count>
```

Plan output includes source/store/state identity, iai version, file and
new/changed/unchanged/deleted counts, collision/rejection status, and whether
the canonical store exists. The plan remains read-only even when the canonical
store is absent.

### Apply

Apply is intentionally separate and explicit:

```powershell
& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me" `
  --expected-files <confirmed-plan-count> `
  --apply
```

The Orion apply lock prevents a second adapter apply from racing the first. The
iai daemon/Hermes writer should still be stopped for the operator bootstrap so
this direct-store maintenance operation is isolated from normal runtime work.

The first full bootstrap is a MODERATE-memory operation because it reads every
Markdown note and invokes iai embedding/study work. It does not load the Orion
qwen model and does not write the vault.

## Non-goals

This ticket does not:

- run the initial full-vault bootstrap;
- create an always-on watcher or Scheduled Task;
- modify Hermes hooks or the DC-02 injector;
- create a custom vector store, retriever, embedding model, or chunker;
- enable iai critic/LLM reconciliation;
- migrate SQLite to Lilli;
- change Ollama, Hermes, or the accepted Orion model;
- change vault mutation policy.

## Acceptance for the adapter implementation

- deterministic Markdown-only inventory;
- directory-enumeration failures abort rather than produce false deletions;
- strict containment/reparse protection;
- strict UTF-8 and bounded source limits;
- vendor doc-tag collision guard for current and previous checkpoint ownership;
- vendor compatibility validation for persisted and pending doc tags;
- content-hash planning;
- current-before-deleted apply ordering for non-colliding ownership;
- durable pending-run recovery for partial native mutations, including reverted
  changed files and newly studied files deleted before retry;
- checkpoint identity distinguishes active recovery from completed cleanup even
  when base and target file maps are equal;
- completed journals do not reserve obsolete document ownership;
- completed-journal cleanup cannot rewrite checkpoint metadata first;
- source reappearance during deletion/fade fails closed;
- full-inventory drift before checkpoint commit fails closed;
- concurrent adapter applies are serialized by a cross-platform advisory lock;
- partial-study and concurrent-file-change failure;
- atomic successful-run checkpoint and pending journal outside vault with no raw
  note content;
- plan-only zero store/checkpoint/journal/apply-lock mutation;
- source tests pass on Windows and Ubuntu.

Runtime bootstrap/calibration is a later operator action.
