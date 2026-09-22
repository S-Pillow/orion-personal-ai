# P5-02D Restart-Safe Approval / Recovery Receipts

Status: **SOURCE-ONLY / WINDOWS-VERIFIED / NON-AUTHORIZING**
Date: 2026-09-22
Depends on: P5-02A approval integrity, P5-02B Windows mutation hardening, P5-02C recovery inspection + restore preview

## Purpose

P5-02D makes the approval/recovery story survive process restart.

The receipt answers:

- which immutable plan was approved;
- which exact approval-card text/diff was shown;
- which one-time approval attempt matched;
- which approval surface returned the decision;
- which recovery artifact belongs to the plan;
- whether the receipt was only prepared or fully finalized;
- what the recovery inspector currently says happened.

It does **not** authorize any future operation.

A receipt is evidence. It is not a capability token.

## Accepted baseline entering this slice

The Windows operator baseline before P5-02D is:

- 55/55 `test_p5*.py` tests passed;
- 2/2 installed-Hermes dispatcher probes passed;
- plugin doctor passed with 4 tools / 2 hooks;
- restore preview + stale revalidation accepted;
- registered apply handler still refuses mutation;
- no restore executor exists.

The known Hermes SQLite 3.40.1 WAL-reset warning remains a separate runtime-hygiene issue; Hermes falls back to `journal_mode=DELETE`.

## Structured one-time approval evidence

The source candidate now has `_fresh_once_approval_evidence()`.

A successful result contains:

- `approved: true`;
- a fresh random `attempt_id`;
- the immutable `plan_token`;
- `choice: once`;
- `surface: cli | gateway`;
- the exact bounded `approval_message`;
- `approval_message_sha256`;
- `authorization_reusable: false`.

It deliberately omits the private Hermes rule key and pattern key.

The evidence object exists only after:

1. the plan still exists and its exact approval summary validates;
2. redaction leaves the summary unchanged;
3. the request enters Hermes generic approval;
4. the matching `post_approval_response` hook observes a fresh `once`;
5. the gate itself also returns `approved=true`.

Session/always, missing observer, mismatched description, late callback, failed gate, redaction mismatch, or attempt saturation do not produce approved evidence.

The existing boolean `_probe_fresh_once_approval()` remains as a compatibility wrapper around this stronger structured result.

## Durable receipt timing

For the disposable candidate only, `_execute_disposable_plan_candidate(..., approval_evidence=...)` may now persist a receipt.

The sequence is:

1. validate the supplied approval evidence against the still-live immutable plan;
2. revalidate source/target state;
3. create recovery directory;
4. durably write backup bytes;
5. durably write the `prepared` recovery manifest;
6. durably create `receipt.json` in `prepared` state;
7. only then enter the protected filesystem mutation;
8. verify postconditions;
9. advance recovery manifest to `committed`;
10. advance receipt to `committed`.

Invalid approval evidence is rejected before recovery creation or document mutation.

If the process fails after step 6, the on-disk prepared receipt survives and can be reconciled after restart.

Existing disposable tests that omit `approval_evidence` remain valid. This optional parameter is a source-prototype seam only. A future production mutator must require fresh evidence rather than treating it as optional.

## Receipt schema

Current candidate shape:

```json
{
  "schema_version": 1,
  "receipt_type": "orion_vault_action",
  "recovery_id": "<64-hex plan token>",
  "plan_token": "<64-hex plan token>",
  "plan": {
    "...": "public immutable plan fields only"
  },
  "approval": {
    "attempt_id": "<32-hex non-authorizing correlation id>",
    "surface": "gateway",
    "choice": "once",
    "approval_message": "<exact bounded approval text including diff>",
    "approval_message_sha256": "<sha256>",
    "authorization_reusable": false
  },
  "backup_file": "original.bin | source.bin",
  "backup_sha256": "<sha256>",
  "state": "prepared | committed",
  "created_at_utc": "...Z",
  "updated_at_utc": "...Z",
  "final_classification": "committed"
}
```

Private cached fields such as `_approval_diff` and `_proposed_bytes` are not copied into the public plan snapshot.

The exact approval message is persisted because a hash alone is not useful for restart-time audit if the in-memory preview has disappeared.

## Restart validation

`_inspect_disposable_receipt_candidate()` is read-only and does not depend on:

- `_PREVIEWS`;
- `_PREVIEW_TIMES`;
- `_APPROVAL_ATTEMPTS`.

It validates:

- recovery ID format;
- recovery directory containment and no reparse point;
- receipt schema/type/state;
- receipt recovery ID == plan token;
- persisted public plan recomputes to the same immutable plan token;
- approval attempt ID format;
- exact `once` choice;
- supported approval surface;
- `authorization_reusable=false`;
- approval message length;
- approval message SHA-256;
- approval-card fixed target/hash wording against the immutable plan;
- exact stored diff hash against the plan's `diff_sha256`;
- backup filename, existence, no reparse point, and hash;
- correlation between receipt action/backup and the recovery manifest/inspector.

A committed receipt must carry `final_classification=committed`.
A prepared receipt must not pretend to have a final classification.

The inspector returns both:

- persisted receipt state;
- current recovery classification.

This matters because a prepared receipt can survive a crash after the filesystem operation. Example:

```text
receipt_state = prepared
current_classification = applied_unfinalized
receipt_reconciliation_required = true
```

No content mutation is needed to determine that state.

## Non-replay rule

A valid receipt must never satisfy a later approval attempt.

The receipt contains no Hermes rule key and no live approval-attempt entry. A later call that merely returns `approved=true` without a new matching `post_approval_response(... choice="once")` still fails.

This is explicitly covered by regression tests.

## Tamper behavior

The inspector fails closed when:

- `authorization_reusable` is changed;
- plan/token binding no longer matches;
- approval message/hash mismatch;
- approval target/hash wording is changed even if the attacker recomputes the message hash;
- stored diff no longer hashes to the immutable plan's `diff_sha256`;
- backup bytes no longer match the receipt/recovery record;
- receipt state/final-classification pairing is invalid.

This is integrity checking under the local recovery-store trust model. It is not a cryptographic signature or remote-attestation system. Production activation still requires restrictive Windows ACLs on the recovery root.

## Source tests in this slice

P5-02D adds/extends coverage for:

- structured non-reusable fresh-once approval evidence;
- exact approval-message persistence and hashing;
- committed receipt surviving cleared in-memory caches;
- prepared receipt surviving an applied-but-unfinalized failure;
- invalid approval evidence blocking before recovery/mutation;
- receipt field tamper failing closed;
- approval-card target/text tamper failing even when its message hash is recomputed;
- a valid receipt failing to authorize a later attempt;
- receipt finalized vs reconciliation-required state reporting.

Current expected `test_p5*.py` discovery is **62 tests**:

- 16 P5-01;
- 10 P5-02A;
- 36 P5-02B/P5-02C/P5-02D.

Windows operator verification is now **PASS**:

- full `test_p5*.py`: **62/62 passed** in 0.841s;
- installed-Hermes dispatcher probe: **2/2 passed** in 0.090s;
- plugin doctor: **PASS**, manifest `orion-vault-actions 0.1.0`, 4 tools / 2 hooks;
- no gateway/HUD fixture or persistent probe process was started by these commands.

The known Hermes SQLite 3.40.1 WAL-reset warning remained non-fatal and Hermes used `journal_mode=DELETE`. It remains separate runtime hygiene.

This accepts the restart-safe non-authorizing receipt layer on Windows.

## Next source gate

Perform a **restore-execution design review** that maps the already-verified edit/move primitives onto restore semantics. Do not implement or enable a restore executor until that review explicitly identifies:

- which restore operations are atomic replacements vs exclusive creates;
- which recovery record is created for the restore itself;
- how fresh-once approval evidence becomes a prepared receipt before mutation;
- how stale revalidation happens immediately before the protected filesystem call;
- how replay, crash, partial success, and receipt-finalization failure are classified.

## Live boundary

Nothing in P5-02D changes the live authorization boundary.

Still true:

- `orion_vault_apply_plan` points to the refusing placeholder;
- no restore executor is registered;
- no live COMPANION plugin install is authorized by this source work;
- no real vault/inbox mutation is authorized;
- a receipt alone can never authorize an action.
