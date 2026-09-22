# P5-02F Production Activation Readiness Review

Status: **SOURCE-ONLY REVIEW COMPLETE / PREVIEW-ONLY INSTALL MAY BE SEPARATELY AUTHORIZED / LIVE MUTATION NOT READY**
Date: 2026-09-22
Depends on: P5-02A through P5-02E

## Purpose

This review answers one narrow question:

> What is still required before the source-verified Phase 5 vault-action candidates can become a real COMPANION mutation handler?

It does not install or enable the plugin, change Hermes configuration, choose/create a production recovery directory, restart a service, or mutate the real vault/inbox.

## Controlling PRD requirements

ORION Master PRD v2.8 requires Phase 5 to provide:

- canonical containment;
- side-effect-free previews;
- exact action / target / relevant diff or payload;
- Hermes generic approval before protected mutation;
- stale-preview protection;
- exact / atomic execution;
- recovery information;
- browser/HUD presentation without filesystem authority.

OR-APR-001 through OR-APR-006 are the controlling approval boundary. In particular:

- the approval card is descriptive/presentation evidence, not authorization;
- plugin registration is not an approval boundary;
- unresolved, denied, expired, timed-out, or stale approval produces no protected side effect.

The current source work satisfies these requirements in disposable/source verification, but production activation still needs explicit wiring and runtime safeguards.

## Accepted Windows evidence entering this review

Current accepted Phase 5 source baseline:

- `test_p5*.py`: **86/86 passed** in 1.850s;
- installed-Hermes dispatcher probe: **2/2 passed** in 0.074s;
- plugin doctor: **PASS**, 4 tools / 2 hooks;
- exact approval-card visual gate passed;
- real Hermes -> Orion HUD -> human DENY / ALLOW ONCE -> no-write approval gate passed;
- Windows move-path file-ID/held-handle hardening passed;
- recovery reconciliation passed;
- historical restore preview/stale revalidation passed;
- restart-safe non-authorizing receipt correlation passed;
- private disposable restore execution/recovery/replay paths passed.

The known Hermes SQLite 3.40.1 WAL-reset warning remains separate runtime hygiene. Hermes falls back to `journal_mode=DELETE`; no dependency update is part of this activation review.

## Current registered live surface

The current plugin manifest advertises four tools and two hooks:

- `orion_vault_preview_edit`;
- `orion_vault_preview_move_draft`;
- `orion_vault_recommend_destination`;
- `orion_vault_apply_plan`;
- `pre_tool_call`;
- `post_approval_response`.

Critically, `orion_vault_apply_plan` is still registered to `apply_plan_placeholder`, which always returns:

```text
p5_01_mutation_not_authorized
```

The private disposable edit/move/restore executors are not registered.

The manifest description still truthfully says that no protected filesystem mutation is registered.

## Readiness result

### Preview-only COMPANION install

**TECHNICALLY READY FOR A SEPARATE OWNER-AUTHORIZED INSTALL GATE.**

Installing the current registered surface would still leave protected mutation disabled.

That gate still requires separate authorization because installation changes the live COMPANION profile/configuration and may require an accepted lifecycle restart.

A preview-only install must not be described as mutation activation.

### Live edit/move/restore activation

**NOT READY.**

The following blockers must be closed first.

---

## Blocker 1 — production recovery root is undefined

The disposable candidate requires a third recovery root outside the vault and inbox, but production has no approved path.

Production must require an explicit configured recovery root. Do not silently default it into either:

- `C:\Personal\Me`;
- `C:\Personal\Orion-Inbox`.

The recovery location contains full note contents and approval receipts. It is private data, not a log folder.

### Required production validation

Before a mutating handler can become active, a read-only validator must confirm:

- configured recovery path exists;
- it is a directory;
- local filesystem only;
- no symlink/junction/reparse traversal;
- raw and resolved path are disjoint from vault and inbox in both directions;
- no broad write ACL for Everyone / Users / Authenticated Users or equivalent;
- current Orion user/service identity has required access;
- recovery record creation can be refused cleanly if validation fails.

Do not auto-create or repair this directory during ordinary plugin startup.

The exact path and any ACL-changing command remain owner decisions and separate mutation/configuration authorization.

## Blocker 2 — no production startup mutation gate

There is currently no explicit production mutation-mode guard.

A live implementation should have an operator-owned configuration state such as:

```text
disabled
preview_only
mutation_enabled
```

or an equivalent fail-closed control.

Requirements:

- default after install: `preview_only` or disabled;
- browser/HUD cannot widen this state;
- missing/invalid value => no protected mutation;
- mutation activation requires successful production-root/ACL validation;
- startup validation failure may leave read-only preview/recommendation available but must disable apply.

The current disposable environment flag is a test guard, not a production activation switch.

## Blocker 3 — registered apply handler is still a placeholder

The live handler must not simply point `orion_vault_apply_plan` at `_execute_disposable_plan_candidate()` or `_execute_disposable_restore_candidate()`.

Reasons:

- the disposable candidate intentionally rejects live roots;
- normal edit/move approval evidence is optional in the disposable executor for historical fixture compatibility;
- restore candidate is private/test-scoped;
- production needs startup/config validation and live receipt policy;
- production must own exact approval ordering.

A dedicated production handler/executor layer is required.

## Blocker 4 — the final approval authority must be handler-side and fresh

The current `pre_tool_call` hook is valuable for fail-closed plan validation and presentation experiments, but the pinned Hermes behavior already demonstrated why a policy-hook directive alone cannot be the final mutation authority.

Production execution must explicitly enter Hermes generic approval from the final mutating path and require:

- fresh exact plan;
- exact approval message/diff;
- human `once`;
- matching `post_approval_response`;
- gate result `approved=true`;
- no session/always;
- no yolo/cached/cron/single-query bypass;
- no missing/late callback;
- no stale state after the human response.

### Double-approval question

The production ticket must resolve the current architecture so the operator does **not** receive two independent approval prompts for one action.

The source needs one deterministic approval owner:

- the final handler explicitly requests Hermes generic approval;
- `pre_tool_call` may still block invalid/expired plans, but its directive must not be mistaken for the final authorization.

The exact installed-Hermes hook/dispatch behavior must be verified when this wiring is implemented.

## Blocker 5 — normal edit lacks Windows file-ID parity

The current restore-edit preview/revalidator binds the Windows file ID in addition to canonical path and SHA-256.

The normal `preview_edit` / disposable edit path currently binds:

- canonical path;
- original content hash;
- proposed content hash;
- exact diff.

Before production activation, normal edit should receive the same Windows object-identity protection as restore edit, or the project must explicitly document and accept the weaker identity model.

Preferred closure:

- bind Windows target file ID at edit preview;
- re-check that file ID immediately before the protected replacement;
- retain current hash check and native `ReplaceFileW`;
- add same-bytes/different-file-object Windows regression coverage.

This keeps edit and restore on the same object-identity policy.

## Blocker 6 — unresolved recovery records are not discoverable after restart

The source can inspect a recovery record when its ID is known, but production has no startup/read-only enumeration path.

A crash can leave:

- prepared/no-effect;
- applied-unfinalized;
- divergent-unresolved;
- duplicate-unresolved move state;
- prepared receipt with committed filesystem state.

Production needs a bounded read-only recovery index that:

- enumerates immediate recovery-record directories only;
- validates IDs and containment;
- never follows reparse points;
- inspects each record independently;
- surfaces unresolved/corrupt records;
- never mutates user content automatically;
- never deletes/prunes unresolved records;
- limits count/work per scan so corrupt storage cannot create an unbounded startup loop.

At minimum, unresolved state must be visible to the operator after restart.

## Blocker 7 — recovery/receipt production schema and retention are not activated

The source-qualified schema is sufficient for disposable evidence, but production activation must freeze a schema contract and retention behavior.

Required:

- versioned production schema;
- explicit recovery ID;
- exact action/plan;
- non-authorizing approval attempt correlation;
- exact approval text/hash;
- artifact role/name/hash;
- prepared/committed state;
- current reconciliation classification;
- origin recovery ID for restore transactions;
- durable write/replace semantics.

Initial retention should remain conservative:

- no automatic deletion of unresolved records;
- no automatic pruning in the first live mutation slice;
- rollback of plugin code/config must **not** delete recovery artifacts.

## Blocker 8 — production configuration and rollback are not yet frozen

The current README already identifies the intended COMPANION plugin destination and the iai MCP allowlist seam, but the exact production configuration delta is not yet captured as an immutable ticket packet.

Before install/activation, freeze:

- source commit;
- plugin destination;
- current user-plugin inventory;
- current COMPANION plugin configuration;
- exact `mcp_allowlist: ["iai-mcp"]` change;
- mutation-mode setting;
- vault/inbox/recovery roots;
- recovery-root ACL evidence;
- manifest/plugin version;
- exact files copied;
- lifecycle command required for activation;
- rollback commands.

Rollback must:

1. disable mutation first;
2. return registered apply behavior to fail-closed;
3. restore prior COMPANION plugin config;
4. remove only the installed plugin artifact when separately authorized;
5. preserve all recovery/receipt records, especially unresolved ones.

## Blocker 9 — production live-path acceptance test does not exist yet

Disposable Windows verification is strong, but the final production handler needs a bounded end-to-end qualification before any real vault mutation.

The first live mutation must not be the first time the production handler wiring is exercised.

Required progression:

1. source tests;
2. plugin doctor;
3. preview-only installed plugin smoke;
4. installed handler no-write/fail-closed smoke;
5. production-style apply wiring against an explicitly disposable root while loaded by the real COMPANION plugin/runtime;
6. exact HUD approval visual check;
7. DENY -> zero mutation;
8. ALLOW ONCE -> one disposable mutation;
9. replay -> refused;
10. stale-after-approval -> refused;
11. restart -> receipt/recovery still inspectable;
12. only then consider a separately authorized bounded real-vault mutation.

This is the bridge between source confidence and live confidence.

---

## Non-blocking items

These do not currently block a source activation-preparation ticket:

### Known Hermes SQLite warning

The accepted Hermes runtime reports linked SQLite 3.40.1 and uses `journal_mode=DELETE` because of the WAL-reset bug warning.

Do not run `hermes update` inside Phase 5 activation work. Updating Hermes would change the accepted runtime pin and needs a separate dependency qualification.

### Automatic recovery resolution

The first production mutation slice does not need automatic repair.

Read-only detection and clear unresolved-state surfacing are sufficient for activation readiness. Any content-changing recovery resolution must remain separately previewed and approval-bound.

### Recovery pruning

Automatic pruning is not required for first activation and should remain disabled.

## Required source ticket before live mutation

Recommended next source unit: **P5-02G Production Mutation Guardrails**.

Scope:

1. add production configuration/mutation-mode parser with fail-closed defaults;
2. add read-only production recovery-root validator, including Windows ACL and local-filesystem checks;
3. add bounded read-only recovery enumeration;
4. add Windows file-ID parity to normal edit preview/revalidation;
5. create a dedicated production apply candidate that:
   - requires mutation mode enabled;
   - validates production roots;
   - owns one fresh Hermes generic ALLOW ONCE;
   - revalidates after approval;
   - requires approval evidence for edit/move/restore;
   - creates durable recovery/receipt before protected side effects;
   - never calls the disposable-root guard;
6. resolve the pre-tool vs handler-side approval ownership so exactly one human approval appears;
7. keep the new production candidate **unregistered** while tests are developed;
8. add source tests for disabled/preview-only modes, invalid ACL/root, unresolved recovery enumeration, same-bytes edit replacement, deny/stale/replay, and recovery-index bounds.

Do not include live plugin installation in P5-02G.

## Suggested activation sequence after P5-02G passes

### Gate A — source acceptance

- full P5 Windows tests pass;
- dispatcher probe passes;
- plugin doctor passes;
- production preflight tests pass;
- registered apply remains placeholder.

### Gate B — preview-only live install

Requires separate explicit owner authorization.

- capture COMPANION plugin/config baseline;
- install exact approved commit;
- configure iai allowlist only;
- keep mutation mode preview-only/disabled;
- restart only through accepted manual lifecycle;
- prove previews/recommendation/HUD approval display;
- prove apply still refuses mutation;
- record rollback.

### Gate C — production candidate installed but mutation disabled

Requires separate explicit owner authorization if the source differs from Gate B.

- deploy production handler code;
- keep mutation mode disabled;
- run startup/preflight;
- verify recovery root/ACL;
- verify no mutation path is active.

### Gate D — real runtime + disposable mutation qualification

Requires separate explicit authorization.

- enable mutation mode only for an explicitly disposable test root/config;
- run DENY/ALLOW ONCE/stale/replay/restart tests through the actual installed COMPANION runtime/HUD;
- return mutation mode to disabled after the test.

### Gate E — bounded real-vault mutation

Requires a new explicit authorization unit naming the exact test action/target.

Only after Gate D is accepted.

## Phase 5 completion boundary

Passing P5-02G and activating edit/move/restore would still not automatically mean Phase 5 is complete.

Remaining Phase 5 work must be evaluated separately, including any still-open:

- draft creation flow;
- delete/undo flow;
- recovery-resolution UI;
- display/summon closure if not already accepted through Phase 3/5 integration;
- final production operator acceptance.

Do not collapse those into mutation activation.

## Review conclusion

### Current decision

- **Preview-only install:** source is ready to enter a separately authorized install gate.
- **Live mutation activation:** **NO-GO until P5-02G closes the blockers above.**

This is not a negative finding. The disposable mutation and restore mechanisms are behaving as intended; the remaining work is the explicit production boundary around them.

No install, config change, lifecycle action, recovery-directory creation, ACL change, or real vault/inbox mutation was performed by this review.
