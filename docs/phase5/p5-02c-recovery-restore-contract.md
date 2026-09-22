# P5-02C Production Recovery / Restore Contract

Status: **SOURCE-ONLY / READ-ONLY INSPECTOR + RESTORE PREVIEW WINDOWS-VERIFIED / NO LIVE RESTORE**
Date: 2026-09-22
Depends on: P5-01 accepted baseline, P5-02A approval integrity, P5-02B Windows mutation/recovery candidate

## Purpose

P5-02B proved that Orion can preserve recovery bytes before protected edits/moves and classify ambiguous failures instead of pretending every filesystem exception is a simple success/failure.

P5-02C turns those bytes into a production recovery contract.

The key principle is:

> Recovery metadata is evidence, not truth.

A process can crash after the protected filesystem mutation but before the recovery manifest is advanced from `prepared` to `committed`. Therefore recovery must reconcile the actual source/target hashes against the record before offering any resolution.

This phase remains source-only. It does not authorize live plugin installation, real vault mutation, real inbox mutation, or automatic restore.

## Current verified baseline

Windows verification at `2e97019` passed:

- 40/40 `test_p5*.py` tests;
- 2/2 installed-Hermes dispatcher probes;
- plugin doctor PASS with 4 tools / 2 hooks;
- exact HUD approval-card visual inspection;
- real Hermes -> Orion HUD -> human DENY/ALLOW ONCE -> fresh-once no-write path;
- Windows source file-ID binding, writer conflict refusal, handle-based delete behavior, native `ReplaceFileW`, containment, replay, and recovery failure tests.

The registered `orion_vault_apply_plan` handler is still the refusing placeholder.

## Recovery root

Production recovery storage must be a separately configured local directory outside both:

- `C:\Personal\Me`;
- `C:\Personal\Orion-Inbox`.

Do not silently pick or create a production recovery root inside this ticket.

Before live activation, the chosen root must satisfy:

- explicit owner-approved path;
- local filesystem;
- existing directory;
- no symlink/junction/reparse traversal;
- disjoint from vault and inbox in both directions;
- no browser authority;
- no model-controlled path selection;
- owner-only or equivalently restrictive ACL expectations verified on Windows;
- no automatic pruning until retention policy is explicitly accepted.

Recovery artifacts can contain full note contents. Treat them as private data, not disposable logs.

## Record identity

One protected plan gets one opaque recovery record.

The current source candidate uses the 64-hex plan token as the recovery directory name. That is acceptable for source qualification because the plan token already binds:

- action;
- fresh preview nonce;
- canonical source/target identity;
- before/after hashes;
- exact diff hash.

For production, retain an explicit `recovery_id` in the manifest even if it initially equals the plan token. User-facing surfaces should treat it as opaque.

## Production manifest direction

The current schema-1 disposable manifest is intentionally small. Before live mutation, advance to a production schema that can survive restart and explain what happened.

Recommended fields:

```json
{
  "schema_version": 2,
  "recovery_id": "<opaque>",
  "plan_token": "<bound plan>",
  "approval_attempt_id": "<non-authorizing correlation id>",
  "approval_surface": "gateway",
  "approval_choice": "once",
  "action": "edit_note | move_draft",
  "state": "prepared | committed | recovery_required | restored",
  "created_at_utc": "...",
  "updated_at_utc": "...",
  "paths": {},
  "hashes": {},
  "backup_file": "...",
  "backup_sha256": "...",
  "classification": "..."
}
```

Do not persist the private Hermes approval rule key as reusable authority. If correlation is needed, persist a separate non-authorizing attempt identifier.

The manifest must be updated by durable temp-write + fsync + replace. The backup bytes must be written and fsynced before any protected document mutation.

## Read-only reconciliation

The source candidate now includes private `_inspect_disposable_recovery_candidate()`.

It:

- requires the same explicit disposable-root guard as the mutation candidate;
- accepts only a 64-hex recovery ID;
- refuses reparse/missing recovery directories;
- validates manifest schema, plan token, action, state, and expected backup filename;
- hashes the recovery backup and compares it to the manifest;
- independently resolves current source/target files through the existing containment policy;
- never mutates a document or recovery artifact.

### Edit classifications

For a `prepared` edit record:

- target == before hash -> `prepared_no_effect`; no recovery required;
- target == after hash -> `applied_unfinalized`; recovery required because mutation occurred but receipt did not finalize;
- target is absent/other hash -> `divergent_unresolved`; recovery required.

For a `committed` edit record:

- target == after hash -> `committed`;
- anything else -> `committed_then_changed`.

A `committed_then_changed` record is not automatically a recovery incident. The original mutation already completed and a later user/tool edit may be legitimate.

### Move classifications

For a `prepared` move record:

- source == approved hash, target absent -> `prepared_no_effect`;
- source == approved hash, target == approved hash -> `duplicate_unresolved`;
- source absent, target == approved hash -> `applied_unfinalized`;
- anything else -> `divergent_unresolved`.

For a `committed` move record:

- source absent, target == approved hash -> `committed`;
- anything else -> `committed_then_changed`.

Again, `committed_then_changed` is history plus later drift, not proof the original mutation failed.

## Recovery resolution vs historical restore

Do not use one generic “restore” button for every state.

### Recovery resolution

Used only for unresolved `prepared` records where the original operation may have partially completed.

Possible future actions:

- **Finalize receipt only**: for an applied-unfinalized state where current files already match the intended committed result. This changes recovery metadata only.
- **Resolve duplicate move by finalizing move**: delete the inbox source only if source + target still exactly match the approved bytes. This is a protected delete and requires a fresh exact approval.
- **Resolve duplicate move by rolling back target**: delete the vault target only if it still exactly matches the approved bytes. This is also a protected delete and requires a fresh exact approval.
- **Divergent state**: no automatic action. Surface evidence and require a new explicit plan based on current bytes.

### Historical restore

Used for an already committed operation whose backup is being intentionally restored later.

Historical restore is always a new transaction:

- current target/source state is read fresh;
- exact restore diff is generated from current bytes to backup bytes;
- current hash is bound into a new plan;
- recovery record + backup hash are bound into that plan;
- the operator sees exact target/diff;
- Hermes fresh ALLOW ONCE is required;
- final state is revalidated immediately before mutation;
- restore receives its own recovery record.

A stale committed record must never silently overwrite a newer user edit.

## Edit restore

A future edit-restore plan may restore `original.bin` to the same vault path.

Required checks:

- original recovery record is valid;
- backup hash matches record;
- current target canonical identity is contained and not a reparse point;
- current target hash is bound into the restore preview;
- exact diff current -> backup is shown;
- restore uses the same Windows atomic replacement path as normal edits;
- the restore itself writes a new recovery backup of the pre-restore current bytes;
- one fresh human ALLOW ONCE authorizes one restore attempt.

This means restore is reversible too.

## Move recovery

Do not pretend a two-path reverse move is atomic.

For a committed move, the safest historical “restore source” operation is:

1. preview recreation of the inbox source from the recovery backup;
2. exclusive-create the source;
3. verify hash;
4. leave the vault target untouched.

If the user wants the vault target removed afterward, that is a separate delete plan/approval. This avoids combining a copy-back and destructive target delete into one hidden rollback.

For unresolved duplicate state, use the explicit finalize-vs-rollback resolution choices above.

## Automatic behavior

Allowed automatically after startup/restart:

- enumerate recovery records;
- validate them read-only;
- classify their current state;
- surface unresolved records.

Not allowed automatically:

- delete source;
- delete target;
- overwrite a note;
- recreate a source;
- mark unresolved content states as committed;
- prune unresolved recovery records.

Silence, timeout, parse error, corrupt backup, path error, missing artifact, or ambiguous state must remain fail-closed.

## Retention

Do not enable automatic pruning in the first live slice.

Initial policy:

- unresolved / recovery-required records: retain indefinitely until explicitly resolved;
- committed records: retain until a later owner-approved retention policy exists;
- restored records: retain until the same policy exists.

When pruning is eventually added, it must:

- never delete unresolved records;
- never delete the only recovery copy for an unresolved mutation;
- use an explicit age/count policy;
- operate outside the browser;
- produce an audit record of what was removed.

## Source tests added in this slice

The new read-only inspector tests cover:

- committed edit;
- prepared edit with no protected effect;
- applied-but-unfinalized edit;
- duplicate unresolved move;
- committed move;
- corrupt backup refusal.

That raises expected `test_p5*.py` discovery to **46 tests**:

- 16 P5-01;
- 9 P5-02A;
- 21 P5-02B/P5-02C candidate tests.

Windows operator verification is now **PASS**: the full `test_p5*.py` discovery ran **46/46 tests successfully in 0.505s**. No Hermes gateway, HUD fixture, or persistent process was started by that run.

## Next source gate

Implement **restore preview only**:

- historical edit restore: exact current -> backup diff;
- historical move restore: exact absent-source -> backup creation diff, leaving the vault target untouched;
- bind the new preview to recovery ID, verified backup hash, current state, canonical path/parent identity, and a fresh nonce;
- add a read-only revalidator that fails if the current target/source state changes after preview;
- extend approval presentation so the operator can see that the action is a restore and which recovery record/target is involved;
- keep every restore mutator unregistered/unimplemented.

Do not wire restore execution until this preview/revalidation gate passes on Windows.

## Restore-preview candidate

The source-only candidate now implements private historical restore preview and read-only stale revalidation.

### Edit restore preview

For a committed edit recovery record, the preview:

- revalidates the recovery record and backup hash;
- requires the current target to exist as a contained Markdown file;
- reads the current target fresh;
- on Windows, binds the current target file ID in addition to its SHA-256;
- generates an exact unified diff from current bytes -> recovery backup bytes;
- binds recovery ID, current hash, restore hash, target canonical path, file ID when available, exact diff hash, and a fresh preview nonce into a new plan;
- stores exact proposed restore bytes only in the bounded preview cache;
- performs no write.

A committed record whose target has changed since the original operation remains eligible for an intentional historical restore because the restore preview binds the *new current state*. A missing current target is not silently recreated by edit restore; that requires a separately designed create/restore flow.

### Move-source restore preview

For a committed move recovery record, the preview:

- requires the inbox source to remain absent;
- requires the inbox parent to exist and not be a reparse point;
- validates the recovery backup and Orion draft markers;
- generates an exact creation diff from /dev/null -> inbox source backup bytes;
- binds recovery ID, backup hash, source-absent state, source candidate path, parent canonical path, and fresh nonce;
- records the vault target only as reference context and does not require that target to still exist;
- leaves the vault target untouched;
- performs no write.

This preserves the design rule that restoring a moved source is a source recreation, not a hidden reverse move.

### Read-only revalidation

`_revalidate_disposable_restore_preview()` fails closed if, after preview:

- the recovery record is no longer valid/committed;
- the recovery backup hash changes;
- an edit target changes hash;
- a Windows edit target is replaced with a different file object even if the bytes are identical;
- an edit target canonical identity changes;
- a move-source candidate appears;
- a move-source parent identity changes or becomes a reparse point;
- the preview expires or is missing.

It never mutates documents or recovery records.

### Approval presentation

The existing exact approval summary now has explicit restore variants:

- historical edit restore: recovery record, canonical target, current hash, restore hash, exact diff;
- historical move-source restore: recovery record, inbox source candidate, absent state, restore hash, reference vault target, exact diff.

The text explicitly states that restore execution is not registered and will not mutate.

### Non-execution boundary

Restore plans are intentionally unsupported by both current execution paths:

- `apply_plan_placeholder` still returns `p5_01_mutation_not_authorized`;
- private `_execute_disposable_plan_candidate()` returns `unsupported_action` for restore plans.

The restore-preview gate cannot become an accidental restore mutator merely because it shares the preview cache and approval presentation machinery.

### Source tests in this delta

Nine restore-specific tests now cover:

- exact edit restore preview and approval text;
- edit stale-content revalidation;
- Windows same-bytes/different-file-ID replacement rejection;
- unresolved prepared record rejection;
- exact move-source creation preview and approval text;
- move-source preview when the reference vault target no longer exists;
- move-source stale source-appearance rejection;
- corrupt recovery backup refusal;
- explicit refusal to execute restore plans through existing public/private mutators.

Together with the previous suite, current expected `test_p5*.py` discovery is **55 tests**:

- 16 P5-01;
- 9 P5-02A;
- 30 P5-02B/P5-02C tests.

Windows operator verification is now **PASS** for the restore-preview delta:

- full `test_p5*.py` discovery: **55/55 passed** in 0.725s;
- installed-Hermes dispatcher probe: **2/2 passed** in 0.078s;
- plugin doctor: **PASS**, manifest `orion-vault-actions 0.1.0`, 4 tools / 2 hooks;
- no gateway/HUD fixture or persistent probe process was started by these commands.

The known Hermes SQLite 3.40.1 WAL-reset warning remained non-fatal and Hermes used `journal_mode=DELETE`. It is runtime hygiene, not a P5 restore-preview failure.

This closes the restore-preview + stale-revalidation gate. Restore execution remains disabled.

## Next source gate

Implement **production receipt schema + restart-safe authorization/recovery correlation** without enabling restore execution.

The receipt must record what was proposed, what one-time approval attempt occurred, what filesystem/recovery identity was involved, and the final observed classification. It must remain non-authorizing: replaying or editing a receipt can never satisfy the final human approval gate.

## Stop conditions before live mutation

No live mutator may be enabled until:

- recovery root path and ACL contract are accepted;
- read-only recovery inspector passes on Windows;
- production manifest/receipt schema is implemented and restart-safe;
- restore preview exists and is exact;
- corrupt/missing/stale/divergent recovery states fail closed;
- one-use approval remains authoritative at the final mutating handler;
- no automatic recovery action can mutate user content;
- live install and first live mutation each receive their own explicit authorization unit.
