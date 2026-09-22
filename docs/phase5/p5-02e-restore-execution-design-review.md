# P5-02E Restore Execution Design Review

Status: **DESIGN COMPLETE / PRIVATE DISPOSABLE EXECUTOR CANDIDATE / WINDOWS VERIFICATION PENDING / LIVE RESTORE PROHIBITED**
Date: 2026-09-22
Depends on: P5-02A approval integrity, P5-02B Windows mutation hardening, P5-02C recovery + restore preview, P5-02D restart-safe receipts

## Review question

Can historical restore reuse the already-qualified P5 edit/move safety primitives without creating a new hidden mutation model?

Review result: **yes, with two bounded restore operations and one new recovery/receipt record per restore transaction.**

The restore path must not mutate the original recovery record and must not treat recovery data as reusable authorization.

## Accepted baseline

Current Windows operator baseline:

- 62/62 `test_p5*.py` passed in 0.841s;
- 2/2 installed-Hermes dispatcher probes passed in 0.090s;
- plugin doctor PASS with 4 tools / 2 hooks;
- exact approval display, real Hermes fresh-once no-write path, Windows move identity hardening, recovery reconciliation, restore preview/stale revalidation, and restart-safe non-authorizing receipts are accepted;
- registered `orion_vault_apply_plan` still points to the refusing placeholder;
- no restore executor is registered.

The known Hermes SQLite 3.40.1 WAL-reset warning remains separate runtime hygiene; Hermes uses `journal_mode=DELETE`.

## Restore operation 1: historical edit restore

### Intent

Replace the *current* vault note with the exact bytes stored in an older committed edit recovery record.

This is not “rewind history.” It is a new edit transaction whose proposed content happens to come from a verified recovery artifact.

### Primitive

Reuse the already-qualified edit primitive:

- same-directory exclusive temporary file;
- durable write + fsync;
- native Windows `ReplaceFileW`;
- post-write SHA-256 verification.

Do not add a second replacement implementation just for restore.

### Required preconditions

The restore plan must still be live and must have action `restore_edit`.

Immediately before mutation the executor must verify:

- originating recovery record is still valid and `committed`;
- originating backup bytes still hash to `recovery_backup_sha256`;
- current target remains within the vault containment policy;
- target canonical path still matches the preview;
- on Windows, target file ID still matches the preview;
- current target SHA-256 still equals the preview-bound `current_sha256`;
- exact cached restore bytes hash to `restore_sha256`;
- exact approval diff hash still matches `diff_sha256`;
- restore plan is not already consumed.

Any mismatch is stale and must fail before creating the restore transaction's recovery directory.

### Fresh approval ordering

The production handler ordering must be:

1. load/validate restore preview;
2. show the exact restore approval summary;
3. obtain fresh Hermes **ALLOW ONCE** evidence;
4. **revalidate the restore preview again after approval**;
5. create the restore transaction recovery/receipt;
6. consume the plan;
7. enter the protected replacement operation.

The second revalidation is required because the file may change while the human is deciding.

A receipt from any earlier action, including the originating recovery record, cannot satisfy step 3.

### Restore transaction recovery record

The restore itself gets a **new recovery ID**, independent of the originating recovery ID.

For the source candidate, using the new restore plan token as the new recovery ID is acceptable.

The restore record links backward with:

- `origin_recovery_id`;
- `origin_action=edit_note`;
- `action=restore_edit`.

Before replacing the note, preserve the *current pre-restore bytes* as the restore transaction's before-image. This makes the restore itself reversible.

Suggested artifact:

- `before_restore.bin` = bytes currently in the vault note immediately before restore.

Suggested manifest state:

```json
{
  "action": "restore_edit",
  "origin_recovery_id": "<old recovery id>",
  "target_relative_path": "...",
  "before_sha256": "<current pre-restore sha>",
  "after_sha256": "<old backup/restore sha>",
  "backup_file": "before_restore.bin",
  "state": "prepared | committed"
}
```

The new prepared receipt contains the fresh restore approval evidence, not the approval evidence from the original edit.

### Crash/restart classification

For a prepared restore-edit record:

- target == before SHA -> `prepared_no_effect`;
- target == restore/after SHA -> `applied_unfinalized`;
- target missing or any other SHA -> `divergent_unresolved`.

For a committed restore-edit record:

- target == restore/after SHA -> `committed`;
- anything else -> `committed_then_changed`.

A crash after replacement but before manifest/receipt finalization must **not** trigger another replacement. Reconciliation detects `applied_unfinalized`.

### Residual concurrency boundary

Restore-edit inherits the same bounded Windows replacement semantics as the accepted edit candidate: final canonical path/file-ID/hash validation occurs immediately before native `ReplaceFileW`, followed by post-write verification.

Do not claim this is a cryptographic lock against a malicious local process racing in the final CPU instructions. The accepted safety model is fail-closed stale detection plus Windows atomic replacement, not hostile-kernel/local-admin resistance.

If the threat model later requires stronger target-object locking, harden the normal edit primitive and restore together rather than adding restore-only behavior.

## Restore operation 2: historical move-source restore

### Intent

Recreate the original Orion inbox draft from a committed move recovery record.

It does **not** delete or modify the vault target.

### Primitive

Reuse the already-qualified exclusive-create primitive:

- source must be absent;
- parent must already exist, remain contained, and not be a reparse point;
- write restore bytes with exclusive `xb` semantics;
- flush + fsync;
- verify SHA-256.

Do not implement a reverse two-path move.

### Required preconditions

Immediately before mutation:

- originating move recovery record remains valid and `committed`;
- recovery backup still hashes to `restore_sha256`;
- backup still carries Orion draft markers;
- inbox source is still absent;
- inbox parent canonical identity still matches the preview;
- proposed source path remains contained;
- exact diff and proposed bytes still match the restore plan;
- restore plan is not already consumed.

Reference vault-target state is informational only. The target may be present, changed, or absent without blocking source recreation.

### Fresh approval ordering

Same sequence as edit restore:

1. validate preview;
2. fresh Hermes ALLOW ONCE;
3. revalidate again **after approval**;
4. create new restore recovery/receipt;
5. consume plan;
6. exclusive-create source;
7. verify result.

If another process creates the source between revalidation and step 6, exclusive creation fails without overwrite.

### Restore transaction recovery record

Again, create a **new** recovery ID linked to the originating move recovery ID.

Because the pre-restore source state is intentionally absent, there is no before-image file to preserve.

Instead store the exact created payload as a recovery evidence artifact, for example:

- `created_source.bin` = exact bytes Orion attempted to create.

Suggested manifest:

```json
{
  "action": "restore_move_source",
  "origin_recovery_id": "<old move recovery id>",
  "source_draft": "...",
  "before_state": "absent",
  "after_sha256": "<restore sha>",
  "evidence_file": "created_source.bin",
  "state": "prepared | committed"
}
```

The purpose of `created_source.bin` is reconciliation and audit, not authorization.

### Crash/restart classification

For a prepared move-source restore:

- source absent -> `prepared_no_effect`;
- source exists and SHA == restore SHA -> `applied_unfinalized`;
- source exists with any other SHA -> `divergent_unresolved`.

For a committed move-source restore:

- source exists and SHA == restore SHA -> `committed`;
- source absent or different SHA -> `committed_then_changed`.

There is no `duplicate_unresolved` state because this restore touches only one path.

### Undoing a move-source restore

Do not silently delete the recreated inbox source.

Undo is a separate future delete transaction:

- preview exact source identity/hash;
- show deletion target clearly;
- fresh ALLOW ONCE;
- delete only if still identical;
- preserve its own recovery/receipt evidence.

This keeps “restore source” and “remove source again” as separate human decisions.

## Receipt requirements for restore execution

The P5-02D receipt model extends naturally to restore, but production schema should advance rather than overloading disposable schema-1 assumptions.

Recommended restore receipt fields:

- new `recovery_id`;
- new restore `plan_token`;
- `origin_recovery_id`;
- restore action;
- exact public restore plan;
- fresh restore `approval.attempt_id`;
- exact restore approval message + SHA-256;
- `approval.choice=once`;
- `authorization_reusable=false`;
- restore recovery artifact role/name/hash;
- prepared/committed state;
- current reconciliation classification.

Never copy the originating action's approval attempt into the restore receipt as if it authorized the restore.

## Receipt-finalization failures

Filesystem success and receipt success are separate observations.

If filesystem postconditions are verified but receipt finalization fails:

- do not repeat the filesystem mutation;
- return failure/recovery-required;
- leave the prepared receipt/recovery record intact;
- restart reconciliation should classify content as `applied_unfinalized`;
- a later metadata-only reconciliation step may finalize the receipt **only after** the current file state still exactly matches the intended after-state.

Metadata-only receipt finalization must not become a route to mutate user content.

## Replay rules

A restore plan becomes consumed before the protected filesystem call.

After consumption:

- success cannot be replayed;
- ambiguous failure cannot be replayed;
- receipt-finalization failure cannot be replayed;
- restart does not recreate approval authority.

A fresh restore requires a new preview/plan and a new human ALLOW ONCE.

## Failure ordering

Before protected mutation, failures report `mutation_performed=false`.

After the protected mutation starts, ambiguous failures conservatively report:

- `mutation_performed=true`;
- `recovery_required=true`;
- the new restore recovery ID when available.

Do not infer “no mutation” solely from an exception after the protected call boundary.

## Proposed source implementation shape

Do **not** extend the existing `_execute_disposable_plan_candidate()` with restore branches indefinitely.

Preferred next source structure:

- keep existing edit/move candidate for regression;
- add one private `_execute_disposable_restore_candidate()`;
- require `approval_evidence` for every restore execution call;
- first call `_revalidate_disposable_restore_preview()`;
- dispatch only `restore_edit` and `restore_move_source`;
- share low-level durable write / ReplaceFileW / exclusive-create helpers;
- share receipt helpers after generalizing artifact role/name handling;
- remain unregistered.

This separation keeps restore-specific origin linkage and crash classifications explicit while still reusing the proven low-level mutation primitives.

## Tests required before source implementation can pass

At minimum:

### Restore edit

- committed restore with new recovery + receipt;
- current bytes preserved in `before_restore.bin`;
- fresh-once evidence required;
- stale hash after approval but before executor mutation fails;
- Windows same-bytes/different-file-ID after approval fails;
- interruption before replace -> prepared/no effect;
- interruption after ReplaceFileW -> applied-unfinalized;
- receipt finalization failure after successful replace -> applied-unfinalized, no replay;
- post-write hash mismatch -> recovery-required;
- consumed plan replay refused;
- restore of restore produces a new independent record, not mutation of the parent record.

### Restore move source

- committed exclusive-create restore;
- fresh-once evidence required;
- source appears after approval -> fail before overwrite;
- exclusive-create race -> no overwrite;
- interruption before create -> prepared/no effect;
- interruption after create -> applied-unfinalized;
- receipt finalization failure after create -> applied-unfinalized, no replay;
- post-create hash mismatch -> recovery-required;
- reference vault target changed/absent does not block;
- consumed plan replay refused.

### Cross-cutting

- original recovery record remains byte-for-byte unchanged;
- originating approval receipt cannot authorize restore;
- restore receipt cannot authorize a later action;
- corrupt origin backup fails before new recovery creation;
- corrupt restore recovery artifact fails reconciliation;
- restart inspection does not depend on in-memory preview/attempt caches;
- registered public apply handler still refuses restore.

## Design stop conditions

Do not implement a registered restore executor until all of the following are true:

- restore source candidate tests pass on Windows;
- restore recovery/receipt inspection handles both restore actions;
- approval evidence is mandatory in the restore executor;
- post-approval revalidation is tested;
- replay is tested after success and ambiguous failure;
- receipt-finalization failure is tested;
- original recovery record immutability is tested;
- plugin doctor still reports only the expected registered tools/hooks;
- no live plugin install or real vault mutation has been separately authorized.

## Private source candidate implemented

A private, unregistered `_execute_disposable_restore_candidate()` now implements the reviewed design for explicitly configured disposable roots only.

It requires structured fresh-once approval evidence on every call. The approval attempt is consumed before post-approval stale revalidation can complete, so a failed stale check cannot reuse the same human decision later.

### Restore edit execution

The candidate:

- performs the mandatory post-approval restore revalidation;
- rechecks canonical target identity, Windows file ID, and current SHA-256;
- creates a new recovery directory keyed by the restore plan token;
- preserves current pre-restore bytes as `before_restore.bin`;
- writes a prepared restore manifest linked by `origin_recovery_id`;
- writes a prepared non-authorizing receipt containing the exact restore approval card;
- consumes the restore plan immediately after durable preparation;
- reuses the same same-directory durable temp + native `ReplaceFileW` primitive as normal edits;
- verifies the final restore hash;
- commits manifest and then receipt.

A later restore of a committed `restore_edit` record is supported. It uses that restore transaction's `before_restore.bin` as the historical content, creating another independent restore transaction rather than modifying the parent record.

### Restore move-source execution

The candidate:

- performs the mandatory post-approval restore revalidation;
- requires the inbox source to remain absent and its parent identity unchanged;
- creates a new recovery directory linked to the originating move record;
- stores `created_source.bin` as exact reconciliation/audit evidence;
- writes a prepared non-authorizing receipt;
- consumes the plan after durable preparation;
- reuses exclusive `xb` creation + fsync + SHA-256 verification;
- never modifies or deletes the reference vault target;
- commits manifest and receipt only after the created source verifies.

If another process wins the create race, Orion does not overwrite it. The result reports no Orion content mutation but leaves the prepared transaction recovery-required for reconciliation.

### Crash and receipt-finalization behavior

The candidate has deterministic private checkpoints around:

- restore recovery preparation;
- immediately before edit replacement / source creation;
- immediately after edit replacement / source creation;
- immediately before receipt finalization.

The generalized read-only recovery inspector now understands `restore_edit` and `restore_move_source` records.

The generalized receipt inspector now:

- validates restore approval-card text against the immutable restore plan;
- accepts only the restore transaction artifact names `before_restore.bin` / `created_source.bin`;
- validates `origin_recovery_id` binding;
- preserves non-replay semantics;
- reports a prepared receipt with already-committed filesystem state as `applied_unfinalized`, so receipt-finalization failure cannot trigger a repeated content mutation.

### Approval wording

Restore approval cards now state truthfully that the one-time approval may be used only by the **private disposable restore candidate for the exact displayed plan**, while registered/live apply remains fail-closed.

They no longer claim that no disposable mutation can occur once this private candidate is invoked.

## Source coverage added

New `test_p5_02e_restore_execution.py` adds **24 tests** covering:

- private/unregistered boundary and public apply refusal;
- fresh approval evidence required;
- originating approval evidence cannot authorize restore;
- successful edit restore with independent recovery/receipt;
- stale content after approval and consumed approval evidence;
- Windows same-bytes/different-file-ID refusal;
- prepared/no-effect edit interruption;
- applied-unfinalized edit interruption;
- receipt-finalization failure without replay;
- edit post-write hash mismatch;
- restore-of-edit-restore as a new independent transaction;
- move-source approval requirement;
- successful exclusive-create restore with untouched vault target;
- source appearance after approval;
- interruption before create -> prepared/no effect;
- exclusive-create race with no overwrite;
- interruption after create -> applied-unfinalized;
- move receipt-finalization failure and replay refusal;
- post-create hash mismatch;
- reference vault target disappearance not blocking source recreation;
- corrupt origin backup refusal before new transaction creation;
- corrupt restore artifact reconciliation refusal;
- durable restore receipt cannot authorize a second restore;
- restart inspection with no reconstructed approval authority.

Current expected `test_p5*.py` discovery is **86 tests**:

- 16 P5-01;
- 10 P5-02A;
- 36 P5-02B/P5-02C/P5-02D;
- 24 P5-02E restore-execution tests.

The accepted Windows baseline remains **62/62 + dispatcher 2/2 + plugin doctor PASS**. The 86-test private restore-executor delta is pending fresh Windows verification.

## Updated stop condition

Even if all 86 tests pass, the private executor remains unregistered.

A green source gate does **not** authorize:

- wiring restore into `orion_vault_apply_plan`;
- installing/enabling the plugin in live COMPANION;
- starting/reconfiguring Hermes services;
- choosing/creating a production recovery root;
- mutating the real vault or inbox.

Those remain separate authorization units.

## Review conclusion

The restore execution design is compatible with the existing P5 safety model.

No new mutation primitive is needed:

- **restore_edit** -> existing atomic replacement primitive;
- **restore_move_source** -> existing exclusive-create primitive.

What is new is transaction bookkeeping: every restore is its own approval, recovery record, receipt, replay boundary, and reconciliation lifecycle.

The design review and private disposable implementation authorize no live mutation by themselves.
