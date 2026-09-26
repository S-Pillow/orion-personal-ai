# P5-03A2 — Hermes Transport Qualification Decision

Status: **QUALIFICATION COMPLETE / DECISION CANDIDATE / REVIEW REQUIRED**

Branch: `feature/orion-phase5-p5-03a2-transport-qualification`

Base commit: `6fa1784ccf40fb91ed736ad84c56ccb2942642e5`

Qualification date: 2026-09-26

## 1. Purpose

P5-03A2 begins by qualifying the Hermes transport that Orion may use for approval-capable protected-action turns.

The question is:

> Can Hermes `/v1/runs` preserve Orion's accepted COMPANION persisted-session semantics while providing native run-scoped approval, or is a narrowly bounded compatibility correction to the existing session-chat transport required?

This document records the qualification result only. It does not implement the transport change.

## 2. Controlling architectural boundary

The accepted architecture remains:

- **Hermes Agent** owns runtime, session/run lifecycle, approval transport/resolution, and persisted SessionDB conversation state.
- **orion-vault-actions** owns deterministic preview, immutable plan binding, protected-action qualification, stale-state revalidation, mutation, structured action results, and recovery/receipt semantics.
- **Orion bridge/HUD** is a narrow presentation/projection layer.
- **Browser state** is never consequential action truth.

Intent Preservation Check:

> Are we preserving Hermes as runtime/session/approval authority, the vault plugin as deterministic protected-action executor/evidence source, and Orion as a narrow projection layer?

A negative or uncertain answer blocks implementation.

## 3. Qualification baseline

Observed Orion state:

| Item | Result |
| --- | --- |
| Orion branch | `feature/orion-phase5-p5-03a2-transport-qualification` |
| Orion HEAD | `6fa1784ccf40fb91ed736ad84c56ccb2942642e5` |
| Orion worktree | clean |
| Hermes commit | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |
| Hermes package/tag baseline | accepted P5-03A1 baseline |
| Hermes listener on `127.0.0.1:8642` | not listening |
| `ORION_P5_MUTATION_MODE` | absent |
| Vault read | none |
| Vault mutation | none |
| Approval request | none |
| Runtime config change | none |
| Source change during qualification | none |

### Accepted P4-04A installed Hermes state

The Hermes checkout is intentionally dirty because the accepted P4-04A audio gateway compatibility patch modifies:

`gateway/platforms/api_server.py`

The installed state was verified through the existing source-controlled P4-04A verifier.

Accepted live SHA-256:

`ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888`

Accepted backup SHA-256:

`8d87036dd488cb811dbabb7048102d0c28fbf54e0e658c464683000118537ec3`

Patch ID:

`ORION-P4-04A-HERMES-AUDIO-GATEWAY-v1`

The only expected Hermes worktree differences are:

- modified `gateway/platforms/api_server.py`;
- `gateway/platforms/api_server.py.orion-p4-04a.bak`;
- `gateway/platforms/api_server.py.orion-p4-04a.json`.

This is accepted known state, not unexplained source drift.

## 4. Existing session-chat transport findings

Current Orion uses:

`POST /api/sessions/{session_id}/chat/stream`

The installed Hermes source confirms this route:

- requires an existing Hermes session;
- loads persisted conversation history from SessionDB;
- uses persisted/runtime session-selection semantics;
- applies and persists the session model-lock contract;
- runs through the existing session-oriented agent path;
- emits the accepted conversation/run lifecycle used by the HUD.

However, the same handler does **not**:

- register its generated `run_id` in Hermes `_run_approval_sessions`;
- register a run-scoped `gateway_notify` approval callback.

Qualification result:

| Session-chat property | Result |
| --- | --- |
| Requires existing session | true |
| Loads persisted history | true |
| Uses persisted runtime semantics | true |
| Persists model lock | true |
| Registers run approval session | **false** |
| Registers gateway approval notify | **false** |

Therefore the existing session-chat transport preserves accepted Orion session semantics but lacks the native interactive run-scoped approval round trip required for protected-action UX.

## 5. `/v1/runs` transport findings

Hermes `/v1/runs` provides the native run-scoped approval machinery:

- assigns a unique `run_id`;
- uses `run_id` as the approval-session key;
- stores that mapping in `_run_approval_sessions`;
- registers the native gateway approval notify callback;
- emits `approval.request`;
- supports `POST /v1/runs/{run_id}/approval`;
- emits `approval.responded`;
- returns `202` on run creation;
- exposes pollable run status and an SSE event stream.

Qualification result:

| `/v1/runs` property | Result |
| --- | --- |
| Accepts `session_id` | true |
| Requires selected session to already exist | **false** |
| Loads selected session persisted history itself | **false** |
| Uses existing persisted session runtime semantics | **false** |
| Persists/applies session model-lock contract | **false** |
| Registers run approval session | true |
| Registers gateway approval notify | true |
| Passes `session_id` to created agent | true |
| Accepts caller-provided `conversation_history` | true |
| Returns `202` on start | true |

The agent finalizer can persist a run when supplied a session ID/history, but that does not make `/v1/runs` a native replacement for the accepted session-chat contract.

Using `/v1/runs` as Orion's primary conversation transport would require Orion or another compatibility layer to reproduce session existence checks, transcript hydration, runtime/model selection, and model-lock behavior that the current session-chat route already owns.

That would widen the integration surface and increase the risk that Orion becomes responsible for reconstructing Hermes session semantics.

## 6. Decision

### Selected direction: **Option B — narrow session-chat approval compatibility correction**

P5-03A2 should preserve:

`POST /api/sessions/{session_id}/chat/stream`

as the approval-capable conversation path and add only the minimum Hermes compatibility wiring required to give that session-chat run the same native run-scoped approval registration/resolution behavior already used by `/v1/runs`.

### Option A disposition

**Option A is not selected as a drop-in transport replacement.**

`/v1/runs` has the approval behavior Orion needs, but it does not natively preserve the full accepted session-chat contract.

A bridge-side reconstruction of those semantics would be a broader and less authority-preserving change than correcting the missing approval registration at the existing session-chat boundary.

This does not declare `/v1/runs` invalid or unusable generally. It only rejects it as the preferred Orion replacement transport for this ticket.

## 7. Exact compatibility implementation boundary

The follow-on implementation unit may change Hermes only as necessary to make the existing session-chat run participate in the native run-scoped approval mechanism.

The implementation should:

1. preserve the existing `session_id` and session-chat persistence behavior;
2. preserve existing transcript loading and model/runtime selection;
3. preserve the session model-lock path;
4. keep each live approval isolated to its exact generated `run_id`;
5. register that run with Hermes' existing approval-session mapping;
6. register the same native gateway approval notify mechanism used by `/v1/runs`;
7. surface the exact native `approval.request` payload through the session-chat stream;
8. allow the existing Hermes `POST /v1/runs/{run_id}/approval` endpoint to resolve only that run's pending decision;
9. unregister/clean approval state when the run completes, fails, is interrupted, or is drained;
10. preserve existing disconnect/stop behavior;
11. use existing Hermes approval authority rather than introducing a new one.

## 8. Explicit non-goals

The compatibility implementation must not:

- create a second approval engine;
- create an Orion approval store;
- create a new session authority;
- create a durable Orion event/action ledger;
- add a general-purpose broker/event bus;
- change vault mutation semantics;
- change vault stale-plan rules;
- change recovery semantics;
- enable mutation mode;
- perform a protected vault action as part of qualification;
- change the accepted COMPANION model;
- upgrade Hermes or other dependencies as part of this ticket;
- remove or rewrite the accepted P4-04A audio patch;
- implement P5-03B visual redesign;
- begin reconnect qualification beyond what is necessary to prove cleanup/fail-closed behavior.

## 9. Minimum implementation tests

Before any installed Hermes deployment, the source-controlled compatibility candidate should prove at minimum:

### Session preservation

- existing session is still required;
- persisted conversation history is still loaded by Hermes;
- selected session/runtime/model behavior is unchanged;
- model-lock behavior is unchanged.

### Approval isolation

- two runs sharing one `session_id` receive distinct approval namespaces;
- resolving approval for run B cannot release run A;
- invalid/non-pending run approval still fails closed;
- accepted approval response proves decision resolution only.

### Lifecycle cleanup

- approval registration exists while the session-chat run is live;
- registration is removed after completion;
- registration is removed after failure;
- registration is removed after cancellation/disconnect;
- no orphaned approval queue remains after drain.

### Event truthfulness

- native `approval.request` is emitted for the exact live run;
- browser/HUD receives no approval rule keys, pattern keys, credentials, or provider secrets;
- generic `tool.completed` or `run.completed` is not redefined as protected-action success.

### Regression safety

- ordinary non-approval session-chat still works;
- persisted SessionDB transcript remains correct;
- existing P4-04A audio routes remain present and unchanged;
- existing Orion HUD session/chat behavior remains compatible.

## 10. Deployment boundary

Any Hermes source change is a separate, source-controlled, reversible compatibility patch.

Before installation:

- exact accepted Hermes source identity must be checked;
- interaction with the already-installed P4-04A patch must be deterministic and explicitly verified;
- the combined installed-file identity must be known;
- patch application must fail closed on unexpected source state;
- rollback must preserve the accepted P4-04A state rather than blindly restoring pristine upstream Hermes.

No installed Hermes source modification is authorized by this qualification document alone.

## 11. P5-03A2 implementation handoff

Recommended next source-control unit after this decision is reviewed and merged:

`feature/orion-phase5-p5-03a2-session-chat-approval-compat`

That unit should contain only:

- the narrow Hermes compatibility patch tooling/source candidate;
- focused no-mutation tests for session preservation and approval isolation;
- deterministic apply/verify/rollback handling that composes with P4-04A;
- implementation evidence and acceptance documentation.

Only after that compatibility unit is accepted should P5-03A2 continue into the Orion browser-safe projection implementation.

## 12. Final qualification disposition

**P5-03A2 transport qualification: PASS**

**Selected direction: Option B — preserve session-chat and add the minimum native Hermes run-scoped approval compatibility wiring.**

The qualification establishes architecture direction only.

It does **not** authorize:

- Hermes source mutation;
- runtime deployment;
- mutation mode;
- vault mutation;
- protected-action execution;
- P5-03B work.
