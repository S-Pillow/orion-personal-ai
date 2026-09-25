# P5-02U — Move-Source Restore

Status: **PASS / MOVE-SOURCE RESTORE ACCEPTED / MUTATION MODE DISABLED / HERMES MANUAL-OFF**

Authorization date: 2026-09-25

Branch: `feature/orion-phase5-p5-02u-move-source-restore`

Baseline: `main` after accepted P5-02T merge `ca20bc82b6ff6aceff011846af86b18cbd4f4d25`.

Installed plugin remains pinned to P5-02N-qualified source `faf8b4787d8e6fb668eb5e9d754104910b4b401a`.

## Authorized scope

P5-02U is limited to one `restore_move_source` action using the committed P5-02T move recovery:

`8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6`

The restore recreates:

`C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md`

The existing vault reference target must remain present and unchanged:

`C:\Personal\Me\_Orion-P5-Move-Canary.md`

Operator token:

`I_AUTHORIZE_P5_02U_EXACT_MOVE_SOURCE_RESTORE`

The production apply still requires a fresh Hermes human **ONCE** decision.

## Frozen contract

- source before restore: absent
- reference target before restore: present
- restore/source/target SHA-256: `132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132`
- restore diff SHA-256: `5129b0fd7837d9207c4a05d3be365d9939c6a0c39c4fba48369487d6a2761bd2`
- production recovery before restore: 3 records / 0 attention
- mutation mode before restore: disabled
- Hermes before restore: manual-off

Exact restore preview:

```diff
--- /dev/null
+++ inbox/_Orion-P5-Move-Canary.md
@@ -0,0 +1,9 @@
+---
+orion_draft: true
+status: draft
+date: 2026-09-24
+origin: p5-02s-controlled-fixture
+---
+# Orion Phase 5 Move Canary
+state: inbox
+gate: first-production-move
```

## Gate artifacts

- `scripts/phase5/p5-02u-move-source-restore.ps1`
- `scripts/phase5/p5-02u-move-source-restore.py`

The gate validates the exact three-record P5-02T recovery baseline, the absent inbox source, the unchanged vault target, the committed move recovery record, and the exact restore preview before enabling process-scoped mutation around one registered apply dispatch.

## Expected successful post-state

- inbox source recreated at the frozen SHA-256
- vault target still present at the same frozen SHA-256
- new recovery action `restore_move_source` committed and valid
- origin P5-02T move record valid with read-time classification `committed_then_changed`
- production recovery after restore: 4 records / 0 attention
- approval surface `cli`, choice `once`, non-reusable
- mutation mode disabled afterward
- config / `.env` / installed plugin unchanged
- unrelated edit canary unchanged
- Hermes manual-off

## Observed live result — PASS

The authorized P5-02U production move-source restore completed successfully on
the accepted Windows COMPANION environment.

Observed result:

```text
P5_02U_PRODUCTION_MOVE_SOURCE_RESTORE=PASS
P5_02U_APPLY_SUCCESS=true
P5_02U_MUTATION_PERFORMED=true
P5_02U_RECOVERY_REQUIRED=false
P5_02U_ORIGIN_MOVE_RECOVERY_ID=8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6
P5_02U_NEW_RECOVERY_ID=5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175
P5_02U_NEW_RECOVERY_MANIFEST_STATE=committed
P5_02U_NEW_RECOVERY_CLASSIFICATION=committed
P5_02U_NEW_RECEIPT_STATE=committed
P5_02U_NEW_RECEIPT_FINALIZED=true
P5_02U_NEW_RECEIPT_RECONCILIATION_REQUIRED=false
P5_02U_APPROVAL_SURFACE=cli
P5_02U_APPROVAL_CHOICE=once
P5_02U_AUTHORIZATION_REUSABLE=false
P5_02U_ORIGIN_MOVE_CLASSIFICATION=committed_then_changed
P5_02U_ORIGIN_MOVE_NEEDS_ATTENTION=false
P5_02U_SOURCE_STATE_AFTER=present
P5_02U_SOURCE_SHA256=132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132
P5_02U_SOURCE_FILE_ID=5e1aeb8a1aeb5d91:67660100000036010000000000000000
P5_02U_REFERENCE_TARGET_STATE_AFTER=present
P5_02U_REFERENCE_TARGET_SHA256=132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132
P5_02U_TARGET_DELETED=false
P5_02U_PRODUCTION_RECOVERY_COUNT_AFTER=4
P5_02U_PRODUCTION_RECOVERY_ATTENTION_AFTER=0
P5_02U_MUTATION_MODE_AFTER=disabled
P5_02U_AUTOMATIC_TARGET_DELETE=false
P5_02U_AUTOMATIC_RECOVERY_CLEANUP=false
P5_02U_AUTOMATIC_FOLLOWUP_MUTATION=false
P5_02U_RECOVERY_EVIDENCE_PRESERVED=true
HERMES_MANUAL_OFF=true
P5_02U_GATE_RESULT=PASS
```

Parent/post-state checks also passed:

```text
P5_02U_PARENT_CHILD_EXIT=0
P5_02U_PARENT_SOURCE_SHA256=132FF51D62FD7FD8827D7222E233617E92C55DC21D40FF68164F2238BA0FD132
P5_02U_PARENT_TARGET_SHA256=132FF51D62FD7FD8827D7222E233617E92C55DC21D40FF68164F2238BA0FD132
P5_02U_PARENT_RECOVERY_COUNT=4
P5_02U_CONFIG_UNCHANGED=true
P5_02U_ENV_UNCHANGED=true
P5_02U_INSTALLED_PLUGIN_UNCHANGED=true
P5_02U_EDIT_CANARY_UNCHANGED=true
P5_02U_PARENT_MUTATION_MODE_ABSENT=true
HERMES_MANUAL_OFF=true
P5_02U_PARENT_SOURCE_HASH_MATCH=true
P5_02U_PARENT_TARGET_UNCHANGED=true
P5_02U_PARENT_RECOVERY_COUNT_MATCH=true
```

Accepted new move-source-restore recovery ID:

```text
5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175
```

Accepted restored inbox source file identity:

```text
5e1aeb8a1aeb5d91:67660100000036010000000000000000
```

Accepted production post-state:

- inbox source is present again at the frozen SHA-256;
- vault target remains present and unchanged at the same frozen SHA-256;
- origin P5-02T move recovery remains valid with read-time classification
  `committed_then_changed`;
- new P5-02U restore recovery is valid and committed;
- production recovery inventory is exactly 4 records with zero attention;
- receipt is committed/finalized with no reconciliation requirement;
- approval surface was `cli` and approval choice was `once`;
- authorization is not reusable;
- mutation mode is absent/disabled after the bounded action;
- COMPANION config and `.env` are unchanged;
- installed Orion plugin is unchanged;
- unrelated edit canary is unchanged;
- Hermes remains manual-off;
- vault target was not deleted;
- no automatic recovery cleanup or follow-up mutation occurred.

## Current stop point

P5-02U is complete and accepted.

The committed P5-02T move source has been restored to the accepted Orion inbox,
while the vault target remains present and byte-identical. Production recovery
now contains 4 valid records with zero attention, mutation mode is disabled,
and Hermes remains manual-off.

Target deletion, recovery-record cleanup, and any further production mutation
remain separate explicit authorization boundaries.
