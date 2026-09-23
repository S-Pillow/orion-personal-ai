# P5-02P — First Production Canary Edit Readiness

Status: **SOURCE-ONLY READINESS / NO PRODUCTION MUTATION AUTHORIZED**

Date: 2026-09-23

Branch:

```text
feature/orion-phase5-p5-02p-production-canary-readiness
```

Depends on:

- P5-02N source qualification accepted;
- P5-02O installed/runtime qualification accepted;
- installed Orion vault plugin is exact P5-02N-qualified `0.2.0` source;
- `orion_vault_apply_plan` is registered to
  `apply_plan_production_guarded`;
- `_execute_production_plan_candidate()` remains private;
- `ORION_P5_MUTATION_MODE` is absent/persisted nowhere and resolves to
  `disabled`;
- production recovery inventory is empty;
- COMPANION is manual-off.

## Purpose

P5-02P is a planning/readiness gate for the first real production mutation.
It does not create the canary, enable mutation, start COMPANION, or invoke a
production apply.

The goal is to make the eventual first mutation deliberately small,
observable, recoverable, and easy to stop before any side effect.

## PRD requirements carried forward

The controlling PRD v2.8 requires:

- side-effect-free preview generation;
- canonical containment beneath the configured vault/inbox roots;
- an explicit Hermes generic approval before mutation;
- an approval payload with the exact target and exact diff/operation;
- no mutation on denied, unresolved, expired, timed-out, or stale approval;
- stale-state revalidation before execution;
- bounded atomic execution;
- recovery information for approved operations;
- deletion as a separate explicit approval/action class.

Therefore the first production mutation SHOULD NOT be a delete and SHOULD NOT
combine multiple action classes.

## External research findings

### 1. Use a single edit as the first production mutation

A one-file edit has a smaller failure surface than a move:

- one existing target rather than source + destination;
- no source deletion;
- no target-create race;
- recovery requires one captured original payload;
- postcondition is a single target hash.

The production edit implementation already performs the required sequence:
preflight, exact preview lookup, fresh human approval, post-approval
revalidation, second recovery-inventory check, durable recovery preparation,
final file-id/hash validation, native replacement, post-write hash validation,
manifest commit, then receipt commit.

### 2. Keep the canary permanent through Phase 5

The first target should be a deliberately created canary note containing no
personal data. Do not plan to delete it immediately after the test.

Reason:

- deleting the canary introduces a second action class;
- PRD OR-NOTE-008 requires deletion to have its own separate explicit approval;
- retaining one known canary gives later edit/restore regression gates a stable,
  low-value target.

Proposed relative path, pending owner confirmation:

```text
_Orion-P5-Canary.md
```

Proposed before bytes (UTF-8, no BOM, LF newlines):

```text
# Orion Phase 5 Canary
state: before
gate: first-production-edit
```

Proposed after bytes:

```text
# Orion Phase 5 Canary
state: after
gate: first-production-edit
```

The exact target and exact before/after hashes must be captured and confirmed
before any mutation-enabled process starts.

### 3. Windows file identity remains a required race guard

Microsoft documents that `FILE_ID_INFO` combines volume serial number and a
128-bit file identifier to uniquely identify a file on one computer. The Orion
production edit rechecks this identity before replacement, in addition to the
content hash.

Reference:

- https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex

### 4. ReplaceFileW is the correct existing primitive, but do not overclaim write-through

Microsoft documents that `ReplaceFileW` replaces one file with another while
preserving important attributes/ACL-related metadata from the replaced file.
The original and replacement are required to be on the same volume.

Microsoft also documents that `REPLACEFILE_WRITE_THROUGH` is not supported.
Therefore P5-02P must not claim that this flag provides durability.

Orion's actual safety case is instead:

1. recovery bytes are written and fsynced first;
2. recovery manifest and prepared receipt are written first;
3. replacement bytes are written to an exclusive temporary file and fsynced;
4. target file identity/hash are rechecked immediately before `ReplaceFileW`;
5. the resulting target hash is checked;
6. recovery manifest and receipt are committed;
7. restart classification can reconcile a prepared record from actual
   filesystem hashes if interruption occurs between protected steps.

Reference:

- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers

No source hardening change is currently justified solely by the unsupported
`REPLACEFILE_WRITE_THROUGH` flag because the qualified implementation already
pre-flushes bytes and provides post-crash recovery classification. Treat a
power-loss-specific durability enhancement as a separate evidence-backed
change if later required.

### 5. Preserve the human once-only approval path

Hermes documents that:

- `pre_tool_call` can block or escalate a tool before execution;
- the Runs API emits an `approval.request` and parks the run in
  `waiting_for_approval`;
- `POST /v1/runs/{run_id}/approval` resolves that exact pending approval;
- `once` authorizes only that request;
- approval timeout denies/fails closed and an expired prompt requires a new
  tool call.

References:

- https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
- https://hermes-agent.nousresearch.com/docs/user-guide/security
- https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop

The first production gate must accept only `choice=once`. Session, always,
smart/automatic approval, cron, single-query auto-approval, cached decisions,
or a missing observer remain non-authorizing under the qualified plugin.

### 6. Use explicit change-control records

NIST configuration-change guidance emphasizes reviewed/approved changes,
documented implementation, testing, and post-change review. Orion's current
gate structure already follows that pattern and should retain:

- exact source/runtime baseline;
- exact target and hashes;
- explicit owner authorization;
- rollback/recovery before side effect;
- captured result and postcondition;
- manual-off restoration;
- repository evidence after acceptance.

References:

- https://csrc.nist.gov/pubs/sp/800/128/upd1/final
- https://nvlpubs.nist.gov/nistpubs/SpecialPublications/800-171r3/NIST.SP.800-171r3.html

## Recommended gate decomposition

Do not combine fixture creation, first production mutation, restore, move, and
delete into one acceptance event.

### P5-02P-A — canary fixture setup

Separate owner authorization should name the exact canary target.

Conditions:

- Hermes manual-off;
- production mutation mode absent;
- production recovery inventory empty;
- target does not already exist;
- target parent is the accepted vault root and is not a reparse point;
- create exactly the agreed before bytes;
- verify SHA-256 immediately after creation;
- leave the canary in place.

This is an operator-created test fixture, not an Orion mutation acceptance.

Prepared source artifact:

```text
scripts/phase5/p5-02p-create-canary-fixture.ps1
```

### P5-02P-B — read-only production readiness

Before mutation enablement:

- prove installed plugin still matches exact P5-02N source;
- run installed plugin doctor;
- prove `config.yaml` and `.env` still match the P5-02O accepted state;
- prove no mutation/disposable settings are ambient or persisted;
- prove recovery inventory is exactly zero with no attention/truncation;
- prove the canary exists at the exact canonical target;
- capture canary SHA-256 and Windows file identity;
- compute exact proposed bytes/hash and unified diff without writing;
- verify no reparse component and fixed local volume assumptions;
- record the expected approval summary.

Prepared source artifact:

```text
scripts/phase5/p5-02p-canary-readiness.ps1
```

### P5-02Q — first Orion production canary edit

This later live gate requires another explicit owner authorization naming:

- action: `edit_note`;
- exact canary relative/canonical path;
- exact expected before SHA-256;
- exact proposed after SHA-256;
- exact approval diff;
- exact accepted installed plugin source;
- rollback/recovery expectations.

Recommended execution order:

1. require manual-off baseline;
2. require P5-02P-B readiness PASS immediately before start;
3. set `ORION_P5_MUTATION_MODE=mutation_enabled` **process-scoped only** for
   the bounded COMPANION start; never persist it;
4. start COMPANION and confirm health/toolset;
5. create the exact edit preview;
6. independently compare returned canonical target, before hash, after hash, and
   diff hash to the frozen gate contract;
7. invoke `orion_vault_apply_plan` through an interactive/gateway Hermes
   execution context;
8. present exactly one Hermes approval request;
9. owner selects **Allow once** only;
10. require the result to report success + `mutation_performed=true` +
    `recovery_required=false`;
11. verify canary after SHA-256 from disk;
12. inspect the exact new schema-v2 recovery record/receipt read-only;
13. verify inventory count becomes exactly 1 and the record classifies
    `committed`, with no attention state;
14. stop COMPANION;
15. clear all process-scoped mutation state;
16. prove persistent mutation mode is still absent;
17. return Hermes to manual-off;
18. commit acceptance evidence.

### P5-02R — restore qualification

Do not automatically restore the canary as part of P5-02Q.

A restore is a distinct approved operation and is useful as its own production
recovery acceptance. P5-02R should use the P5-02Q recovery record to generate a
fresh restore preview and require a new human `ALLOW ONCE`.

### Later move/delete

- Production move should follow only after edit + restore are accepted.
- Delete remains unimplemented and separately approval-gated by the PRD.

## Invocation-path finding that remains open

The safest deterministic invocation should use a real Hermes execution context
so the generic approval observer is genuine.

Two candidate paths were reviewed:

1. Hermes Runs API with SSE + `approval.request` +
   `POST /v1/runs/{run_id}/approval`;
2. an interactive Hermes process using the installed plugin/registry directly.

The Runs API has the strongest product-path fidelity and explicit once-only
approval endpoint, but the current accepted API documentation does not expose a
per-run allowlist that can constrain the model to only the two Orion tools.
A model-driven run therefore needs an additional safety argument before it is
used for the first production mutation.

Do not use an LLM prompt as the sole action-boundary control.

Before P5-02Q execution, resolve this item with a non-production proof:

- either demonstrate a deterministic registered-tool dispatch route that still
  enters Hermes generic approval;
- or demonstrate a Runs API harness that cannot execute any unexpected
  mutating tool during the gate.

Until that is proven, P5-02Q remains **design-ready but execution-blocked**.

## Stop conditions for tomorrow

Stop before mutation enablement if any of the following is true:

- P5-02O source/runtime identity has drifted;
- repository/operator artifacts are dirty or unreviewed;
- Hermes is already running unexpectedly;
- mutation mode exists in persistent config/environment;
- recovery inventory is nonzero before the canary-edit gate;
- canary path/content/hash/file identity differ from the frozen contract;
- preview target/diff/hashes differ from expected;
- deterministic Hermes invocation path is unresolved;
- approval surface does not show the exact canonical target/diff;
- any choice other than fresh human `once` is observed;
- any unrelated tool executes;
- recovery preparation cannot be verified;
- Hermes cannot be returned to manual-off.

## Current stopping point

P5-02O is the accepted installed/runtime boundary.

P5-02P planning/research is source-only preparation. No canary fixture has been
created by this work, no mutation mode has been enabled, and no production
vault/inbox/recovery content has been changed.
