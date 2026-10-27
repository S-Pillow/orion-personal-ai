# DC-02 Markdown-Only Native iai Ingestion Adapter

Date: 2026-10-26

## Purpose

Restore the authoritative Obsidian vault corpus to the canonical native iai
store without reintroducing the Docker-era broad directory watch.

This adapter is deliberately narrow:

- Orion owns source admission, containment, and sync checkpointing.
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

If the old and new paths map to the same iai `doc:` tag, the adapter refuses the
run rather than performing the fade.

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
  DC-02 resolver ceiling.

The adapter fails rather than silently truncating or omitting authoritative
Markdown when a source boundary cannot be proven safe.

### Identity

`source_name` is always the vault-relative POSIX path, e.g.
`Projects/Orion/Architecture.md`.

Before any plan or apply result is accepted, the adapter asks iai 3.3.0's own
`_doc_tag()` function for every current source name and refuses collisions. If
checkpoint state exists, persisted paths are also re-derived through the same
vendor function and checked against current ownership.

### State and change detection

The default state checkpoint is outside the vault:

`<IAI_MCP_STORE>/orion/vault-markdown-ingest-state.json`

The state records:

- schema version;
- `session_id`;
- resolved vault root;
- pinned iai version;
- successful-run UTC timestamp;
- per-file SHA-256, size, mtime, and iai document tag.

Content SHA-256, not mtime alone, decides whether a current note requires
restudy. This avoids reinforcing an unchanged note merely because a sync tool
touched its timestamp.

Existing state is fail-closed validated before it can define deletions. The
checkpoint advances only after the complete apply succeeds and the native store
closes cleanly. A failed run never records a new successful-run checkpoint.

### Apply order

1. new files;
2. content-changed files;
3. vanished paths as empty documents.

This intentionally mirrors iai watch semantics for non-colliding ownership and
makes ordinary rename/shared-owner behavior safe.

### Fail-closed conditions

No checkpoint is committed if any of these occurs:

- iai package version is not exactly 3.3.0;
- required iai study/doc-tag signatures differ from the pinned contract;
- unsafe/reparse path or containment failure;
- invalid UTF-8 or non-regular Markdown source;
- source file exceeds the configured limit;
- corpus exceeds the configured file limit;
- case-insensitive current path collision;
- current iai document-tag collision;
- checkpoint doc tag no longer matches iai 3.3.0 for its persisted source path;
- historical/current document-tag collision;
- state file or iai store is placed inside the vault;
- state belongs to a different vault root/session/schema/iai version;
- persisted checkpoint metadata or successful-run timestamp is malformed;
- canonical `hippo/brain.sqlite3` is absent for apply;
- the native store cannot be opened (including writer/lock conflicts);
- iai reports any skipped or truncated study chunk;
- a note changes before or while it is being studied;
- the store cannot be cleanly closed;
- the checkpoint cannot be written atomically.

Partial iai writes can exist if a later file fails. The state checkpoint does
not advance, so the next operator run retries the same batch. iai's study
capture is idempotent/reinforcing, making this retry behavior intentional.

## Operator modes

### Plan-only (default)

This imports iai 3.3.0 for version/doc-tag compatibility and reads the vault and
checkpoint, but does not open or mutate the semantic store and does not advance
the checkpoint.

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

The iai daemon/Hermes writer should be stopped so the adapter can acquire the
canonical native store directly.

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
- strict containment/reparse protection;
- strict UTF-8 and bounded source limits;
- vendor doc-tag collision guard for current and previous checkpoint ownership;
- vendor compatibility validation for persisted doc tags;
- content-hash planning;
- current-before-deleted apply ordering for non-colliding ownership;
- partial-study and concurrent-file-change failure;
- atomic successful-run checkpoint outside vault with no raw note content;
- plan-only zero store/checkpoint mutation;
- source tests pass on Windows and Ubuntu.

Runtime bootstrap/calibration is a later operator action.
