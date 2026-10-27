# DC-02 Markdown-Only Native iai Ingestion Adapter

Date: 2026-10-27

## Purpose

Restore the authoritative Obsidian vault corpus to the canonical native iai store without reintroducing the Docker-era broad directory watch.

The implementation boundary is intentionally narrow:

- Orion owns Markdown source admission, containment, synchronization state, recovery metadata, adapter/store identity, and apply coordination.
- iai 3.3.0 owns extraction, chunking, embeddings, deduplication, document tags, graph weaving, supersession, recall self-test, and persistence.
- The vault remains read-only.
- The adapter is operator-run only; it is not an always-on service.

## Implementation layout

The public entry point is:

`scripts/dc02/orion_vault_markdown_ingest.py`

It is a small transaction coordinator that loads and re-exports the tested implementation primitives from:

`scripts/dc02/orion_vault_markdown_ingest_core.py`

The split keeps source-boundary and native iai primitives stable while making the crash/order invariants explicit at the public apply boundary.

## Native iai contract

`iai_mcp.study.study_document()` is the ingestion primitive. Orion pins `iai-pme==3.3.0`, validates the vendor signatures it relies on, uses `session_id="vault-study"`, and passes `critic=None`.

For current files, iai performs its normal extraction, chunking, content-hash idempotency, near-duplicate reinforcement, graph weaving, supersession, replay metadata, and recall self-test.

For vanished sources, Orion calls the same vendor primitive with `text=""` and the previous `source_name` so fade/supersession remains native iai behavior.

The durable ownership signal is iai's `doc:<slug>` tag, not `session_id`. Orion derives tags through iai 3.3.0's own `_doc_tag()` and fails closed on current, historical, or active-recovery ownership collisions.

## Source admission

A source is admitted only when it is:

- recursively under the resolved vault root;
- exactly `.md` case-insensitively;
- a contained regular file;
- not a symlink/reparse point and not under a traversed reparse directory;
- strict UTF-8;
- no larger than 2,000,000 bytes by default.

The complete admitted corpus is capped at 5,000 files by default. Recursive enumeration permission/I/O errors abort the scan instead of producing a smaller inventory that could become a false deletion plan.

`source_name` is always the vault-relative POSIX path.

## Successful checkpoint

The default checkpoint is:

`<IAI_MCP_STORE>/orion/vault-markdown-ingest-state.json`

State schema v2 records:

- schema version;
- `session_id`;
- resolved vault root;
- canonical iai store root;
- pinned iai version;
- successful-run UTC timestamp;
- successful checkpoint identity;
- per-file SHA-256, size, mtime, and vendor `doc:` tag.

The checkpoint is bound to both the vault and the canonical iai store, including when a custom `--state-file` is supplied. Reusing state against a different vault or store fails closed.

Content SHA-256, not mtime alone, decides whether a current source requires restudy.

## Pending recovery journal

Before any direct native store open for a mutating plan, Orion atomically writes:

`<state-file>.pending.json`

Pending schema v2 contains only recovery metadata:

- vault/session/iai identity;
- canonical store identity;
- base and target checkpoint identities;
- hashes of the base and target file maps;
- affected relative paths and pinned-vendor `doc:` tags.

It never stores note bodies.

The journal is intentionally durable **before `MemoryStore` is opened**, not merely before `study_document()` is called. This keeps recovery fail-closed even if native store construction performs writes or fails partway through initialization.

If store open or a later study/fade step fails, the successful checkpoint remains unchanged and the pending journal remains. On retry, every possibly-mutated path is forced through reconciliation. This covers reverted changed files, newly studied files deleted before retry, equal base/target file maps, and failures that occur before the first semantic call.

A pending journal is **completed** only when the successful checkpoint contains its target checkpoint identity and matching target file-map digest. Current-source pending ownership collisions are enforced only while the journal is **active**. A completed journal is integrity-checked but no longer reserves obsolete `doc:` ownership.

On apply, a completed journal is cleared before checkpoint metadata can be rewritten or a new mutation cycle can begin. If cleanup fails, the successful state and pending journal remain compatible and semantic work is not replayed.

## Durable adapter ownership of the store

A store-wide adapter owner marker is stored at:

`<store-root>/orion/vault-markdown-ingest-owner.json`

Owner schema v1 binds this DC-02 ingestion stream to exactly:

- one resolved vault root;
- one canonical iai store root;
- one canonical state-file path;
- `session_id="vault-study"`;
- iai 3.3.0.

The marker prevents a fresh second state file or a different vault from sequentially reusing the same iai store and silently repurposing the same vendor `doc:` tags.

Plan-only validates an existing owner marker but never creates one. On the first apply to an unowned store, Orion writes the owner marker only after source/state/pending preflight succeeds and while the store-wide apply lock is held. A crash after that write is safe: the store is merely reserved for the same adapter configuration and no semantic success is implied.

## Apply serialization

iai's `AccessMode.SHARED` permits multiple SHARED holders, so vendor locking alone does not serialize two Orion writers. Apply therefore acquires both:

- `<state-file>.apply.lock`;
- `<store-root>/orion/vault-markdown-ingest-store.apply.lock`.

They are nonblocking OS advisory locks (`flock` on POSIX, `msvcrt.locking` on Windows), acquired in deterministic canonical-path order. Partial acquisition is rolled back if a later lock is unavailable.

The state lock prevents two writers from racing one checkpoint/pending journal. The store lock prevents distinct state files from concurrently mutating the same iai store. The durable owner marker additionally prevents sequential cross-vault/cross-state reuse of that store.

Apply holds both locks across state/owner/pending validation, recovery classification, semantic work, native store close, final inventory verification, checkpoint commit, and pending cleanup.

Plan-only never creates or acquires either lock.

## Apply ordering and source-race fences

Semantic order is:

1. new files;
2. content-changed files;
3. vanished paths as empty documents.

Current files are re-snapshotted before and after native study calls. A planned deletion is faded only while the source path is absent immediately before and immediately after the empty-document call. If the source reappears, the run fails and leaves recovery active so a later run can restudy it.

After all semantic calls and a clean native store close, Orion performs a complete second Markdown inventory. The successful checkpoint is written only if that inventory exactly matches the inventory that defined the apply. Unrelated mid-run source drift therefore cannot be silently checkpointed.

## Fail-closed conditions

No successful checkpoint is committed when any of these occurs:

- pinned iai package/signature assumptions differ;
- enumeration, containment, reparse, UTF-8, regular-file, size, or corpus-count checks fail;
- current, historical, or active-pending `doc:` ownership collides;
- persisted checkpoint or pending vendor tags are inconsistent;
- state/pending schema, session, vault root, iai version, or store root is inconsistent;
- an existing store-owner marker does not match the selected vault/store/state tuple;
- state, pending, owner, either lock file, or the iai store is inside the vault;
- canonical `hippo/brain.sqlite3` is absent for apply;
- either apply lock is already held;
- owner or pending metadata cannot be written atomically before direct-store open;
- native store open/close fails;
- iai reports skipped or truncated study data;
- a current note changes before/during study;
- a deleted source reappears before/during fade;
- the final vault inventory differs from the apply-defining inventory;
- the successful checkpoint cannot be written atomically.

## Operator modes

### Plan-only

Plan-only reads and validates the vault, checkpoint, pending journal, and any existing store-owner marker. It does not open/mutate the semantic store and does not write/clear checkpoint, pending, owner, or lock sidecars.

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

### Apply

Apply remains explicit:

```powershell
& $Python .\scripts\dc02\orion_vault_markdown_ingest.py `
  --vault-root "C:\Personal\Me" `
  --expected-files <confirmed-plan-count> `
  --apply
```

The iai daemon/Hermes writer should still be stopped for the first operator bootstrap so direct-store maintenance is isolated from normal runtime work.

The first full bootstrap is a later MODERATE-memory operation. It does not load the Orion qwen model and does not write the vault.

## Non-goals

This ticket does not:

- run the initial full-vault bootstrap;
- create an always-on watcher or Scheduled Task;
- change Hermes hooks/injectors;
- create a custom vector store, retriever, embedding model, or chunker;
- enable iai critic/LLM reconciliation;
- migrate SQLite to Lilli;
- change Ollama or the Orion model;
- change vault mutation policy.

## Acceptance

- deterministic Markdown-only admission;
- fail-closed enumeration/containment/reparse/source limits;
- vendor ownership collision guards for current, historical, and active-pending paths;
- content-hash planning and current-before-deleted native ordering;
- durable pending recovery written before direct native store open;
- checkpoint identity distinguishes active/completed recovery even when file maps are equal;
- completed journals release obsolete ownership and are cleared before checkpoint rewrite;
- deleted-source reappearance and full-inventory drift fail closed;
- schema-v2 state/pending metadata bind to the canonical iai store;
- a schema-v1 store-owner marker prevents sequential cross-vault/cross-state store reuse;
- same-state and same-store concurrent applies are serialized by cross-platform advisory locks;
- atomic metadata-only checkpoint/pending/owner writes outside the vault;
- plan-only performs zero semantic/checkpoint/pending/owner/lock mutation;
- source tests pass on Windows and Ubuntu.

Runtime bootstrap/calibration remains a separate operator action requiring explicit approval.
