# P5-02R — Production Canary Restore Qualification

Status: **PASS / PRODUCTION CANARY RESTORE ACCEPTED / MUTATION MODE DISABLED / HERMES MANUAL-OFF**

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

## Observed live result — PASS

The authorized P5-02R production canary restore completed successfully on
2026-09-24.

Observed apply result:

```text
P5_02R_PRODUCTION_CANARY_RESTORE=PASS
P5_02R_APPLY_SUCCESS=true
P5_02R_MUTATION_PERFORMED=true
P5_02R_RECOVERY_REQUIRED=false
P5_02R_ORIGIN_RECOVERY_ID=33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f
P5_02R_NEW_RECOVERY_ID=1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27
P5_02R_NEW_RECOVERY_RECORD_VALID=true
P5_02R_NEW_RECOVERY_MANIFEST_STATE=committed
P5_02R_NEW_RECOVERY_CLASSIFICATION=committed
P5_02R_NEW_RECEIPT_STATE=committed
P5_02R_NEW_RECEIPT_FINALIZED=true
P5_02R_NEW_RECEIPT_RECONCILIATION_REQUIRED=false
P5_02R_APPROVAL_SURFACE=cli
P5_02R_APPROVAL_CHOICE=once
P5_02R_AUTHORIZATION_REUSABLE=false
P5_02R_ORIGIN_CLASSIFICATION=committed_then_changed
P5_02R_ORIGIN_NEEDS_ATTENTION=false
P5_02R_PRODUCTION_RECOVERY_COUNT_AFTER=2
P5_02R_PRODUCTION_RECOVERY_ATTENTION_AFTER=0
```

New committed restore recovery directory:

```text
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery\1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27
```

Post-restore canary evidence:

```text
P5_02R_CANARY_POST_RESTORE_FILE_ID=5e1aeb8a1aeb5d91:428a0300000031000000000000000000
P5_02R_CANARY_POST_RESTORE_SHA256=ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c
```

The post-restore Windows file identity again differs from the pre-restore
identity. This is expected for the protected replacement. The pre-restore file
ID served as the stale/race guard for the accepted P5-02Q object; the exact
restored hash plus the committed restore recovery/receipt establish the
accepted P5-02R post-state.

Observed parent/post-state checks:

```text
P5_02R_PARENT_CHILD_EXIT=0
P5_02R_PARENT_CANARY_SHA256=DDB08A8CA9AB5D06185A692182A742210817CBA1D5523C841D6A371DFDB57B4C
P5_02R_PARENT_RECOVERY_COUNT=2
P5_02R_PARENT_AUTOMATIC_FOLLOWUP_MUTATION=false
P5_02R_CONFIG_UNCHANGED=true
P5_02R_ENV_UNCHANGED=true
P5_02R_INSTALLED_PLUGIN_UNCHANGED=true
P5_02R_PARENT_MUTATION_MODE_ABSENT=true
HERMES_MANUAL_OFF=true
P5_02R_PARENT_RESTORED_HASH_MATCH=true
P5_02R_PARENT_RECOVERY_COUNT_MATCH=true
P5_02R_GATE_RESULT=PASS
```

No automatic follow-up mutation was attempted.

## Acceptance

P5-02R is accepted.

Accepted production state:

- canary is restored to the original frozen `state: before` bytes;
- canary SHA-256 is
  `ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c`;
- current canary Windows file identity is
  `5e1aeb8a1aeb5d91:428a0300000031000000000000000000`;
- origin P5-02Q recovery record remains valid and reads
  `committed_then_changed`;
- new P5-02R restore recovery record
  `1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27`
  is valid and `committed`;
- production recovery inventory contains exactly two records;
- recovery attention count is zero;
- mutation mode is absent/disabled after the bounded action;
- COMPANION config and `.env` are unchanged;
- installed plugin bytes are unchanged;
- Hermes remains manual-off.

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
