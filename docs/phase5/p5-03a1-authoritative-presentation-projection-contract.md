# P5-03A1 — Authoritative Presentation / Projection Contract Discovery

Status: **DISCOVERY COMPLETE / CONTRACT CANDIDATE REV 2 / REVIEW REQUIRED**

Branch: `feature/orion-phase5-p5-03a1-projection-contract`

Base commit: `d67ad25dbff60f106aae27ae67f9f6546e19d035`

Discovery date: 2026-09-26

## 1. Scope and non-goals

P5-03A1 defines the authoritative presentation/projection contract that P5-03A2 may implement and P5-03B may render.

Central invariant:

> The UI may simplify presentation, but it may never lower the evidence threshold required to make a claim.

The Orion HUD is a projection layer. It is not a second runtime authority, approval engine, session authority, persistence engine, action ledger, recovery authority, or protected-action executor.

This ticket does **not**:

- change Hermes;
- change the installed Orion vault-actions plugin;
- start Hermes;
- enable mutation mode;
- request approval;
- read or mutate the vault/inbox;
- add a general-purpose event bus, broker, or durable event store;
- redesign the HUD;
- implement P5-03A2 or P5-03B;
- change Phase 4 voice work;
- begin Phase 6 scheduler/reminder work.

## 2. Current accepted architecture

Authoritative ownership remains:

- **Hermes Agent**: agent runtime, session/run lifecycle, tool lifecycle, generic approval transport/resolution, persisted SessionDB transcript.
- **orion-vault-actions plugin**: deterministic preview semantics, immutable plan binding, protected-action approval qualification, stale-state revalidation, protected mutation, structured action result, recovery/receipt semantics.
- **Orion HUD bridge**: narrow loopback adapter and future browser-safe projection layer.
- **Browser HUD**: presentation only.
- **Obsidian vault**: durable human-authored document store.
- **iai**: persistent memory authority.

Intent Preservation Check:

> Are we solving this in a way that preserves why Hermes is runtime authority, the vault plugin is deterministic executor/evidence source, and the Orion bridge/HUD is a narrow projection layer?

A negative or uncertain answer blocks implementation.

## 3. Installed/runtime discovery

The read-only P5-03A1 discovery gate passed with exit code 0.

Observed local state:

| Item | Observed value |
| --- | --- |
| Orion repo | `D:\Orion\orion-personal-ai` |
| Branch | `feature/orion-phase5-p5-03a1-projection-contract` |
| Base/head | `d67ad25dbff60f106aae27ae67f9f6546e19d035` |
| Worktree | clean |
| Hermes checkout | `%LOCALAPPDATA%\hermes\hermes-agent` |
| Hermes commit | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |
| Hermes tag | `v2026.8.27` |
| Hermes package | `0.20.6` |
| Hermes state | manual-off |
| COMPANION config SHA-256 | `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7` |
| Accepted config match | true |
| Mutation mode persisted | false |
| Parent mutation env present | false |
| Production recovery root persisted | true |
| Installed vault plugin | `0.3.0` |
| Installed plugin source matches repo | true |
| Live recovery records | 0 |
| P5-02Y cleanup audit count | 1 |
| P5-02Y audit SHA-256 | `9AFF3BFF771EE8745642510C5F4561DE3F8395C490E0D24FC22563CC85650537` |

The gate reported:

- no vault read;
- no vault mutation;
- Hermes not started;
- no approval requested;
- no runtime configuration change;
- no dependency change.

### Discovery note: historical recovery vs current recovery

P5-02Y pruned the five completed canary recovery directories. The live production recovery inventory is now 0 records.

The retained P5-02Y external audit is **historical evidence of what existed and was removed**. It is not evidence that any pruned recovery is currently available.

Any repository wording that still describes those pruned records as currently valid/live must not be used as runtime authority.

## 4. Authoritative evidence inventory

### 4.1 Hermes session/run surfaces

Pinned installed Hermes source confirms the following relevant surfaces.

#### Session chat stream

`gateway/platforms/api_server.py::_handle_session_chat_stream`

The existing Orion HUD uses:

`POST /api/sessions/{session_id}/chat/stream`

Observed session-chat-stream event vocabulary includes:

- `run.started`
- `message.started`
- `assistant.delta`
- `tool.progress`
- `tool.started`
- `tool.completed`
- `tool.failed` as a supported handler name, although the current executor primarily reports terminal tool state through `tool.completed` plus an error classification upstream
- `assistant.completed`
- `run.completed`
- `run.cancelled`
- `error`

Important correction from architecture review:

The accepted `POST /api/sessions/{session_id}/chat/stream` implementation does **not** register its generated `run_id` in Hermes `_run_approval_sessions`, and it does not register a run-scoped gateway approval notify callback. Therefore the current production session-chat-stream path is **not proven to emit or resolve live `approval.request` events through `POST /v1/runs/{run_id}/approval`**.

The browser already contains an `approval.request` handler, but browser support is not evidence that the accepted production session transport emits that event.

Each session-stream payload is assigned:

- `session_id`
- `run_id`
- `seq`
- `ts`

The session stream creates a Hermes run status entry before execution and updates it through the run lifecycle.

#### Pollable run status

Hermes exposes:

`GET /v1/runs/{run_id}`

Run status contains, at minimum:

- `object = hermes.run`
- `run_id`
- `status`
- `created_at`
- `updated_at`
- `last_event` when provided by the lifecycle path
- additional bounded fields such as session ID, output/error/usage where that lifecycle path records them.

Terminal run status is in-memory and retained for a bounded TTL. In the accepted Hermes source:

- run stream transport TTL: 300 seconds;
- terminal run status TTL: 3600 seconds.

A run status is therefore useful reconnect evidence while present, but is **not durable action history**.

#### Persisted session transcript

Hermes exposes:

`GET /api/sessions/{session_id}/messages`

The response is projected through a client-safe message shape including:

- `id`
- `session_id`
- `role`
- `content`
- `tool_call_id`
- `tool_calls`
- `tool_name`
- `timestamp`
- selected display/runtime metadata.

The accepted session stream also includes an authoritative per-turn transcript on `run.completed` in its `messages` field. Hermes source explicitly describes this transcript as ground truth for reconciling the live SSE view with persisted state.

This is a primary P5-03 completed-action evidence source.

### 4.2 Hermes tool lifecycle semantics

Pinned Hermes `agent/tool_executor.py` shows:

- `tool.started` is emitted before tool execution;
- canonical tool results are persisted/appended before completion projection;
- Hermes classifies structured JSON tool results with `success=false` plus `error/message` as tool failures;
- `tool.completed` is still the lifecycle callback used after the canonical result lands, with an `is_error` flag in the callback.

Important transport limitation:

The current **session chat stream adapter** does not forward the callback's `is_error`, `result`, or `duration` fields in its `tool.completed` event. It currently forwards only:

- `message_id`
- `tool_name`
- `preview`
- `args`.

Therefore a browser must **not** interpret session-stream `tool.completed` as proof of successful action execution.

The authoritative action result is the persisted tool result / `run.completed.messages`, not the generic visual completion event.

### 4.3 Hermes approval semantics

The pinned Hermes approval system is the runtime approval authority.

For Hermes' explicit `/v1/runs` surface:

- Hermes creates a run-scoped approval session keyed to that `run_id`;
- Hermes registers a gateway notify callback for the run;
- `approval.request` contains a redacted command/display target, description, allowed choices, `run_id`, and timestamp;
- `POST /v1/runs/{run_id}/approval` accepts canonical choices `once|session|always|deny`;
- a successful resolution returns:
  - `object = hermes.run.approval_response`
  - `run_id`
  - `choice`
  - `resolved`;
- Hermes emits `approval.responded` on that run surface after successful resolution;
- the endpoint returns conflict when there is no active/pending approval.

A successful approval HTTP response proves only that Hermes resolved the pending approval decision for that run.

It does **not** prove:

- that the vault plugin accepted the decision as sufficient for protected mutation;
- that protected execution began;
- that a filesystem mutation happened;
- that postconditions succeeded.

For the vault plugin specifically, only a fresh human `once` decision observed through the matching plugin approval attempt qualifies the protected executor.

### 4.3.1 Current Orion HUD approval-transport gap

The current Orion typed conversation bridge posts to:

`/api/sessions/{session_id}/chat/stream`

That accepted Hermes handler creates a `run_id` and pollable run status, but the pinned source does not add that run to `_run_approval_sessions` and does not install the run-scoped gateway notify callback used by `/v1/runs`.

Inside the generic API session, Hermes still recognizes the call as a gateway/API approval context. Without a registered notify callback, the approval engine can fall back to a pending/approval-required result instead of producing the same interactive run-scoped round trip used by `/v1/runs`.

Therefore the current HUD's ability to render an `approval.request` event and POST an approval choice is **not proof that the accepted production session-chat transport can complete a live protected vault approval**.

The existing `hud/tests/probe_real_hermes_approval_surface.py` is valuable but deliberately uses an isolated fixture that wires the real Hermes approval engine to a fixture run/approval endpoint. It proves the HUD/bridge can render and submit a real Hermes approval decision without mutation; it does **not** prove the production `/api/sessions/{session_id}/chat/stream` path has equivalent approval registration.

This is a P5-03A2 transport-qualification requirement, not justification for a second approval system.

### 4.4 Vault preview evidence

Installed plugin `0.3.0` exposes these read-only preview tools:

- `orion_vault_preview_edit`
- `orion_vault_preview_move_draft`
- `orion_vault_preview_delete`

A successful preview result includes a bounded structured JSON result with fields such as:

- `success=true`
- `mode=preview`
- `plan_token`
- `plan`
- `diff`
- `mutation_performed=false`
- action-specific canonical target/source fields;
- relevant SHA-256 values;
- Windows file identity where applicable.

The plan token binds the immutable preview plan.

A persisted historical preview result proves that the preview existed. It does **not** prove that the in-memory plan remains unexpired/actionable after reconnect.

### 4.5 Vault approval evidence

The plugin's `_fresh_once_approval_evidence()` requires:

- the exact live plan;
- the exact approval message/diff;
- a fresh Hermes approval request;
- matching `post_approval_response`;
- `choice=once`;
- surface `cli` or `gateway`;
- matching attempt state.

On success it produces structured evidence including:

- `approved=true`
- `attempt_id`
- `plan_token`
- `choice=once`
- `surface`
- exact `approval_message`
- `approval_message_sha256`
- `authorization_reusable=false`.

This evidence is consumed by the executor and may later appear in the durable receipt.

The browser must never receive or reconstruct Hermes rule keys/pattern keys as authorization material.

### 4.6 Vault execution result

The guarded public apply tool is:

`orion_vault_apply_plan`

It accepts only:

`plan_token`

When production mutation is not explicitly enabled, it refuses before approval with structured failure evidence.

When the private qualified production executor succeeds, its structured result includes:

- `success=true`
- `mutation_performed=true`
- `recovery_required=false`
- `recovery_id=plan_token`
- `action`
- action-specific target/source fields.

The executor verifies action-specific postconditions before returning success and commits the recovery/receipt transaction first.

Therefore a successful structured plugin result is stronger action evidence than:

- `tool.completed`;
- `run.completed`;
- approval response;
- browser animation/state.

### 4.7 Vault stale-plan evidence

The plugin exposes explicit stale/state-change error codes during revalidation and immediately-before-effect guards.

The stale-plan presentation class must be driven by an explicit allowlist of known state-change codes, including the applicable production-path errors such as:

- `stale_original_hash`
- `stale_source_hash`
- `target_identity_changed`
- `target_file_id_changed`
- `source_identity_changed`
- `source_file_id_changed`
- `target_already_exists`
- `delete_target_identity_changed`
- `delete_target_file_id_changed`
- `delete_target_hash_changed`
- `delete_target_changed_before_delete`
- `source_changed_before_delete`
- `restore_recovery_record_changed`
- `restore_backup_changed`
- `restore_target_identity_changed`
- `restore_target_file_id_changed`
- `restore_current_state_changed`
- `restore_source_identity_changed`
- `restore_source_parent_changed`
- `restore_source_no_longer_absent`.

Do not classify an unknown error as stale merely because it occurs after preview.

### 4.8 Recovery / receipt evidence

The plugin has read-only restart-safe recovery/receipt inspection internally.

Receipt/recovery evidence may prove:

- recovery ID;
- action;
- receipt state;
- receipt finalization;
- final/current classification;
- approval attempt ID;
- approval surface;
- approval choice;
- approval message hash;
- recovery-required state;
- reconciliation-required state;
- backup hash.

Current public Orion/HUD surfaces do not expose a dedicated supported recovery-status projection.

Therefore:

- a successful live protected-action result containing `recovery_id` proves a committed recovery record was created at that completion point;
- after reconnect or later cleanup, historical action output alone must not be used to claim that recovery is **currently available**;
- current recovery availability must be `unavailable`/`unknown` unless an authoritative current recovery inspection is exposed and queried.

## 5. Evidence-to-presentation matrix

| Presentation state | Authoritative source | Threshold | Direct / derived | Durability | Reconnect | Missing-evidence behavior |
| --- | --- | --- | --- | --- | --- | --- |
| `preview_ready` | vault preview structured tool result | `success=true`, `mode=preview`, valid `plan_token`, plan + exact diff, `mutation_performed=false` | direct | turn-scoped; historical result persists | historical preview reconstructable, **current actionability is not** | `unavailable` for actionable readiness |
| `approval_requested` | Hermes `/v1/runs` `approval.request` after transport qualification | exact event for current approval-capable `run_id`; current session-chat transport does not establish this | direct when supported | transient live | exact pending payload not reliably reconstructable after stream loss | `unobserved` on current session-chat path; otherwise `unavailable` |
| `approval_accepted` | Hermes approval response on a qualified approval-capable run; later receipt where present | response object matches run, `resolved>0`, accepted choice; for protected vault authorization only fresh plugin `once` evidence qualifies | direct for decision, not execution | turn-scoped; receipt may make it durable | only where authoritative persisted evidence exists | `unobserved` on unsupported transport; otherwise `unavailable` |
| `approval_denied` | Hermes approval response on a qualified approval-capable run | response object matches run, `resolved>0`, `choice=deny` | direct | turn-scoped | exact decision not guaranteed durable | `unobserved` on unsupported transport; otherwise `unavailable`; eventual refusal may still be reconstructable |
| `executing` | **not currently exposed at the protected side-effect boundary** | generic `tool.started` is insufficient because it precedes the plugin's internal approval/revalidation/side-effect boundary | unsupported | transient | no | `unobserved` |
| `succeeded` | vault apply structured tool result from authoritative turn transcript / persisted tool message | protected action result `success=true`, `mutation_performed=true`, required postcondition result fields; no contradictory stronger action evidence | direct | completed record | yes from persisted session result while retained | `unknown` if action result absent |
| `failed` | action-specific structured failure result; Hermes run failure only for run-level failure | plugin result proves failure, or run failure is presented separately as run failure | direct/derived | completed record | usually yes for persisted tool result | do not convert generic run failure into action failure |
| `refused` | action-specific plugin result / approval denial | explicit fail-closed/policy/approval/replay refusal with `mutation_performed=false` | derived from allowlisted result code or direct denial | completed record where tool result persisted | yes for refusal outcome; exact human choice may be unavailable | `unknown` |
| `stale_plan` | action-specific plugin structured result | explicit stale/state-change error allowlist and `mutation_performed=false` unless result explicitly reports otherwise | derived from explicit code | completed record | yes | unknown errors remain `failed`/`unknown`, never guessed stale |
| `recovery_available` | current recovery inspection; live success result proves creation only at completion instant | authoritative evidence that the recovery record currently exists and is valid | direct | completed/recovery record | **not currently provable through public HUD surface after reconnect** | `unavailable` |
| `retry_available` | no current authoritative retry contract | none | unsupported | none | no | `unobserved` |
| `degraded` | Hermes/bridge health/readiness | observed bridge/Hermes health failure/degraded readiness | direct | transient | re-query | `unavailable` if health source unavailable |
| `unknown` | projection resolver | authoritative evidence conflicts or cannot establish a single claim | derived epistemic state | any | yes | display explicitly |
| `unobserved` | contract capability map | lifecycle stage is not exposed by accepted source | derived epistemic state | n/a | n/a | display/omit explicitly |
| `unavailable` | projection resolver | authoritative source should be consulted but is unavailable/expired/not reconstructable | derived epistemic state | any | yes | display explicitly |

## 6. Stable presentation vocabulary

P5-03A2 may normalize supported facts into the following presentation vocabulary once the underlying transport/source for that fact has been qualified:

- `preview_ready`
- `approval_requested`
- `approval_accepted`
- `approval_denied`
- `succeeded`
- `failed`
- `refused`
- `stale_plan`
- `degraded`
- `unknown`
- `unobserved`
- `unavailable`

Conditional vocabulary:

- `recovery_available` only when current authoritative recovery evidence exists.

Unsupported in the accepted evidence baseline:

- `executing` as a protected side-effect stage;
- `retry_available`.

A future implementation must not create these unsupported states from timing, animation, HTTP latency, or assumed lifecycle order.

Generic tool activity may still be presented separately as descriptive activity, e.g. `tool_active`, but it must not be relabeled as protected action execution.

## 7. Browser allowlist / redaction contract

### 7.1 General rule

Projection must be allowlist-first.

Do not forward an arbitrary upstream object and remove known bad fields in the browser.

For consequential action state, the bridge/server-side projection must construct a new bounded object from known safe fields.

### 7.2 Allowed common identifiers

Where required:

- presentation schema version;
- normalized presentation state;
- source/provenance kind;
- `session_id`;
- `run_id`;
- `message_id`;
- `tool_call_id`;
- normalized tool/action name;
- `plan_token` as an action correlation ID;
- bounded timestamps/sequence values.

### 7.3 Allowed preview/action fields

Where required by the UX:

- action type;
- canonical target required for approval;
- safe relative target/source display;
- exact unified diff required for approval;
- original/proposed/source/target SHA-256 values;
- Windows file identity where technically useful;
- changed flag;
- exact approval description;
- canonical approval choices;
- resolved approval decision;
- action-specific structured result fields:
  - `success`
  - `mutation_performed`
  - `recovery_required`
  - `recovery_id`
  - `error` as a bounded normalized code
  - safe postcondition hashes/identities;
- receipt/recovery classification fields only when supplied through an approved current inspection surface.

### 7.4 Excluded fields/content

Do not expose through the action projection:

- API keys;
- bearer tokens;
- provider credentials/secrets;
- `.env` values;
- Hermes approval rule keys/pattern keys;
- internal plugin rule keys;
- raw private provider responses;
- stack traces;
- arbitrary exception objects;
- internal routing metadata not required for user understanding;
- arbitrary backend objects;
- raw recovery backup bytes;
- recovery directory filesystem paths unless specifically required by an approved evidence UX;
- preview nonces;
- proposed/private cached bytes;
- full raw tool args;
- full new document content merely because it was a tool argument;
- unnecessary base64 image/audio/media data;
- unbounded logs.

### 7.5 Exact approval-content exception

The exact canonical approval content is not to be semantically summarized before the user decides.

For protected vault actions, the projection must preserve the exact approved:

- action/tool identity;
- canonical target/source where required;
- hashes/file identity where required;
- exact unified diff/operation;
- approval description.

Technical details may be visually collapsed, but the canonical content must remain complete and inspectable.

## 8. Durability classification

### Transient live activity

Examples:

- generic tool activity;
- reasoning/progress;
- current transport health;
- live approval request;
- live run status.

This may disappear.

### Turn-scoped activity/evidence

Examples:

- live preview readiness;
- live approval request/response;
- live correlation between stream event and run.

Do not treat it as durable merely because the browser saw it.

### Completed-record evidence

Examples:

- persisted Hermes session tool result;
- `run.completed.messages` authoritative per-turn transcript;
- durable plugin receipt;
- durable recovery record;
- explicit audit record.

### Reconstructable after reconnect

A presentation claim is reconnect-reconstructable only if the current authoritative source can be queried again or a persisted authoritative record proves it.

Browser cache is not an authoritative record.

## 9. Correlation strategy

### Live turn

Primary:

`session_id + run_id`

Additional live:

- `message_id`
- `seq`
- tool/action name.

### Completed tool/action

Primary:

- `session_id`
- `tool_call_id`
- `tool_name`
- persisted tool result.

Vault-specific:

- `plan_token`
- action
- canonical target/source
- hashes/file identity.

### Approval

Live, only on a qualified approval-capable Hermes transport:

- `run_id`
- exact approval response;
- approval request event.

The current session-chat `run_id` must not be assumed to be an approval-resolution key merely because it is also a Hermes run identifier.

Plugin qualification:

- `plan_token`
- plugin `attempt_id`
- approval message hash;
- surface/choice in receipt when persisted.

Do not expose Hermes `pattern_key`/rule key as browser correlation state.

### Recovery

For production protected actions:

`recovery_id == plan_token`

Origin recovery IDs may additionally connect restore actions to the prior transaction.

## 10. Contradiction / precedence rules

Use the following precedence.

1. **Validated current recovery/receipt evidence** controls current recovery/reconciliation claims.
2. **Action-specific structured plugin result** controls protected-action outcome.
3. **Persisted Hermes tool message / authoritative `run.completed.messages`** controls completed tool evidence.
4. **Hermes approval response / persisted approval receipt evidence** controls approval-decision claims.
5. **Hermes run status/events** control run lifecycle only.
6. **Generic tool lifecycle** controls descriptive tool activity only.
7. **Browser state** never creates consequential truth.

Required examples:

- Approval endpoint returns 200 with `resolved>0`: show decision accepted/denied according to the returned choice. Do not show action success.
- Hermes `run.completed` but plugin tool result says `success=false`: action is not successful.
- Generic `tool.completed` but plugin result says `success=false`: plugin result wins.
- Plugin result says action succeeded but the run later fails while composing/transporting a response: preserve action success and separately show run/turn failure/degraded state.
- Stale error code from the action result: show `stale_plan`, not provider/network failure.
- Recovery ID is present in historical action output but current recovery cannot be inspected: do not show current `recovery_available`.
- P5-02Y historical audit describes pruned recovery: historical evidence only, not current recovery availability.
- Browser remembers a prior state but Hermes/session evidence cannot reproduce it: use `unavailable`/`unknown`.

## 11. Reconnect / hydration mapping

### Browser reload during ordinary completed conversation

Use persisted Hermes session messages.

Do not rely on prior DOM/transcript buffers.

### Browser reload during an active session-chat stream

The current stream disconnect path interrupts/drains the live run. The browser must not assume the action continued unchanged.

A remembered `run_id` may be retained **only as a locator**. It is not state.

If used after reload:

1. query the authoritative run endpoint;
2. accept only the returned Hermes state;
3. if the run is absent/expired, fall back to persisted session evidence;
4. if neither source can establish consequential state, show `unavailable`.

### Reload while approval is pending

This scenario is valid only after P5-03A2 qualifies an approval-capable Hermes transport.

The exact approval payload is live transport evidence and is not preserved in pollable run status.

On the current session-chat stream, disconnect interrupts/drains the live run and that transport is not independently proven to support the `/v1/runs/{run_id}/approval` round trip.

Therefore P5-03A2 must not reconstruct a previous pending approval card from browser cache.

After reconnect:

- query the authoritative run/session source supported by the qualified transport;
- if a terminal persisted tool result exists, project that result;
- otherwise mark the approval/action state `unavailable` or `unobserved` according to the transport capability.

### Reload after approval response but before confirmed action result

Do not infer execution.

Use:

- current Hermes run status if available;
- then persisted session/tool evidence.

Without an action-specific result, protected-action outcome remains `unknown`/`unavailable`.

### Reload after completed protected action

Use the persisted tool result to reconstruct:

- action;
- target;
- success/failure/refusal/stale result;
- hashes/IDs present in the result.

Do not claim current recovery availability from the old tool result alone.

### HUD restart

Same rule as browser reload.

HUD process memory is not authority.

### Hermes restart

In-memory run status and live approval state are not durable.

Use persisted session/tool/receipt/recovery evidence where available.

Otherwise use `unavailable`.

## 12. Unsupported / unobservable states

### Protected `executing`

Current accepted evidence does not expose an authoritative event at the point where the protected filesystem side effect actually begins.

`tool.started` is earlier than:

- internal approval completion;
- post-approval stale revalidation;
- recovery preparation;
- the protected filesystem primitive.

Therefore:

`tool.started != protected action executing`

P5-03A2 must not synthesize an `executing` action stage.

If a future product requirement insists on this exact stage, it needs a separately reviewed narrow source signal at the correct executor boundary.

### `retry_available`

No accepted source currently defines whether retry is safe/appropriate for a given action result.

Do not infer retry safety from generic errors.

### Current recovery availability after arbitrary reconnect

The plugin has authoritative internal recovery inspectors, but the existing HUD surface does not expose a supported current recovery-inspection contract.

Until such a read-only projection exists, use `unavailable` rather than claiming recovery exists.

## 13. Architecture-gap assessment

### Disposition: **B — SUFFICIENT WITH NARROW TRANSPORT/PROJECTION QUALIFICATION**

There is **no requirement for a new event bus, broker, durable Orion event store, parallel approval system, or action ledger**.

The accepted authorities already contain the required core facts:

- Hermes live lifecycle events;
- Hermes approval resolution on the explicit `/v1/runs` surface;
- pollable run status;
- persisted SessionDB tool/result history;
- authoritative per-turn transcript on `run.completed`;
- vault preview result;
- vault structured protected-action result;
- durable receipt/recovery semantics.

The current Orion bridge is not yet sufficient as a browser-safe projection because:

1. it currently forwards session SSE bytes substantially as received and the browser derives presentation state directly; and
2. the accepted session-chat transport does not establish the same run-scoped interactive approval registration as Hermes `/v1/runs`.

P5-03A2 therefore needs a **narrow transport/projection qualification over existing Hermes/plugin facts**, not new authority.

Before implementing the protected-action presentation path, P5-03A2 must qualify exactly one authority-preserving option:

**Option A — reuse Hermes `/v1/runs` for the approval-capable action turn**

- prove the bridge can preserve the selected COMPANION session's conversation continuity and persisted SessionDB semantics;
- use Hermes' existing `run_id`, event stream, approval endpoint, and status surface;
- do not create a parallel session or action store.

**Option B — make the minimum evidence-backed compatibility correction to the existing session-chat path**

- only if Option A cannot preserve the accepted session semantics;
- wire the session-chat run into the same Hermes run-scoped approval notify/resolution semantics;
- treat any Hermes source patch as a separate, source-controlled, reversible dependency compatibility change with focused tests;
- do not create a second approval engine.

No option is selected by P5-03A1 alone.

After that bounded transport qualification, the bridge may add:

1. **normalized action-event projection**
   - parse only supported upstream lifecycle/action evidence server-side;
   - emit only allowlisted normalized presentation objects;
   - preserve conversation deltas as required;
   - never synthesize unsupported action states.

2. **read-only session action-evidence hydration**
   - derive completed action evidence from Hermes' persisted client-safe session messages;
   - correlate by session/tool-call/plan identifiers;
   - return a bounded action-evidence projection;
   - do not create or persist a second action record.

Existing:

`GET /api/orion/runs/{run_id}`

may remain an authoritative live run-status lookup only for run IDs whose lifecycle is actually registered on that Hermes run surface. A session-chat-generated `run_id` must be source-qualified before using run-approval assumptions.

A dedicated current-recovery inspection surface is **not required to begin P5-03A2** if `recovery_available` correctly falls back to `unavailable` after reconnect. Reconnect qualification later will determine whether the UX materially requires a narrow authoritative recovery-status surface.

## 14. Exact recommended P5-03A2 scope

P5-03A2 should:

1. first qualify one exact approval-capable Hermes transport while preserving the accepted persisted COMPANION session semantics;
2. prove with focused source/runtime tests that the selected `run_id` owns the approval request/resolution round trip used by the HUD;
3. define one small versioned browser-safe projection schema;
4. normalize only the evidence states accepted by this contract;
5. parse/allowlist consequential SSE evidence in the bridge before browser delivery;
6. consume the full Hermes approval-response body and distinguish:
   - decision resolved;
   - protected execution result;
7. derive protected action outcomes from structured Orion vault tool results, never from generic run/tool completion;
8. reconcile live presentation against `run.completed.messages`;
9. provide read-only completed-action hydration from persisted Hermes session messages;
10. allow browser-held IDs only as lookup/correlation hints;
11. use explicit `unknown|unobserved|unavailable` states;
12. preserve exact canonical approval content;
13. exclude secrets/private backend fields server-side;
14. keep all protected execution/recovery semantics in Hermes/plugin authority;
15. add focused truthfulness and secret-egress tests.

P5-03A2 should **not**:

- treat the isolated real-Hermes approval fixture as proof that production session-chat approval is wired;
- add a new durable event/action store;
- add an approval engine;
- add a session authority;
- change vault mutation semantics;
- change stale-plan protection;
- change recovery semantics;
- invent protected `executing`;
- invent `retry_available`;
- implement P5-03B visual redesign.

## 15. P5-03B presentation implications

P5-03B may use the accepted visual baseline only after P5-03A2 proves the projection.

The future contextual Action & Evidence rail may safely support:

- preview/proposal;
- awaiting approval;
- approval decision;
- final success/failure/refusal/stale result;
- evidence details;
- degraded/unknown/unavailable.

It must **not** visually force:

`Approved -> Executing -> Completed`

when the accepted evidence does not expose the middle stage.

Current Activity may describe real tool lifecycle independently, but generic tool activity must not masquerade as protected action execution.

The Orion Core and top system strip may react only to normalized accepted presentation states.

## 16. Risks and stop conditions

Stop P5-03A2 if implementation would require:

- browser-local state to become the sole source of consequential truth;
- semantic alteration of exact approval content;
- raw secrets/provider payloads/stack traces to reach the browser;
- generic `tool.completed` to be treated as action success;
- generic `run.completed` to be treated as protected action success;
- a new generalized event bus/broker/store;
- a second approval/recovery/session/runtime authority;
- synthetic protected execution state;
- historical recovery evidence to be presented as current availability.

## 17. Verification performed

P5-03A1 discovery verified:

- correct Orion branch/base;
- clean worktree;
- exact accepted Hermes checkout/tag/package;
- Hermes manual-off;
- accepted COMPANION config hash;
- mutation mode not persisted;
- mutation env not present;
- production recovery root configured;
- installed vault plugin version/hash equal to repo;
- live recovery inventory empty;
- P5-02Y audit retained at accepted hash;
- relevant Hermes lifecycle/approval/run/session source surfaces present;
- `/v1/runs` is the pinned source path that explicitly registers run-scoped gateway approval notification and resolution;
- current session-chat stream does not register its generated `run_id` in `_run_approval_sessions`;
- the existing real-Hermes HUD approval probe is an isolated no-write fixture, not a production session-transport proof;
- no vault read/mutation;
- no Hermes startup;
- no approval request;
- no runtime/config/dependency change.

Source review was performed against:

- installed Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`;
- Orion branch base `d67ad25dbff60f106aae27ae67f9f6546e19d035`;
- current `hud/orion_hud_bridge.py`;
- current `hud/static/app.js`;
- current `hermes_plugins/orion-vault-actions/__init__.py`;
- current `hermes_plugins/orion-vault-actions/plugin.yaml`.

## 18. Final disposition

**P5-03A1 contract candidate is ready for architecture review.**

Recommended review disposition target after this revision:

`READY FOR P5-03A2`

only if review confirms:

- unsupported states remain explicit;
- approval response is not success;
- action-specific plugin result outranks generic lifecycle;
- exact approval content is preserved;
- browser allowlisting occurs server-side;
- reconnect never trusts browser state alone;
- the current session-chat approval gap is carried explicitly into the first P5-03A2 qualification step;
- no generalized infrastructure or second authority is introduced.

No P5-03A2 implementation is authorized by this document alone.
