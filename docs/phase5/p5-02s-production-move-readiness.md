# P5-02S — Production Move Readiness

Status: **PASS / MOVE READINESS COMPLETE / NO PRODUCTION MOVE AUTHORIZED**

Date: 2026-09-24

Branch:

```text
feature/orion-phase5-p5-02s-production-move-readiness
```

Baseline: accepted P5-02R closure head
`6ec5f661719fd86f286c7166280d5da7d887154c`.

Installed plugin source remains pinned to qualified P5-02N code
`faf8b4787d8e6fb668eb5e9d754104910b4b401a`.

## Purpose

P5-02S prepares and qualifies the first production `move_draft` without
executing the move itself. Under separate authorization, P5-02S-A created the
controlled inbox fixture and P5-02S-B completed read-only move readiness.
P5-02T remains a separate production-mutation authorization boundary.

P5-02S was designed and executed under the then-controlling PRD v2.8
document-action contract. Approved/current PRD v2.9 now supersedes v2.8 as the
repository baseline; that PRD publication does not itself authorize P5-02T:

- new drafts belong in the dedicated Orion inbox;
- moving a draft outside the inbox requires approval;
- preview must be side-effect-free;
- the approval payload must contain the exact canonical operation;
- Hermes generic approval must be reached before mutation;
- approved operations must be atomic and recoverable;
- stale/denied actions must make no vault change;
- deletion remains a separate explicit approval class.

## Why move is a separate gate

A production move has a larger side-effect surface than an edit:

1. source exists in the Orion inbox;
2. target must be absent in the vault;
3. the source object must remain stable;
4. a new vault object is created;
5. target bytes must be verified;
6. the source is then removed;
7. recovery/receipt evidence must make the two-sided operation recoverable.

The qualified production executor already implements that shape:

- Windows held source handle and file-ID check;
- source hash revalidation;
- durable `source.bin`, manifest, and receipt before mutation;
- exclusive target creation;
- target hash verification;
- held-source reread immediately before source deletion;
- delete-mark under the held Windows source handle;
- final source-absent + target-hash postcondition;
- committed schema-v2 recovery and receipt.

P5-02S does not execute those mutations. It freezes the fixture and preview
contract that a later P5-02T gate may use.

## Accepted baseline before fixture creation

P5-02R left:

- canary edit fixture restored to its original before-hash;
- production mutation mode absent/disabled;
- Hermes manual-off;
- COMPANION config and `.env` unchanged;
- installed plugin unchanged;
- exactly two valid production recovery records;
- recovery attention count zero;
- origin P5-02Q edit record valid as `committed_then_changed`;
- P5-02R restore record valid as `committed`.

Existing recovery IDs:

```text
33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f
1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27
```

## Proposed controlled move fixture

The fixture is intentionally a new Orion draft in the dedicated inbox.

Source:

```text
C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md
```

Future target:

```text
C:\Personal\Me\_Orion-P5-Move-Canary.md
```

Both use the relative path:

```text
_Orion-P5-Move-Canary.md
```

Exact UTF-8/no-BOM/LF fixture bytes:

```text
---
orion_draft: true
status: draft
date: 2026-09-24
origin: p5-02s-controlled-fixture
---
# Orion Phase 5 Move Canary
state: inbox
gate: first-production-move
```

with one trailing LF.

Frozen source SHA-256:

```text
132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132
```

The future target must be absent before preview and before mutation.

## Frozen move preview

The registered move preview must produce exactly:

```diff
--- /dev/null
+++ vault/_Orion-P5-Move-Canary.md
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

Frozen exact diff SHA-256:

```text
61e4f48a0964aec273217a87dc3d7ac706f2a6525886420ee5e6d80fcb26a587
```

The Windows source file identity cannot be frozen until the fixture exists.
P5-02S-B captures it and requires the registered preview plan to contain that
same identity.

## P5-02S-A — controlled inbox fixture creation

Prepared script:

```text
scripts/phase5/p5-02s-create-move-fixture.ps1
```

This script is **not authorized by preparing this branch**.

If separately authorized, it:

- requires Hermes manual-off;
- requires accepted config baseline;
- requires the restored P5-02R edit-canary hash;
- requires the two accepted recovery IDs and no extra recovery directory;
- requires no ambient production/disposable mutation settings;
- requires both proposed move source and target to be absent;
- creates only the controlled inbox draft with `CreateNew`;
- flushes the fixture bytes;
- verifies the frozen source SHA-256;
- verifies the vault target remains absent;
- does not call the Orion plugin;
- does not enable mutation;
- does not start Hermes;
- does not touch production recovery contents.

Literal operator token:

```text
I_AUTHORIZE_P5_02S_MOVE_FIXTURE_CREATE
```

## Observed P5-02S-A controlled move fixture creation — PASS

The separately authorized controlled inbox fixture creation completed
successfully on the accepted Windows environment.

Observed result:

```text
P5_02S_MOVE_FIXTURE_CREATE=PASS
P5_02S_SOURCE_CANONICAL_PATH=C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md
P5_02S_TARGET_CANONICAL_PATH=C:\Personal\Me\_Orion-P5-Move-Canary.md
P5_02S_SOURCE_SHA256=132FF51D62FD7FD8827D7222E233617E92C55DC21D40FF68164F2238BA0FD132
P5_02S_TARGET_STATE=absent
P5_02S_FIXTURE_UTF8_NO_BOM=true
P5_02S_FIXTURE_NEWLINES=LF
P5_02S_PRODUCTION_RECOVERY_COUNT=2
P5_02S_CONFIG_UNCHANGED=true
P5_02S_ENV_UNCHANGED=true
P5_02S_INSTALLED_PLUGIN_MANIFEST_UNCHANGED=true
PRODUCTION_MUTATION_MODE=disabled
HERMES_MANUAL_OFF=true
P5_02S_MOVE_NOT_EXECUTED=true
```

The fixture exactly matches the frozen source-hash contract.

This was a direct operator-created controlled inbox fixture, not an Orion
`move_draft` mutation. No Orion apply tool was invoked, mutation mode remained
disabled, the vault target remained absent, the accepted P5-02Q/P5-02R recovery
inventory remained at two records, and Hermes remained manual-off.

The controlled source fixture must now be treated as a Phase 5 test asset. Do
not edit, rename, move, or delete it outside the later explicitly authorized
readiness/move/restore gates.

## P5-02S-B — read-only move readiness

Prepared scripts:

```text
scripts/phase5/p5-02s-move-readiness.ps1
scripts/phase5/p5-02s-move-readiness.py
```

This gate is also separately authorization-token guarded.

It must prove:

- installed plugin code/manifest exact-match the P5-02N-qualified source;
- installed plugin doctor passes;
- Hermes remains manual-off;
- mutation mode is absent/disabled;
- recovery inventory still contains exactly the two accepted P5-02Q/P5-02R
  records and zero attention state;
- origin edit record still reads `committed_then_changed`;
- restore record still reads `committed`;
- source fixture canonical path and exact bytes/hash match;
- target canonical path is exact and target remains absent;
- source Windows file identity can be read;
- registered `orion_vault_preview_move_draft` dispatch succeeds;
- preview action is exactly `move_draft`;
- source/target canonical paths are exact;
- source SHA/file-ID match the live fixture;
- target state is `absent`;
- exact preview diff/hash match this frozen contract;
- source bytes/file-ID remain unchanged after preview;
- target remains absent;
- recovery inventory remains unchanged.

Literal operator token:

```text
I_AUTHORIZE_P5_02S_MOVE_READINESS
```

## Observed P5-02S-B read-only move readiness — PASS

The separately authorized read-only production move readiness gate completed
successfully on the accepted Windows environment.

Observed installed/runtime checks:

```text
P5_02S_READINESS_PRECHECK=PASS
P5_02S_INSTALLED_SOURCE_MATCH=true
P5_02S_INSTALLED_PLUGIN_DOCTOR=PASS
P5_02S_VERIFIER_COMPILE=PASS
P5_02S_HERMES_MANUAL_OFF=true
P5_02S_MOVE_READINESS=PASS
P5_02S_MUTATION_MODE=disabled
P5_02S_MUTATION_ALLOWED=false
P5_02S_RECOVERY_INVENTORY_COUNT=2
P5_02S_RECOVERY_ATTENTION_COUNT=0
```

Frozen source/target identity and move-preview contract:

```text
P5_02S_SOURCE_RELATIVE_PATH=_Orion-P5-Move-Canary.md
P5_02S_SOURCE_CANONICAL_PATH=C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md
P5_02S_SOURCE_FILE_ID=5e1aeb8a1aeb5d91:eec0070000001f000000000000000000
P5_02S_SOURCE_SHA256=132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132
P5_02S_TARGET_RELATIVE_PATH=_Orion-P5-Move-Canary.md
P5_02S_TARGET_CANONICAL_PATH=C:\Personal\Me\_Orion-P5-Move-Canary.md
P5_02S_TARGET_STATE=absent
P5_02S_MOVE_DIFF_SHA256=61e4f48a0964aec273217a87dc3d7ac706f2a6525886420ee5e6d80fcb26a587
```

Exact registered move preview:

```diff
--- /dev/null
+++ vault/_Orion-P5-Move-Canary.md
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

Observed side-effect-free/post-state checks:

```text
P5_02S_PREVIEW_MUTATION=false
P5_02S_SOURCE_UNCHANGED=true
P5_02S_TARGET_STILL_ABSENT=true
P5_02S_READINESS_WRAPPER=PASS
P5_02S_MUTATION_INVOCATION=false
P5_02S_CONFIG_UNCHANGED=true
P5_02S_ENV_UNCHANGED=true
P5_02S_INSTALLED_PLUGIN_UNCHANGED=true
HERMES_MANUAL_OFF=true
```

The Hermes process also emitted the already-known linked SQLite 3.40.1
WAL-reset warning and used `journal_mode=DELETE`. That runtime-maintenance
warning did not affect this read-only gate and remains outside P5-02S scope.

P5-02S readiness is therefore complete:

- controlled move fixture exists and matches the frozen bytes/hash;
- actual Windows source file identity is frozen;
- registered move preview exactly matches the frozen source/target/diff contract;
- target remains absent;
- production recovery remains at the accepted two-record/zero-attention baseline;
- mutation mode remains disabled;
- no apply/mutation invocation occurred;
- Hermes remains manual-off.

P5-02T remains a separate production-mutation authorization boundary.

## Planned later gates — not authorized

### P5-02T — first production move

Only after P5-02S-A and P5-02S-B pass.

Expected design:

1. re-run the P5-02S readiness checks immediately before execution;
2. freeze the actual Windows source file identity;
3. create the exact registered move preview while mutation remains disabled;
4. independently validate source, target, SHA, file ID, and exact diff;
5. enable `ORION_P5_MUTATION_MODE=mutation_enabled` in the child only;
6. dispatch exactly `orion_vault_apply_plan`;
7. require one fresh Hermes human **ONCE**;
8. allow the qualified executor to hold/revalidate the source, prepare recovery,
   exclusively create/verify target, recheck source, remove source, and verify
   the final two-sided postcondition;
9. require a new committed move recovery/receipt record;
10. remove mutation mode and remain manual-off.

Expected success state:

- inbox source absent;
- vault target present with exact frozen source SHA;
- new move recovery record committed;
- existing recovery records remain valid;
- attention count remains zero.

### P5-02U — move-source restore

Separately authorized after P5-02T.

It should use the committed move recovery record's `source.bin` through the
qualified production `restore_move_source` path.

A successful move-source restore recreates the inbox source but does **not**
silently delete the vault target. Deleting that target would be a separate
delete action and OR-NOTE-008 requires separate explicit approval.

This distinction is important: restore of the removed source and deletion of
the created vault target are not one authorization.

## Current stop point

P5-02S-A and P5-02S-B are complete and accepted.

The controlled source fixture exists at
`C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md` with frozen SHA-256
`132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132`
and frozen Windows file identity
`5e1aeb8a1aeb5d91:eec0070000001f000000000000000000`.

The future target `C:\Personal\Me\_Orion-P5-Move-Canary.md` remains absent.
Production recovery remains at exactly two accepted records with zero attention.
Mutation mode remains disabled and Hermes remains manual-off.

No production move has been executed or authorized by P5-02S. Do not edit,
rename, move, or delete the controlled source fixture outside a separately
authorized later Orion gate.

P5-02T is the next separate authorization boundary: the first bounded production
`move_draft` against exactly the frozen source/target/hash/file-ID/diff
contract. P5-02U move-source restore remains separately gated after P5-02T.
