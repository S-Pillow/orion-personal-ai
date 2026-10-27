# DC-02 Markdown-Only Native iai Ingestion Adapter

Date: 2026-10-27

## Purpose

Restore the authoritative Obsidian vault corpus to the canonical native iai store without reintroducing the Docker-era broad directory watch.

This adapter is deliberately narrow:

- Orion owns source admission, containment, synchronization checkpointing, store/state identity, and apply coordination.
- iai 3.3.0 owns document extraction, chunking, embeddings, deduplication, document tags, graph weaving, supersession, recall self-test, and storage.
- The vault remains read-only.
- The adapter is operator-run only; it is not an always-on service.

## Research findings

### iai 3.3.0 study semantics

`iai_mcp.study.study_document()` is the correct native ingestion primitive. For a path-backed document it uses iai's normal extraction, chunking, content-hash idempotency, near-duplicate reinforcement, `doc:<slug>` ownership tags, provenance, graph weaving, supersession, replay metadata, and recall self-test. Orion calls it with `session_id="vault-study"` and `critic=None`.

For a vanished source, Orion uses the vendor-supported empty-document path (`text=""`, old `source_name`) so native supersession/fade semantics remain owned by iai.

### Why stock `iai teach <vault>` / `iai watch <vault>` is not the boundary

The stock directory iterator accepts every suffix in iai's `SUPPORTED_SUFFIXES`, not Markdown only. Orion's authority boundary is stricter: only contained, non-reparse `*.md` files are admissible. Orion preserves the useful native lifecycle ordering: study current new/changed files first, then fade vanished document ownership.

### Durable ownership

`session_id` is not a reliable durable ownership discriminator after near-duplicate reinforcement. The durable vault ownership signal is iai's `doc:<slug>` tag. Therefore Orion:

- uses `session_id="vault-study"` for ingestion provenance;
- derives exact document tags through iai 3.3.0's `_doc_tag()`;
- refuses current-corpus tag collisions;
- re-derives persisted checkpoint and pending-journal tags through the pinned vendor function;
- refuses active historical/current ownership collisions before semantic mutation.

A completed recovery journal does not continue reserving an old `doc:` tag after its target checkpoint proves the semantic work committed.

### Why Orion serializes `--apply`

The direct-store primitive opens `MemoryStore(..., access_mode=AccessMode.SHARED, persist_index=False)`. In iai 3.3.0, SHARED mode permits multiple SHARED holders, so the vendor lock does not serialize two independent Orion adapter writers.

Orion therefore owns two nonblocking advisory locks:

- a state-specific lock: `<state-file>.apply.lock`;
- a store-wide lock: `<store-root>/orion/vault-markdown-ingest-store.apply.lock`.

The state lock prevents concurrent writers from racing one checkpoint/pending journal. The store lock prevents two different state files from concurrently mutating the same native iai store. Locks are acquired by canonical path in deterministic order, and partial acquisition is rolled back if a later lock is unavailable. POSIX uses `flock`; Windows uses `msvcrt.locking`. Plan-only never creates or acquires either lock.

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
- it is at most 2,000,000 bytes by default;
- its bytes decode as strict UTF-8;
- the complete admitted corpus is at most 5,000 files by default;
- recursive directory enumeration completes without permission or I/O errors.

Enumeration errors abort the scan rather than becoming a smaller inventory that could falsely generate deletion/fade work.

### Identity

`source_name` is always the vault-relative POSIX path, for example `Projects/Orion/Architecture.md`.

Before plan/apply acceptance, Orion asks iai 3.3.0's `_doc_tag()` for every current source name and refuses collisions. Persisted checkpoint and pending paths are also re-derived through the same vendor function before their ownership metadata is trusted.

### State and store binding

The default successful-run checkpoint is:

`<IAI_MCP_STORE>/orion/vault-markdown-ingest-state.json`

State schema v2 records:

- schema version;
- `session_id`;
- resolved vault root;
- canonical iai store root;
- pinned iai version;
- successful-run UTC timestamp;
- successful checkpoint identity;
- per-file SHA-256, size, mtime, and vendor document tag.

The checkpoint is bound to both the vault and the iai store. Reusing a checkpoint with a different vault or different store fails closed. This remains true when an operator supplies a custom `--state-file`.

Content SHA-256, not mtime alone, decides whether a current note requires restudy. Existing state is validated before it can define deletions.

Immediately before successful checkpoint commit, Orion performs a complete second Markdown inventory and requires it to equal the inventory that defined the apply. Any mid-run addition, removal, content change, or timestamp change prevents a stale successful checkpoint from being written.

### Pending mutation recovery

Native iai calls are durable individually, so a later failure in a multi-file apply can leave the semantic store ahead of the last successful checkpoint. Before the first native mutation, Orion atomically writes:

`<state-file>.pending.json`

Pending schema v2 contains metadata only:

- vault/session/iai identity;
- canonical store identity;
- base and target checkpoint identities;
- hashes of the base and target file maps;
- affected relative paths and pinned-vendor `doc:` tags.

It never stores note bodies.

If an apply fails after one or more iai calls, the successful checkpoint stays unchanged and the pending journal remains. Every affected path is forced through reconciliation on retry even if its current hash now matches the old checkpoint. This covers reverted changed files and newly studied files deleted before retry.

Checkpoint identity, not equality of base/target file maps, distinguishes active recovery from completed cleanup. A journal is completed only when the successful checkpoint carries its target checkpoint identity and target file-map digest.

Pending ownership collisions against current sources are enforced only while the journal is **active**. A **completed** journal is validated for integrity but no longer reserves obsolete ownership tags.

On `--apply`, a completed journal is cleared before checkpoint metadata can be rewritten or a new mutation cycle can begin. If cleanup fails, state and pending metadata remain compatible and semantic work is not replayed.

The pending journal is also bound to the canonical iai store. A state/pending/store mismatch fails closed.

### Apply serialization

Apply acquires both the state-specific and store-wide advisory locks before loading state/pending recovery and holds them across:

1. state load and validation;
2. pending recovery classification;
3. plan reconciliation;
4. native semantic mutations;
5. native store close;
6. final vault inventory verification;
7. successful checkpoint commit;
8. pending-journal cleanup.

A concurrent apply fails with `apply_lock_unavailable` instead of waiting or racing. Lock-file existence alone is not ownership; the live OS advisory lock is. Process termination releases the OS lock, so a stale lock file does not block future use.

### Apply order and source-race fences

Semantic mutation order is:

1. new files;
2. content-changed files;
3. vanished paths as empty documents.

Current files are re-snapshotted before and after each native study call. For a planned deletion, Orion verifies that the source path is still absent immediately before and immediately after the empty-document fade. If it reappears, the run fails and leaves recovery active so the next run can restudy the source rather than checkpoint a false deletion.

After all semantic calls and a clean store close, the entire vault inventory is re-scanned before the successful checkpoint is written.

### Fail-closed conditions

No successful checkpoint is committed when any of these occurs:

- iai package version/signature does not match pinned 3.3.0 assumptions;
- vault enumeration, containment, reparse, UTF-8, regular-file, size, or file-count checks fail;
- current, historical, or active-pending `doc:` ownership collides;
- persisted checkpoint/pending vendor tags are invalid;
- state/pending schema, session, vault root, iai version, **or store root** is inconsistent;
- state, pending journal, either apply-lock file, or iai store is inside the vault;
- canonical `hippo/brain.sqlite3` is absent for apply;
- either apply lock is already held;
- native store open/close fails;
- pending journal cannot be written before mutation;
- iai reports skipped or truncated study data;
- a current note changes before/during study;
- a deleted source reappears before/during fade;
- the final vault inventory differs from the apply-defining inventory;
- successful checkpoint cannot be written atomically.

If pending cleanup fails after successful checkpoint commit, the run reports failure; the next run recognizes the completed journal without replaying semantic work.

## Operator modes

### Plan-only (default)

Plan-only imports iai 3.3.0 for compatibility and reads the vault, checkpoint, and pending journal. It does not open/mutate the semantic store and does not write/clear checkpoint, pending journal, state lock, or store lock.

```powershell
$Python = "$env:LOCALAPPDATA\hermes\profiles\companion\iai\venv\Scripts\python.exe"

& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me"
```

Optional bootstrap guard:

```powershell
& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me" `
  --expected-files <confirmed-plan-count>
```

### Apply

Apply is explicit:

```powershell
& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me" `
  --expected-files <confirmed-plan-count> `
  --apply
```

The Orion state/store locks serialize adapter applies. The iai daemon/Hermes writer should still be stopped for the operator bootstrap so direct-store maintenance is isolated from normal runtime work.

The first full bootstrap is a MODERATE-memory operation because it reads every Markdown note and invokes iai embedding/study work. It does not load the Orion qwen model and does not write the vault.

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
- strict containment/reparse/UTF-8/source limits;
- vendor ownership collision guards for current, historical, and active-pending paths;
- content-hash planning;
- current-before-deleted native apply ordering;
- durable pending recovery for partial native mutations;
- checkpoint identity distinguishes active/completed recovery even when file maps are equal;
- completed journals release obsolete ownership and are cleared before checkpoint rewrite;
- deleted-source reappearance fails closed;
- full-inventory drift before checkpoint commit fails closed;
- schema-v2 state and pending metadata are bound to the canonical iai store;
- same-state and same-store concurrent applies are serialized by cross-platform advisory locks;
- partial lock acquisition is rolled back on contention;
- atomic metadata-only checkpoint/pending writes outside the vault;
- plan-only performs zero store/checkpoint/journal/lock mutation;
- source tests pass on Windows and Ubuntu.

Runtime bootstrap/calibration is a later operator action.
