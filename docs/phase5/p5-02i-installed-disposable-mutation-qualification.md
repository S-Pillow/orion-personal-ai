# P5-02I Installed-Runtime Disposable Mutation Qualification

Status: **OWNER AUTHORIZED / I1-I3 PASS / I4 SOURCE HARDENING VERIFIED / INSTALLED UPDATE AUTHORIZATION REQUIRED**

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

## Authorized operator probe

Owner authorization for P5-02I disposable-root qualification was received on 2026-09-22.

The first executable probe is pinned at:

```text
aaede442c768e31ef6f9744ecfbde70497ac18f1
scripts/phase5/p5-02i-disposable-edit-qualification.py
```

It imports the installed plugin, keeps Hermes in manual-off state, creates temporary disposable roots under an explicit neutral parent (use `D:\Orion`), and performs:

- I1 disposable opt-in guard;
- I1 live-vault-overlap refusal;
- real Hermes CLI **DENY** control;
- a new preview followed by real Hermes CLI **ALLOW ONCE**;
- disposable edit commit with recovery + receipt verification;
- replay refusal;
- registered apply fail-closed verification;
- fixture cleanup on PASS and fixture preservation on FAIL.

The script sets `HERMES_INTERACTIVE=1` only inside its own process so the pinned Hermes approval engine presents its bounded stdin prompt. It clears gateway/cron/single-query routing markers in that same process and does not persist those settings.

## I1/I2 observed result — PASS

Operator execution of the installed-runtime disposable edit probe completed successfully.

Observed:

- disposable fixture: `D:\Orion\orion-p5-02i-edit-2ynfq5u_`;
- real Hermes human **DENY** control was presented and selected;
- DENY left the disposable note unchanged and created no recovery data;
- a new preview was generated for the allow path;
- real Hermes human **ALLOW ONCE** was presented and selected;
- disposable edit committed successfully;
- before SHA-256: `c158e2b9b16d664b91a74ecceb44faa020db1e8c3072b2c069ab25bce656c702`;
- after SHA-256: `fa288ca7e1fb041e282f2ec69c02eb4578cb6dc10d6bcb57c4071e17b25cc7ae`;
- recovery classification: `committed`;
- receipt state: `committed`;
- `authorization_reusable=false`;
- replay refused;
- registered apply remained fail-closed;
- real vault/inbox untouched;
- disposable fixture cleaned on PASS;
- Hermes gateway remained stopped;
- COMPANION config SHA-256 remained exactly `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- temporary operator worktree cleaned.

Acceptance markers:

```text
P5_02I_I1_GUARDS=PASS
P5_02I_DENY_CONTROL=PASS
P5_02I_FRESH_ONCE=PASS
DISPOSABLE_EDIT_MUTATION_PERFORMED=true
RECOVERY_CLASSIFICATION=committed
RECEIPT_STATE=committed
AUTHORIZATION_REUSABLE=false
PLAN_REPLAY_REFUSED=true
REGISTERED_APPLY_FAIL_CLOSED=true
REAL_VAULT_INBOX_TOUCHED=false
DISPOSABLE_FIXTURE_CLEANED=true
P5_02I_EDIT_QUALIFICATION=PASS
P5_02I_OPERATOR_WORKTREE_CLEANED=true
```

I1 and the disposable-edit portion of I2 are accepted.

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

### I3 operator probe

Prepared source pin:

```text
e559ceba324276abf5e4aa5a72578ce8eb48906b
scripts/phase5/p5-02i-disposable-move-qualification.py
```

The probe keeps Hermes manual-off, imports the installed plugin, uses an explicit neutral fixture parent under `D:\Orion`, and requires:

- a real human **DENY** control for a disposable move;
- a separate fresh-plan real human **ALLOW ONCE**;
- exact source-byte preservation at the target;
- source absence after commit;
- Windows source file-ID binding;
- committed recovery + receipt;
- non-reusable approval correlation;
- replay refusal;
- registered apply still fail-closed;
- fixture cleanup only on PASS.

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

## I3 observed result — PASS

Operator execution of the installed-runtime disposable move probe completed successfully.

Observed:

- real Hermes human **DENY** control passed;
- fresh-plan real Hermes **ALLOW ONCE** passed;
- disposable move committed with `mutation_performed=true`;
- source SHA-256: `da84eb6e01c935b76368d57baa4dcd504f5081fe4f0188faf45e24e1dd4e8579`;
- source absent after commit;
- target bytes exactly matched approved source bytes;
- Windows source file-ID binding present;
- recovery classification: `committed`;
- receipt state: `committed`;
- `authorization_reusable=false`;
- replay refused;
- registered apply remained fail-closed;
- real vault/inbox untouched;
- disposable fixture cleaned;
- Hermes gateway remained stopped;
- COMPANION config SHA-256 remained exactly `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- temporary operator worktree cleaned.

Acceptance markers included:

```text
P5_02I_MOVE_DENY_CONTROL=PASS
P5_02I_MOVE_FRESH_ONCE=PASS
DISPOSABLE_MOVE_MUTATION_PERFORMED=true
MOVE_SOURCE_ABSENT=true
MOVE_TARGET_BYTES_MATCH=true
WINDOWS_SOURCE_FILE_ID_BOUND=true
MOVE_RECOVERY_CLASSIFICATION=committed
MOVE_RECEIPT_STATE=committed
MOVE_AUTHORIZATION_REUSABLE=false
MOVE_PLAN_REPLAY_REFUSED=true
REGISTERED_APPLY_FAIL_CLOSED=true
REAL_VAULT_INBOX_TOUCHED=false
DISPOSABLE_FIXTURE_CLEANED=true
P5_02I_MOVE_QUALIFICATION=PASS
P5_02I_MOVE_OPERATOR_WORKTREE_CLEANED=true
```

I3 is accepted.

### I4 source blocker discovered before live execution

Review before the I4 operator run found that the older disposable edit/move
prototype validated optional `approval_evidence` but did not consume its
`attempt_id` before stale-state checks. That behavior was deliberately kept
for earlier source-prototype compatibility, while disposable restore and the
production-shaped executor already consume approval before post-human stale
revalidation.

Running I4 against that older installed path would therefore not prove that a
stale human ALLOW ONCE cannot later be revived.

P5-02I source hardening adds a qualification-only
`require_fresh_approval=True` seam to the private disposable executor:

- approval evidence becomes mandatory for the qualification path;
- valid evidence is consumed before source/target stale revalidation;
- stale edit or move-target-race rejection consumes the human once;
- returning fixture state to the earlier bytes/path does not revive that
  approval;
- invalid/mismatched evidence still refuses before recovery/mutation;
- the default remains false only so older source-prototype tests keep their
  historical semantics;
- the public registered apply handler is unchanged and remains fail-closed.

Source commits:

```text
d7d429f333fbe15fbc3a44dcd6c68d0a0435ee93  implementation
55049f782e43fc48505ad8b1cae53eeaec3ca427  focused P5-02I tests
```

New focused tests cover:

1. required mode refuses missing approval before recovery;
2. stale edit consumes approval and same evidence cannot revive;
3. move target race consumes approval and same evidence cannot revive;
4. mismatched evidence refuses before recovery/mutation;
5. valid required-mode once commits and plan replay refuses.

This source change has **not** been copied into the installed COMPANION plugin.
Source verification must pass first. Updating the installed plugin to this new
exact source is a separate live-plugin change and requires explicit owner
authorization before I4 installed-runtime execution.

### I4 source verification — PASS

Owner-run Windows verification of the hardened P5-02I source at
`ce676a263f3dd2c18a7d7700b17a6023c6845904` completed successfully:

- focused approval-consumption tests: **5/5 passed** in 0.066s;
- full Phase-5 source suite: **121/121 passed** in 2.534s;
- source plugin doctor: **PASS**, runtime discovery/import/registration;
- registrations remain **4 tools / 2 hooks**;
- verification worktree cleaned.

No installed COMPANION plugin files were changed by this verification.

The next required step before installed-runtime I4 execution is an exact live-plugin
source update from the P5-02H installed pin
`b8cbb63c3db20c38543220956d3f776bffecf432` to the verified P5-02I pin
`ce676a263f3dd2c18a7d7700b17a6023c6845904`.

That update is a persistent COMPANION plugin change and therefore requires
separate explicit owner authorization. The update must occur with Hermes
manual-off, capture an exact rollback copy of the currently installed plugin,
replace only the Orion plugin directory from the verified source pin, preserve
COMPANION config unchanged, and re-run installed-location doctor before any
I4 mutation probe.

### Installed plugin update authorization

Owner explicitly authorized updating only the installed COMPANION
`orion-vault-actions` plugin from the accepted P5-02H source pin

```text
b8cbb63c3db20c38543220956d3f776bffecf432
```

to the verified P5-02I source pin

```text
ce676a263f3dd2c18a7d7700b17a6023c6845904
```

for disposable-root qualification only.

The authorization does not extend to production mutation mode, production
recovery-root configuration, ACL changes, public production-executor
registration, or real vault/inbox mutation.

GitHub compare confirms the installed plugin directory delta is limited to:

- modified `hermes_plugins/orion-vault-actions/__init__.py`;
- added `hermes_plugins/orion-vault-actions/tests/test_p5_02i_disposable_approval.py`.

`plugin.yaml` is unchanged. Other files in the commit are docs/operator
scripts outside the plugin directory and are not part of the COMPANION plugin
copy.

Update procedure requirements:

1. Hermes gateway remains stopped;
2. accepted COMPANION config hash must match before and after;
3. current tracked installed plugin files must match the old P5-02H pin before replacement;
4. capture an exact rollback copy of the installed plugin directory first;
5. replace only the Orion plugin directory from the exact P5-02I source pin;
6. verify all tracked installed plugin files against the new pin;
7. run installed-location doctor and require 4 tools / 2 hooks;
8. leave Hermes manual-off after update;
9. do not run I4 mutation checks until the update evidence is accepted.

### Installed P5-02I plugin update — PASS / temporary swap cleanup pending

Owner executed the authorized installed-plugin update from
`b8cbb63c3db20c38543220956d3f776bffecf432` to
`ce676a263f3dd2c18a7d7700b17a6023c6845904`.

Verified before/after replacement:

- old installed tracked files matched the accepted P5-02H pin: **10 tracked files**;
- rollback copy matched the old pin: **10 tracked files**;
- rollback backup preserved at
  `C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\backups\p5-02i-plugin-update-20260922-034043`;
- staged new plugin matched the P5-02I pin: **11 tracked files**;
- installed new plugin matched the P5-02I pin: **11 tracked files**;
- installed-location doctor PASS: **4 tools / 2 hooks**;
- plugin remains enabled as user plugin version 0.1.0;
- COMPANION config SHA-256 remained
  `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- installed `__init__.py` SHA-256:
  `FCFA3DDC4A86B99691FB003CF4421027C5CC3CA22AC99ADBCCEEE8D3B3C7B5DA`;
- update marker: `P5_02I_INSTALLED_PLUGIN_UPDATE=PASS`;
- manual-off marker: `HERMES_MANUAL_OFF_PRESERVED=true`;
- both temporary source worktrees were removed;
- rollback backup remains preserved.

The only operator-script issue was cleanup syntax: the `finally { ... }` clause
was pasted/executed as a new top-level PowerShell statement after the
`try/catch` had already completed, so PowerShell rejected the standalone
`finally`. This does not invalidate the plugin replacement evidence. It means
the temporary old-plugin swap directory may still exist and must be removed in
a separate bounded cleanup step before I4.

### Installed-plugin cleanup — PASS

The post-update cleanup completed successfully after the earlier interactive
PowerShell `finally` issue.

Observed:

- Hermes gateway remained manual-off / no process detected;
- old timestamped swap directory removed;
- no `.orion-vault-actions-p5-*` temporary plugin directories remained;
- COMPANION config remained unchanged;
- rollback backup remained preserved;
- final marker: `P5_02I_PLUGIN_UPDATE_CLEANUP=PASS`.

Two standalone `else` clauses were rejected by PowerShell because the matching
`if` blocks had already completed as separate interactive submissions. This
did not affect the cleanup state: the final leftover enumeration was empty and
the explicit PASS marker was reached.

The installed P5-02I plugin update is therefore fully accepted and I4 may run
against the hardened installed code.

### I4 installed-runtime operator probe

Prepared source pin:

```text
c36792838660f7d4eb232bb7e71327a4f4aeba96
scripts/phase5/p5-02i-stale-approval-qualification.py
```

The probe imports the installed P5-02I plugin, keeps Hermes manual-off, uses
temporary disposable roots under an explicit neutral parent, and exercises
three real human **ALLOW ONCE** decisions:

1. edit evidence is first presented to a mismatched plan and refused, then the
   correct target is changed after approval; stale execution must refuse and
   consume the approval so restoring the old bytes cannot revive it;
2. a move target is created after approval; execution must refuse and consume
   the approval so deleting the raced-in target cannot revive it;
3. a successful disposable edit creates a committed durable receipt; the
   receipt's approval record is then presented to a different plan and must
   fail as non-authorizing evidence.

Acceptance also requires registered apply to remain fail-closed, no real
vault/inbox access, and fixture cleanup only on PASS.

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
