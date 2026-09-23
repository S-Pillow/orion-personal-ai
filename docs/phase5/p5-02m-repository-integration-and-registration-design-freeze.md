# P5-02M Repository Integration and Production Registration Design Freeze

Status: **READY FOR INTEGRATION REVIEW / SOURCE-CONTROL AND DESIGN FREEZE ONLY / NO RUNTIME CHANGE**

Date: 2026-09-23

Branch: `feature/orion-phase5-p5-02m-registration-design-freeze`

Depends on: P5-02L accepted at `243f778a2a09a4a9f2c603c437e8b94149d52e2b`

## Purpose

P5-02M reconciles the accepted Phase 5 evidence into one reviewable repository lineage and freezes the design of the future registered production apply path.

This gate deliberately stops before source wiring, live installation, mutation-mode enablement, or any real vault/inbox mutation.

## Owner authorization

The owner authorized P5-02M after accepting P5-02L and reviewing the proposed repository-integration and registration-design scope.

This authorization permits:

- a new source-control branch from the accepted P5-02L commit;
- repository status/documentation reconciliation through P5-02L;
- preservation of the approved PRD v2.8 artifact and SHA-256 record;
- a source-only design freeze for the future registered production apply wrapper;
- local non-mutating regression tests;
- push and integration pull-request preparation.

This authorization does not permit:

- changes to the installed COMPANION plugin;
- changes to COMPANION `config.yaml` or `.env`;
- starting or stopping Hermes, Ollama, or iai;
- persisting or enabling `ORION_P5_MUTATION_MODE`;
- registering the private production executor in the installed runtime;
- creating a production recovery transaction;
- mutating real vault or inbox content;
- changing vault, inbox, or recovery-root ACLs;
- upgrading Hermes, Ollama, iai, or any accepted dependency.

## Entry state

P5-02L established:

- accepted production recovery root exists and is ACL-qualified;
- the exact recovery-root path is persisted in COMPANION `.env`;
- live COMPANION ingests that value;
- production mode resolves to `disabled`;
- `mutation_allowed=false`;
- public apply remains `apply_plan_placeholder` and fail-closed;
- the live `orion_vault` toolset exposes the expected four tools;
- production recovery inventory is empty;
- Hermes is restored to manual-off;
- no production mutation occurred.

## Repository reconciliation

Before P5-02M, `main` remained at the P5-01 merge while later Phase 5 work existed across an extended feature lineage. Draft PR #23 ended at the P5-02F readiness review and did not contain P5-02G through P5-02L.

P5-02M therefore prepares the accepted P5-02A through P5-02L lineage as one integration branch against `main`. It does not rewrite or squash the acceptance history. The existing draft PR may remain as historical review context; the P5-02M integration PR is the complete review surface.

Repository status documents are updated so they no longer claim that the plugin is uninstalled or that P5-02A is the resume point.

## Approved PRD preservation

The approved PRD v2.8 artifact is preserved at:

```text
docs/prd/orion-master-prd-v2.8-ai-optimized-approved.docx
```

Expected SHA-256:

```text
6b24d4d85bb1142c9284c8bd9ac202ec7cdb0f641a5b093eec6880426e107c6f
```

Approval record:

```text
docs/prd/orion-master-prd-v2.8-approval-record-2026-09-10.md
```

The binary is copied without content modification. Future revisions require a new version and approval record rather than overwriting this artifact.

## Frozen future registration design

The later source-wiring ticket must introduce a named registered wrapper. Proposed source name:

```text
apply_plan_production_guarded(params: Dict[str, Any], **_: Any) -> str
```

The registered tool must point to this wrapper, not directly to `_execute_production_plan_candidate()`.

### Public argument boundary

The apply tool schema continues accepting only:

```json
{"plan_token": "string"}
```

The public handler must not accept caller-controlled approval functions, redactors, root validators, ACL probes, filesystem probes, failure hooks, recovery paths, or proposed bytes.

Test injection remains possible only through direct private-function tests or controlled monkeypatching outside the public tool schema.

### Mode behavior

The registered wrapper must re-read and validate production mode on every invocation.

- missing or blank mode: refuse as `production_mutation_not_enabled`;
- `disabled`: refuse as `production_mutation_not_enabled`;
- `preview_only`: refuse as `production_mutation_not_enabled`;
- unknown mode: fail closed as `invalid_production_mutation_mode`;
- `mutation_enabled`: continue only through the private production candidate and every qualified guard.

No disabled, preview-only, or invalid mode may call the production executor or request human approval.

### One approval owner

When mutation is disabled, preview-only, or invalid, `pre_tool_call` must block apply without showing a misleading approval prompt.

When explicit `mutation_enabled` is present:

1. `pre_tool_call` validates that the plan exists and the exact approval summary is complete/bounded;
2. `pre_tool_call` returns no approval directive for a valid plan;
3. the registered wrapper calls the private production candidate;
4. the private candidate owns exactly one Hermes generic approval request;
5. execution requires both `approved=true` and a matching, fresh, non-coalesced human `choice=once` event from CLI or gateway;
6. session, always, yolo, cached, cron, single-query, missing, late, denied, timed-out, mismatched, or observer-failed approval refuses mutation.

This preserves Hermes as the approval authority without relying on a best-effort policy hook as the final mutation boundary.

### Execution ordering

The production path remains:

1. validate mode and production roots;
2. require bounded recovery inventory with no attention state;
3. resolve a live, unconsumed preview plan;
4. construct and verify the exact approval message;
5. obtain one fresh Hermes human `ALLOW ONCE`;
6. consume the approval evidence;
7. revalidate path, hash, Windows object identity, target/source state, and restore origin as applicable;
8. repeat bounded recovery inventory after the human decision;
9. durably create schema-v2 recovery data and a non-authorizing prepared receipt;
10. run final state/object checks immediately before the protected primitive;
11. execute native atomic replacement, exclusive creation, or held-handle delete as applicable;
12. verify the filesystem postcondition;
13. commit recovery manifest, then commit receipt;
14. return bounded JSON describing success, mutation state, and recovery state without returning secret or note bytes.

### Registration and manifest changes

The later source-wiring ticket must:

- change `orion_vault_apply_plan` registration from `apply_plan_placeholder` to `apply_plan_production_guarded`;
- keep `_execute_production_plan_candidate()` private;
- bump the plugin version from `0.1.0` to `0.2.0`;
- replace the manifest description that currently says no mutation is registered;
- keep the tool count at four and hook count at two unless a separately reviewed requirement justifies a change;
- update operator verification to assert wrapper identity, private-executor non-registration, and disabled-mode refusal.

Source wiring does not itself authorize installation or mutation.

## Required tests for the later source-wiring ticket

The next source candidate must add tests proving:

- public registration points to the named guarded wrapper;
- the private executor is not registered as any tool;
- schema exposes only `plan_token`;
- disabled, preview-only, missing, and invalid modes do not request approval or call the executor;
- disabled/preview-only `pre_tool_call` blocks rather than generating an approval card;
- mutation-enabled valid-plan `pre_tool_call` does not create a first approval;
- handler-side execution creates exactly one approval request;
- deny, timeout, yolo, cached, session, always, automatic, missing observer, late observer, and mismatched observer paths produce zero mutation;
- stale state after approval consumes evidence and produces zero mutation;
- unresolved or truncated recovery inventory blocks before approval and before a new recovery record;
- caller-supplied extra parameters cannot inject callbacks, roots, probes, bytes, or failure hooks;
- result JSON does not expose approval keys, API keys, note bytes, recovery bytes, or internal callback objects;
- replay is refused before another approval;
- all existing Phase 5 and HUD approval-rendering tests remain green;
- Windows-only file-ID, ACL, local-volume, `ReplaceFileW`, held-handle, and delete-pending checks pass on the accepted machine.

## Frozen rollback order for later installation

Any later installation of the wired plugin must capture rollback before replacement and preserve this order:

1. require Hermes manual-off;
2. verify no persistent or ambient mutation-enabled state;
3. capture exact installed plugin and COMPANION configuration bytes/hashes;
4. install only the accepted source pin;
5. run installed-location doctor while Hermes remains stopped;
6. start COMPANION only under the separately authorized gate;
7. verify public apply is the guarded wrapper but refuses because mode is disabled;
8. stop COMPANION and restore manual-off;
9. on failure, keep mutation disabled first, restore the prior plugin/config bytes, and preserve all recovery/receipt records;
10. never delete unresolved recovery evidence during code rollback.

## Required future authorization units

P5-02M freezes the following sequence:

### P5-02N source wiring

Implement and source-test the named guarded wrapper, manifest/version update, disabled-mode pre-tool blocking, and required regressions. No live installation or lifecycle action.

### P5-02O installed but disabled qualification

Install the accepted P5-02N source with rollback captured, keep mutation mode absent/disabled, verify the registered wrapper through installed source and live toolset/runtime evidence, prove apply refuses without a human approval prompt, then restore manual-off. No real vault/inbox mutation.

### Later bounded production mutation gate

Require a new owner authorization naming the exact action and target. Prefer a deliberately created canary draft/note with known bytes and a defined recovery/restore path. Enable mutation only for the bounded gate, require one exact human `ALLOW ONCE`, verify the result and recovery record, disable mutation, and restore manual-off.

Edit, move, restore, and delete acceptance are not silently bundled. Delete remains unimplemented and requires its own explicit design and approval.

## Verification evidence

Local non-mutating verification on 2026-09-23:

- Phase 5 `test_p5*.py`: **121 tests passed**, with nine expected Windows-only skips on Linux;
- HUD Python suite: **78/78 passed**;
- HUD approval-rendering Node suite: **3/3 passed**;
- plugin and HUD bridge Python sources compile successfully;
- approved PRD artifact SHA-256 and size match the approval record;
- changed-path review confirms no plugin runtime source or manifest change in P5-02M.

The accepted Windows-specific file-identity, ACL, fixed-volume, native replacement, and held-handle evidence remains the evidence recorded by the preceding Phase 5 gates. P5-02M does not claim a new Windows runtime qualification.

## P5-02M acceptance

P5-02M passes when:

- the branch descends from accepted P5-02L;
- PRD v2.8 binary and approval record are present and hash-verified;
- top-level and plugin status documentation accurately describe P5-02L;
- the future registration, approval ownership, mode behavior, test requirements, version change, rollback order, and later gates are frozen;
- no plugin runtime source is changed in this gate;
- available Phase 5/HUD regressions pass;
- a reviewable integration branch/PR is prepared against `main`;
- no installed/runtime/vault/inbox/recovery-root mutation occurs.

Passing P5-02M does not authorize P5-02N implementation, live installation, production mutation enablement, or a real vault/inbox action.
