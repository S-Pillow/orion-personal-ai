# P5-02Y — Exact Audited Phase 5 Recovery Cleanup

Status: **PASS / AUDITED RECOVERY CLEANUP ACCEPTED / PHASE 5 CANARY CLOSURE COMPLETE**

Authorization date: 2026-09-25

Branch: `feature/orion-phase5-p5-02y-audited-recovery-cleanup`

Baseline: `main` after accepted P5-02X merge
`6e5a58cf3e684642a1100c3b1e4e6a6c206bc60b`.

Installed protected-delete plugin source:
`211255ff9abfa04101760c7e3358b521a3e530ae`.

## Purpose

P5-02Y is the final authorized Phase 5 canary closure gate.

It removes the retained recovery evidence for the completed Phase 5 canary
transaction chain only after P5-02X established the final five-record set.

This is recovery-retention pruning, not a note mutation. It runs outside the
browser and does not use the registered note-action apply path.

## Owner-approved retention policy

Policy kind:

```text
exact_count_exact_id
```

Pruning is permitted only if production recovery contains exactly five
directories and their IDs are exactly:

```text
33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f
1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27
8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6
5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175
e48123ceecc2be50afb2902511f64397f5dcfa35338ab9fd785cbf7278658b36
```

No extra recovery record may exist.

Every record must be:

- valid;
- zero-attention;
- `recovery_required=false`;
- manifest state `committed`;
- receipt state `committed`;
- receipt finalized;
- receipt reconciliation not required.

Expected actions / read-time classifications:

| Recovery ID | Action | Classification |
| --- | --- | --- |
| `33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f` | `edit_note` | `committed_then_changed` |
| `1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27` | `restore_edit` | `committed` |
| `8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6` | `move_draft` | `committed_then_changed` |
| `5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175` | `restore_move_source` | `committed` |
| `e48123ceecc2be50afb2902511f64397f5dcfa35338ab9fd785cbf7278658b36` | `delete_note` | `committed` |

This exact-count/exact-ID rule is the explicit count policy required by the
accepted recovery contract.

Unresolved or attention-bearing recovery is never eligible.

## Required production state

Before cleanup:

- restored inbox source exists at
  `C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md`;
- source SHA-256 is
  `132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132`;
- source Windows file ID is
  `5e1aeb8a1aeb5d91:67660100000036010000000000000000`;
- protected vault target
  `C:\Personal\Me\_Orion-P5-Move-Canary.md` remains absent;
- unrelated edit canary remains at accepted restored hash;
- installed plugin exactly matches P5-02V-qualified `0.3.0` source;
- mutation mode is absent/disabled;
- Hermes is manual-off.

## Audit record

Before the first recovery directory is removed, the gate writes a durable JSON
audit outside the production recovery root:

```text
%LOCALAPPDATA%\hermes\profiles\companion\orion\recovery-audit\
  p5-02y-phase5-canary-recovery-cleanup-<timestamp>.json
```

The audit records:

- gate and schema version;
- exact retention policy;
- exact approved recovery IDs;
- pre-cleanup source / target / edit-canary state;
- for every recovery record:
  - action;
  - classification;
  - manifest state;
  - recovery-required state;
  - receipt state;
  - receipt finalized / reconciliation state;
  - approval surface / choice;
  - every retained recovery file's relative path, size, and SHA-256;
- a durable removal journal;
- final post-cleanup state.

Audit writes use temp-file + flush/fsync + same-directory atomic replace.

The audit file is deliberately outside the recovery root so it survives the
cleanup it documents.

## Cleanup algorithm

Artifacts:

```text
scripts/phase5/p5-02y-audited-recovery-cleanup.ps1
scripts/phase5/p5-02y-recovery-cleanup-audit.py
```

The PowerShell gate:

1. requires the exact P5-02Y branch and a clean worktree;
2. requires Hermes manual-off by TCP listener state;
3. requires exact installed plugin source `0.3.0`;
4. validates source / target / edit-canary / config state;
5. requires exactly the five approved recovery directory IDs;
6. rejects reparse points in every cleanup tree;
7. compiles the audit helper and doctors the installed plugin;
8. asks the helper to validate native recovery semantics and write the durable
   `prepared` audit;
9. removes each approved recovery directory individually by literal path;
10. after each successful removal, requires a durable audit-journal update
    before proceeding to the next ID;
11. after all five removals, requires the recovery root to be empty;
12. asks the helper to revalidate production state and commit/finalize the
    audit;
13. verifies config, `.env`, plugin, source, target, edit canary, mutation
    environment, and Hermes manual-off remain correct.

No wildcard recovery deletion is used.

## Failure semantics

P5-02Y does not automatically restore pruned recovery records.

If failure occurs before any deletion:

- the prepared audit is preserved if created;
- no recovery record is removed.

If failure occurs after one or more removals:

- stop immediately;
- do not delete any additional recovery directory;
- preserve the audit;
- preserve the observed remaining recovery set;
- do not attempt automatic reconstruction;
- reconcile read-only before any new action.

The audit's removal journal makes partial cleanup distinguishable from
ambiguous loss.

## Expected successful post-state

- all five explicitly approved recovery directories removed;
- production recovery root still exists but is empty;
- native recovery inventory reports 0 records / 0 attention;
- durable P5-02Y audit status = `committed`;
- audit includes all five removal journal entries;
- restored inbox source unchanged;
- vault target remains absent;
- edit canary unchanged;
- installed plugin unchanged;
- config / `.env` unchanged;
- mutation mode remains absent/disabled;
- Hermes remains manual-off.

## Phase 5 closure boundary

P5-02Y does not authorize any unrelated future mutation.

After successful P5-02Y, the controlled Phase 5 canary transaction/recovery
chain is closed and its runtime recovery artifacts are pruned under the explicit
owner-approved policy, while its durable audit and repository acceptance
records remain.

## Accepted Windows execution result

Observed operator result:

```text
P5_02Y_PRECHECK=PASS
P5_02Y_INSTALLED_SOURCE_MATCH=true
P5_02Y_INSTALLED_PLUGIN_VERSION=0.3.0
P5_02Y_INSTALLED_PLUGIN_DOCTOR=PASS
P5_02Y_AUDIT_HELPER_COMPILE=PASS
P5_02Y_POLICY_KIND=exact_count_exact_id
P5_02Y_APPROVED_RECOVERY_COUNT=5
P5_02Y_TARGET_STATE_BEFORE=absent
P5_02Y_SOURCE_SHA256=132FF51D62FD7FD8827D7222E233617E92C55DC21D40FF68164F2238BA0FD132
P5_02Y_HERMES_MANUAL_OFF=true
P5_02Y_AUDIT_PREPARE=PASS
P5_02Y_RECOVERY_ATTENTION_COUNT=0
P5_02Y_UNRESOLVED_RECORDS=0
P5_02Y_REFERENCE_SOURCE_VALID=true
P5_02Y_REFERENCE_TARGET_ABSENT=true
P5_02Y_AUDIT_FINALIZE=PASS
P5_02Y_AUDIT_STATUS=committed
P5_02Y_PRODUCTION_RECOVERY_COUNT_AFTER=0
P5_02Y_PRODUCTION_RECOVERY_ATTENTION_AFTER=0
P5_02Y_REFERENCE_SOURCE_VALID_AFTER=true
P5_02Y_REFERENCE_TARGET_ABSENT_AFTER=true
P5_02Y_RECOVERY_CLEANUP=PASS
P5_02Y_REMOVED_RECOVERY_COUNT=5
P5_02Y_PRODUCTION_RECOVERY_ROOT_EMPTY=true
P5_02Y_SOURCE_UNCHANGED=true
P5_02Y_TARGET_REMAINS_ABSENT=true
P5_02Y_EDIT_CANARY_UNCHANGED=true
P5_02Y_CONFIG_UNCHANGED=true
P5_02Y_ENV_UNCHANGED=true
P5_02Y_INSTALLED_PLUGIN_UNCHANGED=true
P5_02Y_MUTATION_MODE_PERSISTED=false
P5_02Y_AUTOMATIC_RECOVERY_RESTORE=false
HERMES_MANUAL_OFF=true
P5_02Y_GATE_RESULT=PASS
```

Committed audit:

```text
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\recovery-audit\p5-02y-phase5-canary-recovery-cleanup-20260925-041448.json
```

Final audit SHA-256:

```text
9aff3bff771ee8745642510c5f4561de3f8395c490e0d24fc22563cc85650537
```

All five approved recovery IDs were removed individually and each removal was
durably journaled before the next deletion. The final audit was committed only
after the production recovery root was empty and native inventory reported
0 records / 0 attention.

P5-02Y is accepted.

## Current stop point

The controlled Phase 5 canary transaction/recovery chain is closed.

Production recovery root exists and is empty. Its five prior canary recovery
records were pruned under the owner-approved exact-count/exact-ID policy, while
the durable external audit above remains as evidence of what was removed.

The restored inbox source remains present and valid, the protected vault target
remains absent, the edit canary is unchanged, installed plugin/config/.env are
unchanged, mutation mode remains absent/disabled, and Hermes remains manual-off.

No further Phase 5 mutation is authorized by this closure result.
