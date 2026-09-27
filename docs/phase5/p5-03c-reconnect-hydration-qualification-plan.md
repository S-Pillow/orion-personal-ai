# P5-03C Reconnect / Hydration Qualification Plan

Status: **PLANNING / READY FOR QUALIFICATION AFTER HARDWARE STABILIZATION**

Date: 2026-09-27  
Base main: `e55517bfc33b93a0983026a3a494d6df86c9532f`

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
