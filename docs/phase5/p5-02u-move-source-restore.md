# P5-02U — Move-Source Restore

Status: **AUTHORIZED / GATE PREPARED / EXECUTION PENDING**

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

## Current stop point

P5-02U is authorized and the guarded gate is prepared. The Windows move-source restore has not yet been executed by repository preparation.
