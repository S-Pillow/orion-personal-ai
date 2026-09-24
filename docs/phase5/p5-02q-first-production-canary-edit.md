# P5-02Q — First Production Canary Edit

Status: **PASS / FIRST PRODUCTION CANARY EDIT ACCEPTED / MUTATION MODE DISABLED / HERMES MANUAL-OFF**

Date: 2026-09-24

Branch:

```text
feature/orion-phase5-p5-02q-first-production-canary-edit
```

Depends on accepted P5-02P readiness at repository head:

```text
d6ed0bb7ef4625344c4a69e3d20c93c130a4e558
```

Installed Orion plugin source remains pinned to the P5-02N-qualified code:

```text
faf8b4787d8e6fb668eb5e9d754104910b4b401a
```

## Owner authorization

The owner explicitly authorized the start of P5-02Q.

That authorization is limited to exactly one Orion production action:

```text
action: edit_note
relative target: _Orion-P5-Canary.md
canonical target: C:\Personal\Me\_Orion-P5-Canary.md
```

Frozen pre-action Windows file identity:

```text
5e1aeb8a1aeb5d91:cba20a00000012000000000000000000
```

Frozen before SHA-256:

```text
ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c
```

Frozen after SHA-256:

```text
86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19
```

Frozen exact diff SHA-256:

```text
6642d44372449d01e1ec3f5d325bd2b372f52cc58610293bcccf0e4e4ec996e8
```

Exact diff:

```diff
--- vault/_Orion-P5-Canary.md
+++ vault/_Orion-P5-Canary.md
@@ -1,3 +1,3 @@
 # Orion Phase 5 Canary
-state: before
+state: after
 gate: first-production-edit
```

No other target, action, content, or diff is authorized by P5-02Q.

## Execution architecture

P5-02Q deliberately does not use an LLM to select the tool.

The runner calls Hermes `model_tools.handle_function_call()` with the exact
registered tool name:

```text
orion_vault_apply_plan
```

and only the exact preview `plan_token`.

This is the same deterministic registered-dispatch path proven in P5-02P.

The live execution sequence is:

1. require Hermes manual-off;
2. require clean operator repository state on the P5-02Q branch;
3. require installed plugin code/manifest to exactly match qualified P5-02N;
4. require installed plugin doctor PASS;
5. require production recovery inventory to be empty;
6. require mutation mode to be absent from the parent process and persisted environment;
7. require the exact frozen canary bytes, SHA-256, and Windows file identity;
8. create the exact side-effect-free preview while mutation remains disabled;
9. require exact target, before hash, after hash, file ID, and diff hash;
10. set `ORION_P5_MUTATION_MODE=mutation_enabled` only in the child process;
11. dispatch exactly `orion_vault_apply_plan`;
12. present one genuine Hermes approval prompt;
13. owner must select **ONCE** only;
14. private production executor performs its own post-approval stale checks;
15. executor writes durable schema-v2 recovery data before the protected file replacement;
16. executor rechecks file identity/hash immediately before replacement;
17. executor performs the qualified Windows replacement;
18. executor verifies the post-write hash;
19. executor commits recovery manifest and correlation receipt;
20. child removes `ORION_P5_MUTATION_MODE` immediately after dispatch;
21. gate verifies exact after bytes/hash and one clean committed recovery record;
22. parent verifies config, `.env`, installed plugin, parent environment, and manual-off state remain unchanged.

The Hermes gateway is not required and is not started.

## Recovery and failure policy

P5-02Q never automatically restores the canary.

This is intentional.

If the apply is denied or fails before mutation, the gate stops.

If a failure occurs after recovery preparation or after the protected
replacement, the gate:

- leaves the canary in its observed state;
- preserves the recovery directory;
- prints the observed target hash and recovery count;
- leaves mutation mode absent in the parent process;
- does not delete or rewrite recovery evidence;
- stops for read-only reconciliation.

A restore is a distinct production mutation and requires a later separately
authorized gate.

## Expected successful recovery state

A successful P5-02Q must produce exactly one recovery record whose:

- recovery ID equals the immutable preview plan token;
- recovery record is valid;
- `needs_attention=false`;
- manifest state is `committed`;
- recovery classification is `committed`;
- backup hash equals the frozen before SHA-256;
- target hash equals the frozen after SHA-256;
- receipt state is `committed`;
- receipt is finalized;
- receipt reconciliation is not required;
- approval surface is `cli`;
- approval choice is `once`;
- authorization is not reusable.

Expected recovery directory contents are exactly:

```text
manifest.json
original.bin
receipt.json
```

The recovery record is retained after success for the later restore gate.

## Prepared operator artifacts

```text
scripts/phase5/p5-02q-first-production-canary-edit.ps1
scripts/phase5/p5-02q-first-production-canary-edit.py
```

The PowerShell gate requires the literal token:

```text
I_AUTHORIZE_P5_02Q_EXACT_CANARY_EDIT
```

This token is only an operator-script scope guard. The actual mutation still
requires the separate live Hermes human `ONCE` decision.

## Stop conditions

Stop before approval if any of these fail:

- branch/worktree exactness;
- qualified installed source;
- plugin doctor;
- config baseline;
- no ambient mutation/disposable settings;
- manual-off;
- empty recovery inventory;
- exact canary path;
- exact before bytes/hash;
- exact Windows file identity;
- exact preview target/hash/diff contract.

At the approval prompt, stop/deny unless the displayed target and diff are
exactly the frozen contract above.

Only **ONCE** is acceptable.

## Observed live result — PASS

The authorized P5-02Q production canary edit completed successfully on
2026-09-24.

Observed apply result:

```text
P5_02Q_PRODUCTION_CANARY_EDIT=PASS
P5_02Q_APPLY_SUCCESS=true
P5_02Q_MUTATION_PERFORMED=true
P5_02Q_RECOVERY_REQUIRED=false
P5_02Q_RECOVERY_ID=33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f
P5_02Q_RECOVERY_RECORD_VALID=true
P5_02Q_RECOVERY_MANIFEST_STATE=committed
P5_02Q_RECOVERY_CLASSIFICATION=committed
P5_02Q_RECEIPT_STATE=committed
P5_02Q_RECEIPT_FINALIZED=true
P5_02Q_RECEIPT_RECONCILIATION_REQUIRED=false
P5_02Q_APPROVAL_SURFACE=cli
P5_02Q_APPROVAL_CHOICE=once
P5_02Q_AUTHORIZATION_REUSABLE=false
P5_02Q_PRODUCTION_RECOVERY_COUNT_AFTER=1
P5_02Q_PRODUCTION_RECOVERY_ATTENTION_AFTER=0
```

Committed recovery directory:

```text
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery\33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f
```

Post-mutation canary evidence:

```text
P5_02Q_CANARY_POST_FILE_ID=5e1aeb8a1aeb5d91:19c10700000020000000000000000000
P5_02Q_CANARY_POST_SHA256=86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19
```

The post-edit Windows file identity differs from the frozen pre-edit identity.
That is not treated as a failure: the pre-edit identity was the race guard for
the original target immediately before the protected replacement. Acceptance
after replacement is based on the exact frozen after-bytes/hash plus the valid
committed recovery and receipt state.

Observed parent/post-state checks:

```text
P5_02Q_PARENT_CHILD_EXIT=0
P5_02Q_PARENT_CANARY_SHA256=86E94184EF6FF2A80F5CDFA04749C42328079E029D153D3A23D42EAB05059E19
P5_02Q_PARENT_RECOVERY_COUNT=1
P5_02Q_PARENT_AUTOMATIC_RESTORE=false
P5_02Q_CONFIG_UNCHANGED=true
P5_02Q_ENV_UNCHANGED=true
P5_02Q_INSTALLED_PLUGIN_UNCHANGED=true
P5_02Q_PARENT_MUTATION_MODE_ABSENT=true
HERMES_MANUAL_OFF=true
P5_02Q_PARENT_AFTER_HASH_MATCH=true
P5_02Q_PARENT_RECOVERY_COUNT_MATCH=true
P5_02Q_GATE_RESULT=PASS
```

No automatic restore was attempted. The committed recovery record is retained
as production evidence and as the input to a later separately authorized
restore qualification.

## Acceptance

P5-02Q is accepted.

Accepted production state:

- canary is in the frozen `state: after` form;
- canary SHA-256 is
  `86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19`;
- current canary Windows file identity is
  `5e1aeb8a1aeb5d91:19c10700000020000000000000000000`;
- exactly one committed production recovery record exists;
- that record has zero attention/reconciliation requirement;
- mutation mode is absent/disabled after the bounded action;
- COMPANION config and `.env` are unchanged;
- installed plugin bytes are unchanged;
- Hermes remains manual-off.

## Acceptance boundary

P5-02Q acceptance means exactly one production `edit_note` canary operation
completed through the registered guarded wrapper, fresh Hermes human-once
approval, qualified Windows replacement path, and committed recovery evidence.

P5-02Q does not authorize:

- a second edit;
- restore;
- move;
- delete;
- persistent mutation mode;
- session/always approval;
- any other vault or inbox target;
- recovery-record deletion;
- Hermes/runtime upgrades.

A successful P5-02Q leaves the canary in the `state: after` form and leaves
one committed recovery record for the separately authorized restore phase.
