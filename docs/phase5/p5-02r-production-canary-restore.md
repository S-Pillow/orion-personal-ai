# P5-02R — Production Canary Restore Qualification

Status: **AUTHORIZED / PREPARED / NOT YET EXECUTED**

Date: 2026-09-24

Branch:

```text
feature/orion-phase5-p5-02r-production-canary-restore
```

Depends on accepted P5-02Q state.

## Owner authorization

The owner explicitly authorized the restore qualification following accepted
P5-02Q.

This authorization is limited to exactly one `restore_edit` derived from the
committed P5-02Q recovery record:

```text
33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f
```

Target:

```text
C:\Personal\Me\_Orion-P5-Canary.md
```

No other recovery record, target, action, or follow-up mutation is authorized.

## Frozen pre-restore contract

Accepted P5-02Q current SHA-256:

```text
86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19
```

Accepted current Windows file identity:

```text
5e1aeb8a1aeb5d91:19c10700000020000000000000000000
```

Required restore SHA-256 from the committed `original.bin`:

```text
ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c
```

Frozen reverse diff SHA-256:

```text
3963b73cb038a92f67fb7d81c7d3443dace68ebd238bbdbd73ce04197d9d8ba8
```

Exact reverse diff:

```diff
--- vault/_Orion-P5-Canary.md
+++ vault/_Orion-P5-Canary.md
@@ -1,3 +1,3 @@
 # Orion Phase 5 Canary
-state: after
+state: before
 gate: first-production-edit
```

## Qualified restore path

There is no registered public restore-preview tool.

The installed plugin's qualified production restore path is:

1. read-only `_preview_production_restore_candidate(origin_recovery_id)`;
2. validate the exact committed origin recovery record and backup;
3. freeze a new immutable `restore_edit` plan token;
4. dispatch that token through registered `orion_vault_apply_plan`;
5. guarded wrapper delegates only while process-scoped
   `ORION_P5_MUTATION_MODE=mutation_enabled`;
6. private executor requests one fresh Hermes human `ONCE`;
7. executor revalidates origin record, target hash, target file identity, and
   recovery inventory after the human decision;
8. executor writes a **new** schema-v2 recovery/receipt record for the restore;
9. executor replaces the target with the origin backup bytes;
10. executor verifies the restored hash and commits the new restore record;
11. mutation mode is removed from the child process immediately after dispatch.

The originating P5-02Q record is never rewritten or deleted.

## Expected post-restore recovery state

Success must leave exactly two valid production recovery records and zero
attention state.

### Origin P5-02Q record

The original edit record remains committed, but its read-time classification
becomes:

```text
committed_then_changed
```

because the target has been intentionally restored away from that record's
accepted edit-after hash.

This is historical truth and is not an attention condition.

Expected:

- manifest remains `committed`;
- record remains valid;
- `needs_attention=false`;
- `recovery_required=false`;
- target SHA becomes the restored SHA;
- receipt remains committed/finalized;
- receipt reconciliation remains false;
- receipt current classification becomes `committed_then_changed`.

### New P5-02R restore record

The new restore record must:

- have a new recovery ID equal to the new restore plan token;
- link `origin_recovery_id` to the P5-02Q record;
- action = `restore_edit`;
- manifest state = `committed`;
- classification = `committed`;
- backup file = `before_restore.bin`;
- backup SHA = the P5-02Q after-hash
  `86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19`;
- target/restored SHA =
  `ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c`;
- receipt state = `committed`;
- receipt finalized = true;
- receipt reconciliation = false;
- approval surface = `cli`;
- approval choice = `once`;
- authorization reusable = false.

Expected new recovery-directory files:

```text
before_restore.bin
manifest.json
receipt.json
```

## Failure policy

No automatic follow-up mutation is permitted.

If the restore is denied or fails, the gate preserves:

- the canary's observed state;
- the original recovery record;
- any newly created restore recovery record;
- all receipt/manifest evidence.

The gate then stops for read-only reconciliation.

This prevents one restore authorization from silently becoming an additional
edit or "restore the restore" action.

## Prepared operator artifacts

```text
scripts/phase5/p5-02r-production-canary-restore.ps1
scripts/phase5/p5-02r-production-canary-restore.py
```

The wrapper requires:

```text
I_AUTHORIZE_P5_02R_EXACT_CANARY_RESTORE
```

This is only the script scope token. Actual execution still requires a fresh
Hermes human `ONCE`.

## Stop conditions

Stop before approval unless all of these are exact:

- Hermes manual-off;
- clean P5-02R branch/worktree;
- installed plugin exact-match to P5-02N-qualified source;
- plugin doctor PASS;
- mutation mode not ambient or persisted;
- recovery inventory count = 1;
- recovery attention count = 0;
- sole recovery ID = accepted P5-02Q recovery ID;
- origin record/receipt valid and committed;
- current canary SHA = P5-02Q after-hash;
- current file ID = accepted P5-02Q post-edit file ID;
- restore preview action = `restore_edit`;
- origin recovery/action linkage exact;
- current/restore/diff hashes match this document.

At the live approval prompt, choose **ONCE** only if the recovery ID, target,
current hash, restore hash, and reverse diff exactly match this frozen contract.

## Acceptance boundary

P5-02R acceptance means the accepted P5-02Q canary edit was restored through
the qualified production restore path, a fresh human `ONCE`, and a new
committed schema-v2 recovery/receipt record.

It does not authorize:

- deletion of either recovery record;
- another restore;
- another edit;
- move;
- delete;
- persistent mutation mode;
- session/always approval;
- any other vault/inbox target.

A successful P5-02R returns the canary content to the original
`state: before` bytes but intentionally retains both recovery records as
historical evidence.
