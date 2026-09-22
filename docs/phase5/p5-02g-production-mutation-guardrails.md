# P5-02G Production Mutation Guardrails

Status: **SOURCE-ONLY / WINDOWS-VERIFIED / LIVE MUTATION PROHIBITED**
Date: 2026-09-22
Branch: `feature/orion-phase5-p5-02g-production-guardrails`
Depends on: P5-02A through P5-02F

## Purpose

P5-02G closes the source-level production-boundary blockers identified by the P5-02F activation-readiness review without installing or enabling the plugin in the live COMPANION profile.

The central rule remains:

> A production mutation requires an explicit production mode, validated roots, one fresh Hermes ALLOW ONCE owned by the final handler, post-approval stale revalidation, durable recovery/receipt preparation, and verified protected execution.

The public registered apply handler remains fail-closed throughout this ticket.

## Accepted baseline entering P5-02G

Windows evidence accepted before this branch:

- `test_p5*.py`: **86/86 passed**;
- installed-Hermes dispatcher probe: **2/2 passed**;
- plugin doctor: **PASS**, 4 tools / 2 hooks;
- exact HUD approval display accepted;
- real Hermes fresh-once no-write path accepted;
- disposable edit/move/restore transactions, recovery reconciliation, restart receipts, and replay refusal accepted.

## Production mutation mode

New environment contract:

```text
ORION_P5_MUTATION_MODE=disabled | preview_only | mutation_enabled
```

Behavior:

- missing/blank -> `disabled`;
- unknown value -> invalid/fail-closed;
- `disabled` -> no production mutation;
- `preview_only` -> no production mutation;
- `mutation_enabled` -> mutation is only *eligible*; every other production guard still applies.

This variable is not automatically set by the plugin.

The browser/HUD has no code path that widens this mode.

## Production recovery root

Production recovery storage is separate from the disposable fixture root:

```text
ORION_P5_PRODUCTION_RECOVERY_ROOT
```

There is no default.

The validator refuses production readiness when the root is absent.

The plugin does not auto-create the production recovery root.

## Production root preflight

`_validate_production_roots()` is read-only.

It verifies:

- vault root exists;
- inbox root exists;
- production recovery root exists;
- no root path contains a symlink/junction/reparse component;
- vault/inbox/recovery roots are disjoint after resolution;
- Windows raw-path overlap is rejected as an additional alias guard;
- recovery storage is on a fixed local Windows volume;
- the current identity can list the recovery directory and create a child directory;
- the recovery DACL has no allowed write-like ACE for:
  - Everyone (`S-1-1-0`);
  - Authenticated Users (`S-1-5-11`);
  - BUILTIN\Users (`S-1-5-32-545`).

Standard allowed ACEs and object-specific allowed ACEs are parsed.

Conditional/callback allowed ACEs fail closed as unsupported rather than being silently ignored.

The validator does not repair ACLs.

## Recovery startup inventory

`_enumerate_production_recovery_records()` performs a bounded, read-only immediate-child scan.

Properties:

- hard maximum: **128 entries** per call;
- caller may request a lower positive limit;
- uses bounded `os.scandir()`, not whole-directory sorting;
- does not follow directory symlinks;
- invalid/non-64-hex/reparse entries are surfaced as attention-required;
- valid records are inspected through the shared recovery and receipt validators;
- unresolved/prepared/divergent/duplicate/corrupt states are surfaced;
- scan truncation is explicit.

The production mutation preflight refuses mutation when:

- the inventory is truncated; or
- any recovery entry needs attention.

This prevents a new mutation from being layered over unresolved transaction state.

## Windows edit object identity parity

Normal edit preview now binds the target Windows file ID, matching restore-edit hardening.

On Windows:

- preview reads and stores `target_file_id`;
- revalidation checks canonical path + file ID + current SHA-256;
- the disposable edit executor now also rejects same-path/same-bytes file replacement;
- the production candidate repeats file-ID/hash checks immediately before native `ReplaceFileW`.

This closes the edit/restore identity-policy gap identified by P5-02F.

## Single approval owner

P5-02G resolves the double-approval question.

For a valid apply plan:

- in disabled/preview-only mode, the existing `pre_tool_call` approval contract remains unchanged;
- in explicit `mutation_enabled` mode, `pre_tool_call` validates the plan but returns no approval directive;
- the private final production candidate then owns exactly one Hermes generic approval request.

Invalid/unknown/expired plans still receive a blocking pre-tool directive.

The final production candidate accepts only fresh handler-side evidence produced by:

- exact approval message;
- fresh private attempt key;
- matching `post_approval_response`;
- human `choice=once`;
- supported CLI/gateway surface;
- generic gate result `approved=true`.

Session/always, yolo/cached/automatic approval, missing callback, deny, or timeout cannot create approved evidence.

## Truthful approval wording

When `mutation_enabled` is explicit, the approval card says:

> This one-time approval may be used only by the private production mutation candidate for this exact plan. Registered/live apply remains fail-closed.

Schema-v2 receipts bind that exact production wording plus the exact diff hash.

Legacy/disposable schema-v1 receipts retain their original expected wording.

## Production schema v2

The private production candidate writes recovery manifests and receipts with:

```text
schema_version = 2
recovery_id = plan_token
```

Shared inspectors accept schema 1 for prior source/disposable evidence and schema 2 for the production candidate.

For schema 2, the recovery manifest must explicitly bind `recovery_id == plan_token`.

The receipt remains non-authorizing.

## Private production apply candidate

`_execute_production_plan_candidate()` is implemented but **unregistered**.

It never calls the disposable-root guard.

It requires:

1. explicit `mutation_enabled`;
2. successful production root/ACL/local-volume preflight;
3. bounded recovery inventory with zero attention-required records;
4. live preview plan;
5. fresh handler-side Hermes ALLOW ONCE;
6. post-human-decision stale revalidation;
7. a second bounded recovery inventory check;
8. durable schema-v2 recovery/receipt preparation;
9. final state/object checks immediately before the protected filesystem call;
10. postcondition verification.

Supported private actions:

- `edit_note`;
- `move_draft`;
- `restore_edit`;
- `restore_move_source`.

## Production edit

Execution uses the already-qualified primitives:

- durable recovery backup;
- schema-v2 prepared manifest/receipt;
- same-directory exclusive temp;
- final Windows file-ID/hash check;
- native `ReplaceFileW`;
- post-write SHA-256 verification;
- committed manifest then committed receipt.

Any prepared record left by a pre-write failure remains visible to recovery inventory rather than being silently discarded.

## Production move

Execution reuses:

- Windows held source handle + source file ID;
- exclusive target creation;
- target hash verification;
- held-source final hash check;
- handle-based delete on Windows;
- schema-v2 recovery/receipt.

If a target race wins after preparation, Orion does not overwrite it and the prepared transaction remains attention-required.

## Production historical restore

The existing restore preview/revalidation logic is generalized to already-validated roots.

`_preview_production_restore_candidate()` is private/unregistered and may operate in preview-only mode.

Production restore execution:

- requires a new fresh ALLOW ONCE;
- creates a new schema-v2 recovery/receipt;
- preserves origin recovery linkage;
- edit restore uses the atomic replacement primitive;
- move-source restore uses exclusive creation;
- the reference vault target is not deleted by move-source restore.

## Replay and restart behavior

Plan consumption remains one-use.

Receipts remain non-authorizing.

A restart can inspect schema-v2 recovery/receipt state without reconstructing human approval authority.

Receipt-finalization failure after a verified filesystem change is surfaced as reconciliation-required rather than replaying the protected operation.

## Registered/live boundary

Still unchanged:

```text
orion_vault_apply_plan -> apply_plan_placeholder
```

The placeholder returns:

```text
p5_01_mutation_not_authorized
```

The private production candidate is not registered.

The plugin manifest remains 4 tools / 2 hooks.

## P5-02G test delta

New `test_p5_02g_guardrails.py` contains **30 tests** covering:

- mutation-mode parsing/fail-closed default;
- preview-only vs mutation-enabled preflight;
- required recovery root;
- root overlap rejection;
- broad ACL rejection;
- fixed-local-storage requirement;
- access-probe failure;
- committed and unresolved recovery inventory;
- bounded/truncated inventory;
- invalid inventory limits/entries;
- Windows edit file-ID binding;
- same-bytes/different-file-object edit refusal;
- read-only native Windows local/access/ACL probe smoke;
- pre-tool single-approval ownership;
- private/unregistered production candidate boundary;
- preview-only production refusal before approval;
- DENY -> zero mutation;
- ALLOW ONCE edit -> schema-v2 committed transaction;
- stale-after-approval refusal;
- Windows same-bytes swap after approval;
- receipt-finalization failure reconciliation;
- replay refusal before another approval;
- production move without disposable opt-in;
- target appearance after approval;
- unresolved recovery blocking a new action;
- production historical edit restore as a new schema-v2 transaction.

Expected full discovery:

- 16 P5-01;
- 10 P5-02A;
- 36 P5-02B/P5-02C/P5-02D;
- 24 P5-02E;
- 30 P5-02G;

**Total: 116 tests.**

Windows operator verification is now **PASS**:

- full `test_p5*.py`: **116/116 passed** in 2.281s;
- installed-Hermes dispatcher probe: **2/2 passed** in 0.079s;
- plugin doctor: **PASS**, manifest `orion-vault-actions 0.1.0`, 4 tools / 2 hooks;
- no gateway/HUD fixture or persistent probe process was started by these commands.

The known Hermes SQLite 3.40.1 WAL-reset warning remained non-fatal and Hermes continued to use `journal_mode=DELETE`. It remains separate runtime hygiene.

This accepts the P5-02G production-shaped source guardrails on Windows.

## Accepted boundary after PASS

The following are now source-qualified:

- fail-closed production mutation-mode parsing;
- explicit production recovery-root validation;
- fixed-local/access/DACL checks;
- bounded unresolved-recovery discovery;
- Windows edit file-ID parity;
- single handler-side approval ownership in mutation-enabled mode;
- post-approval stale revalidation;
- schema-v2 recovery/receipt generation;
- private production-shaped edit/move/restore execution against temporary roots;
- replay refusal and restart reconciliation.

Still **not** authorized or activated:

- live COMPANION plugin installation;
- persistent mutation-mode configuration;
- creation/ACL modification of a real production recovery root;
- replacing `apply_plan_placeholder` in the registered tool surface;
- Hermes lifecycle changes for this plugin;
- any real vault/inbox mutation.

The next live-facing gate, if separately authorized, is a **preview-only COMPANION installation** of an exact approved source commit with mutation mode disabled/preview-only and rollback captured before any restart.

A real-vault mutation remains a later explicit authorization unit after installed-runtime disposable qualification.

## Explicitly out of scope / not performed

P5-02G does not:

- install/copy the plugin into the COMPANION profile;
- edit live Hermes plugin configuration;
- set production mutation mode persistently;
- choose/create the real production recovery root;
- change Windows ACLs;
- restart/start/stop Hermes;
- register the private production executor;
- mutate `C:\Personal\Me`;
- mutate `C:\Personal\Orion-Inbox`;
- consume VT/API quota or make unrelated network calls;
- update Hermes/SQLite dependencies.
