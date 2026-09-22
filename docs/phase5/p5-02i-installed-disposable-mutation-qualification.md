# P5-02I Installed-Runtime Disposable Mutation Qualification

Status: **SOURCE-ONLY PREPARATION / LIVE DISPOSABLE MUTATION REQUIRES EXPLICIT OWNER AUTHORIZATION**

Base: P5-02H preview-only COMPANION install accepted on 2026-09-22.

## Goal

Qualify the already-installed `orion-vault-actions` private disposable mutation candidates on the pinned Windows Hermes runtime without touching the real Orion vault or inbox.

This gate is intentionally narrower than production activation. It proves that the accepted source-only mutation/recovery design still behaves correctly when imported from the installed plugin location and exercised on explicitly disposable Windows roots.

## Authorization boundary

Source-only preparation, documentation, and read-only inspection may proceed under the normal project workflow.

**Do not execute this gate until the owner separately and explicitly authorizes installed-runtime disposable mutation qualification.**

That later authorization may cover only:

- creation of temporary disposable vault, inbox, and recovery roots outside `C:\Personal\Me` and `C:\Personal\Orion-Inbox`;
- process-scoped environment variables for those disposable roots;
- process-scoped `ORION_P5_ALLOW_DISPOSABLE_MUTATION=1`;
- installed-plugin preview/edit/move/recovery/restore qualification against those disposable roots;
- fresh Hermes human ALLOW ONCE / DENY qualification for disposable plans;
- deterministic failure/crash probes whose effects are confined to the disposable fixture;
- cleanup of the disposable fixture after evidence is captured.

It does **not** authorize:

- `ORION_P5_MUTATION_MODE=mutation_enabled`;
- `ORION_P5_PRODUCTION_RECOVERY_ROOT`;
- any persistent COMPANION `.env` mutation for disposable qualification;
- registering the private production executor;
- any real vault/inbox edit, move, restore, delete, or recovery operation;
- changing ACLs;
- Hermes/Ollama/iai upgrades;
- merge/deploy actions.

## Existing installed source boundaries

The accepted plugin already contains:

- registered previews:
  - `orion_vault_preview_edit`
  - `orion_vault_preview_move_draft`
  - `orion_vault_recommend_destination`
- registered `orion_vault_apply_plan`, which remains bound to `apply_plan_placeholder` and fail-closed;
- private, unregistered `_execute_disposable_plan_candidate`;
- private, unregistered `_execute_disposable_restore_candidate`;
- private read-only recovery/receipt inspection and restore-preview helpers;
- fresh-once approval evidence with non-reusable attempt correlation.

The disposable root guard requires all of the following in the qualifying process:

- `ORION_P5_ALLOW_DISPOSABLE_MUTATION=1`;
- explicit `ORION_VAULT_ROOT`;
- explicit `ORION_INBOX_ROOT`;
- explicit `ORION_P5_RECOVERY_ROOT`;
- all three roots exist;
- all three roots are distinct and disjoint;
- none overlaps the protected live default roots, even after resolution;
- no disposable root is a reparse point.

The private disposable executor is not registered as a Hermes tool and must remain unregistered throughout this gate.

## Preflight

Before any disposable mutation:

1. Hermes/Orion should be in the accepted manual-off state unless the human approval surface chosen for the gate specifically requires a controlled temporary runtime.
2. Confirm the installed plugin still passes doctor at 4 tools / 2 hooks.
3. Confirm the registered apply handler is still `apply_plan_placeholder`.
4. Confirm `ORION_P5_MUTATION_MODE` is absent or disabled.
5. Confirm `ORION_P5_PRODUCTION_RECOVERY_ROOT` is absent.
6. Confirm no disposable mutation env variables persist in COMPANION `.env`.
7. Create one timestamped temporary fixture parent and three child roots: `vault`, `inbox`, `recovery`.
8. Record fixture-path identities and initial file hashes before mutation.

## Required qualification sequence

### I1 — fail-closed control

With the installed plugin and disposable roots configured in-process:

- verify the registered `orion_vault_apply_plan` still returns `p5_01_mutation_not_authorized`;
- verify the private disposable executor refuses when `ORION_P5_ALLOW_DISPOSABLE_MUTATION` is absent;
- verify live default/root-overlap inputs are rejected;
- verify no recovery record is created by a refused attempt.

### I2 — disposable edit with fresh-once approval

Create a disposable Markdown note, then:

1. preview an edit;
2. obtain fresh Hermes approval evidence for that exact plan;
3. require human **ALLOW ONCE**;
4. execute only `_execute_disposable_plan_candidate` with the matching evidence;
5. verify:
   - exact proposed bytes landed;
   - `mutation_performed=true`;
   - recovery record created;
   - manifest committed;
   - receipt committed;
   - approval choice is `once`;
   - `authorization_reusable=false`;
   - recovery/receipt inspection reports committed;
   - replay is refused.

A separate DENY attempt must leave the disposable note and recovery root unchanged.

### I3 — disposable move with fresh-once approval

Create an Orion-marked disposable draft and absent disposable target, then:

1. preview the move;
2. obtain fresh Hermes **ALLOW ONCE** evidence;
3. execute the private disposable candidate;
4. verify:
   - target contains exact source bytes;
   - source is absent after commit;
   - recovery backup and receipt are committed;
   - held-handle/file-ID protections remain active on Windows;
   - replay is refused.

A separate DENY attempt must leave source/target/recovery state unchanged.

### I4 — stale-state and evidence-consumption checks

At minimum:

- mutate the disposable edit target after approval but before execution and require stale/file-ID rejection with no protected write;
- create/replace the disposable move target after approval and require refusal;
- verify used or mismatched approval evidence cannot authorize a later attempt;
- verify receipt data cannot authorize a later attempt.

### I5 — restart-safe recovery classification

After one committed edit and one committed move:

- clear in-memory preview/approval caches to simulate restart;
- inspect recovery and receipt records from disk;
- require correlation validity, committed classification, and non-reusable authorization;
- do not auto-repair or auto-restore anything.

### I6 — disposable historical restore

Using the committed disposable records only:

- build restore previews;
- require a new fresh human **ALLOW ONCE** for each restore;
- execute `_execute_disposable_restore_candidate`;
- verify edit restore creates an independent restore recovery/receipt and restores prior bytes;
- verify move-source restore recreates the original disposable inbox source only and leaves the disposable vault target untouched;
- verify originating approval evidence cannot authorize restore;
- verify stale state after approval consumes that approval and blocks replay.

### I7 — controlled failure checkpoints

Exercise at least one pre-mutation and one post-mutation failure checkpoint on disposable files and require restart-safe classification:

- prepared/no-effect before protected replace/delete;
- applied-unfinalized after protected mutation but before receipt finalization.

Do not auto-retry a mutation after an applied-unfinalized result.

## Acceptance criteria

P5-02I passes only if all of the following are true:

- every filesystem mutation occurred exclusively under the disposable fixture roots;
- no path resolved into or overlapped the real vault/inbox;
- registered live apply remained fail-closed throughout;
- fresh human `once` evidence was required for successful qualification mutations/restores;
- denial/stale/replay/mismatched-evidence paths produced no unauthorized protected side effect;
- Windows file identity/held-handle protections behaved as designed;
- recovery + receipt records survived in-memory reset and classified correctly;
- historical restore used a new transaction and new approval;
- no persistent production mutation setting or production recovery root was created;
- fixture cleanup was performed only after evidence collection;
- final Orion/Hermes lifecycle returned to the pre-gate manual-off state.

## Stop / escalation rules

Stop immediately if:

- any fixture path resolves into a protected live root;
- the registered apply handler is no longer the placeholder;
- the private executor is unexpectedly registered as a public Hermes tool;
- production mutation mode appears;
- a DENY, stale, mismatched-evidence, or replay case mutates a fixture;
- a failure classification is ambiguous;
- the runtime cannot distinguish prepared/no-effect from applied-unfinalized;
- approval is session/permanent/cached/automatic rather than a fresh human `once`.

Do not "fix forward" by broadening scope. Preserve the fixture/recovery evidence and return to source investigation.

## Post-gate boundary

A P5-02I PASS still does **not** authorize production mutation.

The following remain separate future gates:

- production recovery-root location + ACL acceptance;
- production handler activation design and registration;
- first bounded real-vault mutation with exact fresh approval;
- restore/delete production acceptance.
