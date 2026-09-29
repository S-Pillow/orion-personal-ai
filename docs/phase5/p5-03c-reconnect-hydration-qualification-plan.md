# P5-03C Reconnect / Hydration Qualification Plan

Status: **COMPLETE / ACCEPTED / READY TO MERGE**

Date: 2026-09-27  
Base main: `4fb9e0abe7e534f0aa8fbfa42d52e480681c30d5`

## Stage A/B implementation checkpoint

Source branch:

`feature/orion-phase5-p5-03c-reconnect-hydration`

Qualified Stage A/B implementation ancestor:

`e214d152460ede4790488343c01998ccc1b7d53d`

Automated qualification run:

`36533575723`

Result:

- Python HUD suite: **203 tests, PASS**;
- Node renderer/reconnect suite: **25/25 PASS**;
- existing desktop/mobile Playwright capture: **PASS**;
- deterministic P5-03C reconnect/hydration browser matrix: **PASS**;
- aggregate gate: `python=0 node=0 visual=0 reconnect=0`.

The deterministic fixture is read-only and synthetic. It uses the real Orion
bridge/HUD against a fake Hermes authority and performs no vault read, vault
mutation, real approval resolution, or protected action execution.

Implemented reconnect boundary:

- browser persistence contains only exact `session_id` + `run_id` as a
  `sessionStorage` locator hint;
- the locator carries no approval, success, recovery-availability, or action
  state;
- reload/reconnect re-queries authoritative Orion/Hermes run status;
- matching active run status may restore run lifecycle controls, but protected
  action state remains explicit **UNAVAILABLE** unless separate authoritative
  action evidence exists;
- terminal/expired run status falls back to persisted SessionDB action evidence;
- terminal run status alone never proves protected-action success;
- malformed, mismatched, poisoned, expired, or cross-session locators fail
  closed;
- late hydration from a previously selected session is discarded;
- selected-session disappearance clears locator and consequential presentation;
- historical recovery IDs remain historical; current recovery availability is
  still **UNAVAILABLE** without authoritative current inspection.

Stage A/B covers RC-01 through RC-10, including a fresh Orion HUD/bridge process
for RC-06. Installed-runtime qualification remains Stage C.

The Stage C read-only installed verifier is:

`scripts/phase5/p5-03c-installed-readonly-qualification.py`

It requires Hermes to be started manually, starts only a temporary loopback
Orion bridge, performs GET/read-only hydration, verifies the accepted installed
Hermes compatibility-patch identity, then stops only the temporary Orion bridge.
It records before/after source/worktree identity and refuses to run if
mutation-enabling environment state is present.

## Stage C installed read-only acceptance

Operator qualification passed against the installed COMPANION runtime.

Accepted Orion head:

`f6721ffbcb87805b1d827d5ca6463e2037939310`

Observed installed runtime:

- Hermes source head: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`;
- installed P5-03A2 Hermes API SHA-256:
  `7a206396aac7abe7e50fd5d346733fea85bb57160cb0a5d8a2e7feda29167c84`;
- Hermes listener: online on accepted loopback transport;
- persisted Hermes sessions observed: **17**;
- selected persisted session:
  `api_1789034057_7eeae131`;
- projected transcript rows: **25**;
- projected action-evidence rows in the selected session: **0**;
- current recovery visibility: **unavailable**.

Safety/truth results:

- mutation mode absent;
- no approval requested;
- no protected action executed;
- no vault read;
- no vault mutation;
- Orion worktree unchanged;
- Hermes worktree unchanged;
- installed Hermes source unchanged;
- temporary Orion bridge used the established in-process
  `OrionHTTPServer` pattern and was shut down deterministically.

Stage C disposition: **PASS**.

Because the selected live persisted session contained no completed protected
action evidence, Stage D must next follow the plan's least-risk evidence order:
first search existing persisted sessions for retained non-sensitive completed
action evidence. A new disposable protected action is not authorized unless
read-only discovery proves existing evidence is insufficient.

## Stage D retained-evidence discovery

Read-only discovery across the installed COMPANION SessionDB completed after
Stage C.

Observed:

- persisted sessions enumerated: **17**;
- qualifying completed protected-action evidence records: **0**;
- transcript bodies printed: **false**;
- raw tool results printed: **false**;
- vault read: **false**;
- vault mutation: **false**.

Discovery disposition: **PASS / NO RETAINED EVIDENCE AVAILABLE**.

Therefore Stage D cannot use preferred option 2 (retained non-sensitive
persisted test evidence).

The next candidate is a separately approved **isolated disposable
protected-action fixture**. It must reuse the already-qualified P5-02I
disposable-root guardrails and must not place synthetic action records into
the live Hermes SessionDB.

The proposed Stage D fixture will:

1. create temporary disposable vault/inbox/recovery roots under a neutral
   operator path;
2. obtain a fresh real Hermes human **ALLOW ONCE** or **DENY** decision for the
   exact disposable plan;
3. execute only the installed plugin's private disposable executor;
4. preserve the exact structured plugin result as the authoritative action
   result for the fixture;
5. present that result through an isolated fake-Hermes persisted session to
   the real Orion bridge/HUD;
6. reload the browser and restart the HUD/bridge process;
7. require the same completed action projection after each reconstruction;
8. poison browser-local state and require it to have no effect;
9. require current recovery visibility to remain **unavailable** unless a
   separate authoritative current inspector exists;
10. verify real vault/inbox remain untouched and clean up disposable roots on
    PASS.

This fixture is **not authorized for execution by this document update**.
Disposable mutation execution still requires explicit owner authorization.

## Stage D first execution finding

The owner-authorized disposable edit executed successfully far enough to create
and preserve a committed disposable fixture, but the first reconnect assertion
stopped at:

`generation_1_state:unknown`

This was **not** a reconnect regression and must not be fixed by weakening the
HUD projection threshold.

Root cause:

- the private disposable executor is older test-oriented machinery;
- its successful edit return includes
  `success=true`, `mutation_performed=true`,
  `recovery_required=false`, target-relative path, post-write hash, and the
  private recovery directory;
- unlike the production executor, that private return does **not** include the
  projection-required `action` and 64-hex `recovery_id`;
- P5-03A therefore correctly classified the incomplete result as
  `unknown / success_evidence_incomplete`.

The disposable fixture was intentionally preserved at:

`D:\Orion\orion-p5-03c-stage-d-xu_wj7s1`

No second mutation is required. The read-only resume verifier:

`scripts/phase5/p5-03c-stage-d-resume-reconstruction.py`

must validate the preserved committed manifest, receipt, recovery
classification, approval correlation, and current disposable target
postcondition. Only if all independent durable checks agree does it compose the
same bounded completion fields returned by the qualified production executor
(`action`, `recovery_id`, target, and completion flags) for an isolated
persisted-Hermes reconstruction test.

This composition is fixture-only, performs no new approval or mutation, does
not touch live SessionDB, and does not change the production HUD/projection
contract.

## Stage D accepted consequential reconnect result

The preserved owner-authorized disposable action was resumed read-only and
qualified successfully.

Accepted evidence:

- existing disposable mutation reused: **true**;
- new approval requested: **false**;
- new mutation performed: **false**;
- durable recovery classification: **committed**;
- durable receipt state: **committed**;
- durable receipt/recovery correlation: **valid**;
- current disposable target postcondition: **matches committed result**;
- composite evidence threshold preserved: **true**;
- projected action state: **succeeded**;
- projected durability: **completed_record**;
- current recovery visibility after reconstruction: **unavailable**;
- fresh-HUD-process reconstruction match: **true**;
- private recovery path egress: **false**;
- live Hermes SessionDB written: **false**;
- real vault/inbox touched: **false**.

Stage D disposition: **PASS**.

The first Stage D attempt's `unknown` projection remains an accepted
truth-boundary observation: the private disposable executor's incomplete
success return was insufficient for protected success. The production
projection threshold was not weakened. The resume gate instead required the
durable manifest, receipt, recovery inspection, approval correlation, and
current target postcondition to independently establish the fields that the
qualified production executor normally returns.

This closes the required consequential reconnect proof without a second
protected action.

The preserved temporary disposable fixture
`D:\Orion\orion-p5-03c-stage-d-xu_wj7s1` was removed through the bounded
cleanup gate after qualification.

Cleanup evidence:

- real vault/inbox targeted: **false**;
- disposable fixture cleaned: **true**;
- cleanup gate: **PASS**.

No production content or live SessionDB data was part of cleanup.

## Final P5-03C closure

P5-03C reconnect/hydration qualification is complete.

Accepted coverage:

- Stage A deterministic fixture: **PASS**;
- Stage B automated browser-state contract: **PASS**;
- Stage C installed read-only COMPANION qualification: **PASS**;
- Stage D retained-evidence discovery: **PASS / none available**;
- owner-authorized disposable consequential qualification: **PASS**;
- read-only reconstruction from preserved durable evidence: **PASS**;
- bounded disposable fixture cleanup: **PASS**.

The final implementation preserves these boundaries:

- browser persistence is locator-only;
- run status alone never proves protected-action success;
- completed protected-action success requires the existing P5-03A evidence
  threshold;
- incomplete successful-looking evidence remains `unknown`;
- pending approval is not reconstructed from browser storage;
- historical recovery IDs do not establish current recovery availability;
- cross-session and late-hydration evidence cannot bleed into the selected
  session;
- no browser action ledger, approval ledger, retry authority, or persistent
  SSE replay store was introduced;
- no production vault/inbox mutation was performed for P5-03C;
- no synthetic action evidence was written into live Hermes SessionDB;
- no Core artwork/behavior or presentation redesign was introduced.

The Stage D first-attempt `unknown` result is retained as positive evidence
that the projection fails closed when the private disposable executor omits
required production completion fields. Closure did not lower that threshold.

Final merge-readiness boundary:

- branch is based directly on accepted main
  `4fb9e0abe7e534f0aa8fbfa42d52e480681c30d5`;
- no base drift was present at closure review;
- changed paths are limited to reconnect/projection/bridge behavior,
  qualification tests/scripts, workflow gating, and this qualification record;
- production merge remains a separate repository action and is not performed
  by this closure record.

P5-03C disposition: **ACCEPTED / READY TO MERGE**.

## 1. Objective

Qualify reload, reconnect, HUD restart, and Hermes restart behavior for consequential presentation state without creating a second source of truth.

P5-03C is a truth/durability qualification unit. It is independent of the broader UI convergence pass and must remain independently testable.

## 2. Controlling invariants

The browser/HUD may retain identifiers as lookup hints, but consequential truth must be reconstructed only from authoritative evidence.

Accepted authority remains:

- Hermes session/run lifecycle;
- persisted Hermes SessionDB messages/tool results;
- accepted P5-03A projection;
- vault plugin structured results;
- approved recovery/receipt evidence when exposed through an authoritative read-only path.

The browser must never recreate consequential truth from:

- prior DOM text;
- JavaScript object state;
- localStorage/sessionStorage;
- cached presentation events;
- remembered approval cards;
- timing assumptions.

If authoritative evidence cannot establish a state after reconnect, the HUD must show:

- `unknown`;
- `unobserved`; or
- `unavailable`

as appropriate.

## 3. Current accepted baseline

P5-03A/P5-03B already provide:

- allowlisted action projection;
- read-only completed action-evidence hydration from persisted Hermes session messages;
- approval-response != execution-success semantics;
- selected-session switching/disappearance clearing;
- asynchronous hydration bound to the requesting session;
- no browser action ledger.

P5-03C must qualify the reconnect behavior around those existing mechanisms before adding new infrastructure.

## 4. Scenario matrix

### RC-01 — Ordinary completed conversation reload

Procedure:

- complete an ordinary typed turn;
- reload browser;
- remove browser-local presentation state;
- reselect/recover the same persisted Hermes session.

Expected:

- transcript comes from persisted Hermes session messages;
- no duplicate session is created;
- no stale transient tool/approval state is recreated.

### RC-02 — Completed protected-action evidence reload

Use deterministic fixture or approved persisted test evidence.

Expected:

- completed action state reconstructs only from persisted structured tool/result evidence;
- operation/target/result may reappear when authoritative evidence supports them;
- current recovery availability is **not** inferred from historical recovery ID alone.

### RC-03 — Reload during active stream

Expected:

- browser does not assume the run continued;
- any remembered run ID is locator-only;
- authoritative run status may be queried while still available;
- persisted session evidence is fallback;
- if neither source establishes consequential state, show unavailable/unknown.

### RC-04 — Reload while approval is pending

Expected:

- prior approval card is not recreated from browser cache;
- no decision controls appear unless the authoritative active transport/source proves a current pending approval;
- absent authoritative evidence => approval/action unavailable or unobserved.

### RC-05 — Reload after approval acknowledgement, before action result

Expected:

- approval may be known only if authoritative evidence still proves it;
- protected execution must remain unproven;
- no success animation/card from prior browser state;
- later persisted action result, if any, controls outcome.

### RC-06 — HUD process restart

Expected:

- same rules as browser reload;
- process memory contributes no authority.

### RC-07 — Hermes restart

Expected:

- live run state and pending approval state are treated as non-durable unless Hermes itself persists them;
- persisted session/tool evidence remains usable;
- expired/missing run lookup must not be converted into success/failure assumptions.

### RC-08 — Session disappearance/switch race

Expected:

- late hydration response for prior session is discarded;
- prior approval/evidence disappears;
- no cross-session bleed.

### RC-09 — Hydration failure / 404 / malformed / unavailable

Expected:

- prior action evidence is cleared;
- explicit unavailable/unknown state is used;
- stale evidence remains hidden.

### RC-10 — Browser-state poisoning

Before reload, deliberately place fake state in:

- DOM text;
- JavaScript presentation object;
- localStorage/sessionStorage where applicable.

Expected:

- fake approval/success/recovery state cannot survive as authoritative truth;
- no second persistent action record appears.

## 5. Qualification architecture

### Stage A — Deterministic isolated fixture

Build a dedicated reconnect fixture around the real Orion bridge/HUD with fake authoritative Hermes responses.

The fixture must support controlled transitions for:

- persisted completed result;
- active run status;
- missing/expired run;
- approval previously seen but not authoritatively available;
- session switch/disappearance;
- delayed hydration race;
- hydration failure;
- contradictory browser-local state.

This stage must not access live vault contents or perform mutation.

### Stage B — Automated browser-state contract tests

Add focused tests proving:

- browser state cannot manufacture consequential truth;
- hydration is session-bound;
- completed evidence only comes from projected persisted source;
- approval controls require current authoritative pending state;
- run lookup fallback rules;
- recovery availability remains unavailable when no current authoritative recovery inspector exists.

### Stage C — Installed read-only runtime qualification

After the hardware change and runtime sanity checks:

- start Orion normally;
- use accepted COMPANION session;
- exercise ordinary conversation reload/restart behavior;
- inspect real persisted session continuity;
- do not consume mutation unless a separately approved consequential fixture is required.

### Stage D — Consequential reconnect qualification

Use the least-risk authoritative fixture that satisfies the PRD:

Preferred order:

1. isolated authoritative persisted-action fixture;
2. retained non-sensitive persisted test evidence;
3. separately approved disposable protected-action fixture only if the first two cannot prove the required installed behavior.

Do not use production vault content merely to test presentation durability.

## 6. Recovery-status decision

Do **not** add a recovery-status endpoint by default.

First run P5-03C with the existing contract:

- historical recovery ID may be displayed as historical evidence;
- current recovery availability remains `unavailable` unless an authoritative current read-only source exists.

Only if acceptance shows the UX materially requires current recovery availability should a separate narrow read-only recovery-inspection design be opened.

That endpoint, if later required, must not expose:

- recovery directory paths;
- backup bytes;
- secrets;
- arbitrary filesystem access.

## 7. Required tests

Minimum automated coverage:

- completed action survives reload from persisted source only;
- fake local success does not survive reload;
- fake local approval does not survive reload;
- approval acknowledgement never becomes success;
- active run lookup controls live reconnect claim;
- expired run => persisted fallback;
- no persisted result => unavailable;
- delayed hydration from old session discarded;
- selected session disappearance clears evidence;
- malformed/failed hydration clears evidence;
- historical recovery ID != recovery available;
- no browser/local persistent action database is introduced.

## 8. Runtime acceptance evidence

Record:

- exact Orion head;
- exact Hermes accepted head/package;
- listener/bind state;
- session ID continuity;
- run IDs used only as locators;
- browser storage state before/after where relevant;
- persisted-message source used for reconstruction;
- absence of secret/private field egress;
- worktree clean;
- no unintended vault mutation;
- clean Stop Orion at end.

## 9. Interaction with UI convergence

The two tracks are intentionally separate.

Recommended order after GPU stabilization:

1. hardware/runtime sanity check;
2. UI convergence implementation;
3. UI convergence source/visual acceptance;
4. P5-03C reconnect/hydration qualification against the converged HUD.

Reason:

- reconnect truth is primarily architecture/data-flow behavior;
- running final reconnect acceptance against the converged UI avoids repeating browser-level acceptance after a major layout rewrite;
- no UI convergence implementation may weaken the existing hydration/truth rules.

If reconnect work uncovers a source-truth defect during UI implementation, fix the truth defect separately and re-gate before continuing visual polish.

## 10. Explicit non-goals

P5-03C shall not:

- create an Orion event database;
- create a persistent approval record;
- create an action ledger;
- persist raw SSE for replay;
- make localStorage authoritative;
- introduce retry semantics;
- invent protected `executing`;
- infer current recovery availability from historical IDs;
- alter vault mutation/recovery semantics;
- redesign the UI beyond what is necessary to present explicit unavailable/unknown state.

## 11. Stop conditions

Stop and open a separate architecture decision if qualification appears to require:

- a new generalized event bus;
- a second session store;
- a second approval system;
- browser-owned durable action state;
- mutation changes;
- broad Hermes fork beyond a narrow compatibility fix;
- current recovery claims without an authoritative read-only source.

## 12. Completion definition

P5-03C is complete when all required reconnect scenarios pass and the HUD can be reloaded/restarted without fabricating approval, success, failure, recovery, or actionability.

The accepted outcome may legitimately be `unknown`, `unobserved`, or `unavailable` when authoritative evidence is absent.
