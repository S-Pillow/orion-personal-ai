# P6-05 Reminder CRUD + HUD — Correction/Resume Plan

Status: **IMPLEMENTATION WRITTEN LOCALLY / FINAL QUALIFICATION PENDING**

Date: 2026-10-05

Accepted Orion repository base/head for the local P6-05 worktree:

- repository: `D:\Orion\orion-personal-ai`
- branch: `feature/p6-05-reminder-crud-hud`
- commit: `69309e1559428ffee0455ed9f476222600e392a4`

Accepted Hermes baseline:

- tag: `v2026.8.27`
- package: `0.20.6`
- commit: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- profile: `companion`
- COMPANION home: `%LOCALAPPDATA%\hermes\profiles\companion`

This document is the durable resume point for P6-05 after the 2026-10-05 correction session.

## 1. Architecture and authority boundary

The Phase 6 architecture remains unchanged:

- Hermes is the authoritative reminder scheduler and durable job owner.
- Orion must not add a second general scheduler, timer daemon, background watcher, or scheduler-owning service.
- Orion P6-05 is a bounded adapter, bridge, browser-safe projection, and HUD control surface over the accepted Hermes cron implementation.
- The primary adapter seam remains the accepted P6-02 Candidate A contract: local invocation of `tools.cronjob_tools.cronjob()` with `HERMES_HOME` explicitly bound to the COMPANION profile.
- Ordinary reminder CRUD may list, get, create, pause, resume, and cancel Orion-owned reminders only.
- P6-05 must never expose or invoke Hermes `run` through the reminder UI/API.
- Browser presentation is not durable authority.
- Manual-off remains controlling: the HUD must not start Hermes and must not treat conversation-gateway offline state as proof that durable reminder state is unavailable.

No production reminder, live delivery, COMPANION configuration mutation, Hermes restart, or P6-06 acceptance is authorized by this plan.

## 2. Work completed before the 2026-10-05 correction

The P6-05 branch already contained the repository-only implementation across exactly twelve local working-tree paths:

Tracked modifications:

- `hud/orion_hud_bridge.py`
- `hud/static/app.js`
- `hud/static/index.html`
- `hud/static/target-layout.css`
- `hud/static/workspace-state.js`
- `hud/tests/test_phase3_workspace.py`

New files:

- `hud/reminder_adapter.py`
- `hud/reminder_projection.py`
- `hud/tests/test_reminder_adapter.py`
- `hud/tests/test_reminder_bridge.py`
- `hud/tests/test_reminder_projection.py`
- `hud/tests/test_reminder_workspace.py`

Previously accepted repository-only gates established:

- native structured Hermes CRUD adapter path;
- strict Orion-owned reminder filtering and mutation ownership checks;
- no generic cron proxy;
- no manual `run` route;
- exact reminder/run correlation;
- same-origin mutation enforcement;
- browser-safe projection with raw prompt/provider/base URL/process/error details omitted;
- fourth HUD workspace: `CONVERSATION | REMINDERS | SYSTEM | MEMORY`;
- bridge unavailability fails closed without taking the conversation HUD down.

Before final review, the focused gate passed 95 tests:
28 frontend-hardening + 33 reminder + 10 Phase 3 workspace + 8 UI convergence + 14 bridge + 2 POST-close.

## 3. Final-review findings that required correction

The final implementation review found four real contract gaps:

1. **Hermes version gate**  
   The adapter hard-gated the accepted Hermes commit but did not also hard-gate package/project version `0.20.6`, despite the frozen P6-02 contract requiring commit + version qualification.

2. **Reminder refresh coupled to conversation gateway online state**  
   `refreshReminders()` was behind the `payload.hermes.online` branch. This incorrectly made the HUD declare reminder authority unavailable when the conversation gateway was offline, even though durable Hermes reminder state is a separate authoritative surface.

3. **Unsupported schedule examples in the HUD**  
   The create form advertised prose such as `tomorrow at 9am` and `every weekday at 8am`. The accepted Hermes parser proof only established forms including `30m` and `every 30m` for this Orion contract.

4. **Create path did not bind an explicit delivery intent**  
   The local adapter has no live chat origin from which Hermes could infer a delivery destination. The accepted Hermes `cronjob()` surface supports `deliver`, and its structured job projection includes the stored delivery token.

A separate read-only review also established that `HERMES_PROFILE` is not part of the accepted pin's cron-home precedence for this adapter; explicit `HERMES_HOME` remains the correct profile-binding control.

## 4. Research conclusions used for the correction

Research against the accepted Hermes pin established:

- `tools.cronjob_tools.cronjob()` accepts `deliver: Optional[str] = None`;
- native create routes `deliver` through Hermes' own normalization/context-resolution path;
- formatted native job output includes the persisted `deliver` field, allowing Orion to verify the create result rather than assuming the option was honored;
- `deliver="discord"` is a native platform delivery intent;
- actual fire-time Discord delivery still depends on Hermes resolving a configured Discord home destination;
- historical Orion acceptance already recorded that the accepted COMPANION setup did not have a Discord home channel configured;
- therefore P6-05 should bind the intended native delivery token but **must not** configure a channel or claim live Discord delivery;
- exact Discord delivery remains a P6-06 prerequisite and live acceptance item.

The earlier patch-generation failures were not architecture failures. They were caused by brittle byte/format-sensitive edit scripts being applied to a dirty working tree. That method is retired for this correction.

## 5. Correction successfully written on 2026-10-05

The semantic correction script reached:

- `P6_05_CORRECTION_SCOPE=PASS`
- `P6_05_HERMES_BASELINE=PASS`
- `P6_05_SEMANTIC_CORRECTION_WRITE=PASS`

The corrected local P6-05 source now includes:

- `EXPECTED_HERMES_VERSION = "0.20.6"`;
- runtime project-version qualification through the accepted Hermes checkout's `[project]` metadata;
- fail-closed version mismatch behavior;
- `REMINDER_DELIVERY_TARGET = "discord"`;
- native create with `deliver=REMINDER_DELIVERY_TARGET`;
- verification that Hermes' returned job preserved the requested delivery token;
- schedule UI examples narrowed to `30m or every 30m`;
- bridge test fixtures changed from unsupported prose schedule syntax to `30m`;
- `refreshReminders()` executed independently before the conversation `if (online)` branch;
- scheduler-active / scheduler-inactive presentation derived from reminder authority response;
- removal of the false statement `Hermes offline // reminder authority unavailable`.

The correction then passed:

- Python compile;
- frontend hardening: **28/28**;
- reminder suite: **36/36**.

The reminder-suite increase from 33 to 36 includes new regression coverage for:

- Hermes project-version reading;
- version mismatch fail-closed behavior;
- accepted schedule examples / reconnect-independent reminder refresh behavior.

## 6. Current stopping point: one stale Phase 3 static assertion

The correction did **not** fail because the new reminder behavior was incorrect.

`hud/tests/test_phase3_workspace.py::test_status_observations_sync_before_online_branch`
still asserts the old byte-adjacent sequence:

`syncSystemWorkspace();` immediately followed by `if (online) {`.

The corrected architecture intentionally inserts:

`await refreshReminders();`

between those statements so reminder authority is refreshed independently of conversation-gateway online state.

The existing test's semantic intent is still valid: bridge/credential observations must be synchronized before the online-only conversation branch. The test implementation is now stale because it encodes adjacency instead of ordering.

No further source correction should be reapplied. The next edit is **test-only**.

## 7. Exact next implementation unit

Modify only:

`hud/tests/test_phase3_workspace.py`

Replace `test_status_observations_sync_before_online_branch` with a function-scoped ordering contract that:

1. isolates the `refreshStatus` source block;
2. proves bridge status assignment is present;
3. proves credential status assignment is present;
4. proves `syncSystemWorkspace();` is present;
5. proves `await refreshReminders();` is present;
6. proves `if (online) {` is present;
7. asserts ordering:
   - bridge observation
   - credential observation
   - system-workspace synchronization
   - authoritative reminder refresh
   - conversation-online branch

This preserves the original Phase 3 contract and adds the accepted P6-05 independence requirement without relying on exact multiline formatting.

Do not rerun any of the earlier correction scripts. They already wrote the intended P6-05 source correction.

## 8. Final qualification gate after the test-only repair

Run, in this order:

1. Python compile for reminder adapter/projection/bridge.
2. `test_phase3_workspace.py` targeted regression: expect 10/10.
3. frontend hardening: 28 tests.
4. reminder suite: 36 tests.
5. Phase 3 workspace: 10 tests.
6. UI convergence: 8 tests.
7. bridge regression: 14 tests.
8. POST connection-close regression: 2 tests.

Focused expected total: **98 passing tests**.

Then run the complete HUD Python discovery:

`python -m unittest discover -s .\hud\tests -p "test_*.py" -v`

Record the observed count rather than assuming a fixed total.

Finally:

- `git diff --check`;
- verify exactly the same twelve P6-05 working-tree paths and no others;
- inspect the final diff;
- write a read-only final correction report;
- confirm no `run` reminder route/control;
- confirm no generic cron proxy;
- confirm unsupported schedule prose is absent;
- confirm the version gate is present;
- confirm reminder refresh precedes the conversation `online` gate;
- confirm Discord delivery intent is bound but no live-delivery claim is made.

Only after that gate is green should P6-05 be considered **ready for commit authorization**.

## 9. P6-06 carry-forward

P6-06 remains a separate live-acceptance phase. It must not be folded into the P6-05 repository gate.

The live matrix still needs to prove, under separate explicit authorization:

- one bounded live one-shot;
- actual Discord delivery;
- HUD projection/reconnect;
- manual-off missed-reminder behavior;
- restart/interrupted-run `unknown`;
- duplicate suppression;
- delivery failure;
- sibling failure isolation;
- corruption preservation using disposable evidence where destructive testing is required.

Because the accepted COMPANION configuration historically has no Discord home channel configured, P6-06 must first qualify/configure an exact delivery destination under a separate production-configuration authorization. P6-05 must not silently create one.

## 10. Prepared continuation tooling

Use:

`scripts/phase6/Invoke-P6-05-FinalizeCorrection.ps1`

The script is deliberately a **resume/finalize** gate, not another source correction script. It:

- verifies the exact Orion branch/head and twelve-path working-tree scope;
- verifies the 2026-10-05 semantic source correction is already present;
- performs only the one AST-scoped stale-test repair if required;
- compiles the candidate before writing it;
- runs the targeted + focused + full HUD regression gates;
- checks `git diff --check`;
- rechecks the twelve-path scope;
- writes a final report under `%TEMP%`.

It does not commit, push, merge, deploy, start/restart Hermes, create/run a reminder, or change COMPANION configuration.

## 11. Resume rule

At the next session, start from this document and the prepared finalization script.

Do **not**:
- regenerate the whole P6-05 implementation;
- rerun earlier brittle patch/correction scripts;
- change the accepted Hermes pin;
- configure Discord as a side effect of P6-05;
- claim P6-05 closed merely because the 36 reminder tests pass.

The immediate next goal is narrow:

> repair one stale Phase 3 static test, run the complete final gate, review the final twelve-file diff, then decide whether P6-05 is ready for commit authorization.
