# P3-04 Provenance / Origin / Authority — Read-Only Source Inventory and Execution Contract

Status: **SOURCE + TEST INVENTORY COMPLETE / IMPLEMENTATION NOT YET STARTED**

Date: 2026-09-11

Branch: `feature/orion-phase3-provenance-authority`

Base `main`: `8db415a78cf23a99a93c8772cc54a5c357243663`

Controlling baseline: **ORION — Master PRD v2.8**

## Purpose

Define the smallest truthful Phase 3 implementation for:

- local/cloud response-origin indication;
- relevant source/memory provenance indication;
- descriptive authority state;
- evidence-backed UI behavior when origin/authority cannot be proven.

P3-04 must improve transparency without turning Orion into a second routing/runtime authority or making cosmetic guesses about where a response came from.

## Why this is the next slice

PRD v2.8 Phase 3 requires:

- Orion Core;
- adaptive workspace;
- Memory Lens / native IAI Brain handoff;
- local/cloud/source indicators;
- authority state;
- summonable-panel shell.

P3-01 through P3-03 established the first three items. P3-04 therefore addresses provenance/origin/authority before later visual composition and voice/action phases depend on those labels.

The owner-approved Orion final-interface visual contract also makes P3-04 the first build step toward the visual north star: provenance and authority language must become truthful before those indicators are made more prominent in the top edge and adaptive workspace.

PRD v2.8 also requires evidence calibration:

- diagnostics distinguish observed runtime evidence, installed-source confirmation, upstream documentation, and hypothesis;
- authority/status visualization is descriptive evidence, not an authorization mechanism;
- presence/provenance indicators must not fabricate tool execution, permissions, memory health, or cloud/local origin.

## Accepted entry state

Current accepted `main`:

`8db415a78cf23a99a93c8772cc54a5c357243663`

Already accepted:

- persistent Hermes session-based typed conversation;
- Hermes SSE streaming;
- STOP / cancellation;
- canonical approvals;
- activity display;
- bridge/Hermes/readiness/credential/lifecycle observations;
- capabilities, skills, and jobs observations;
- Orion Core deterministic presentation/gaze state;
- Conversation/System adaptive workspaces;
- Memory workspace with iai authority statement and link-only native Brain handoff.

Accepted repository baseline also records the normal COMPANION model path as:

- model `qwen3.5-hermes:9b`;
- Ollama provider `http://localhost:11434/v1`;
- context `65536`.

That is accepted **baseline configuration evidence**. It is not automatically a live per-turn origin observation.

## Evidence hierarchy

P3-04 uses the following precedence for every label:

1. explicit current owner decision;
2. installed-version-observed runtime behavior;
3. source-verified behavior from the exact accepted vendor version/tag;
4. accepted Orion repository contract/evidence;
5. deterministic inference that is explicitly documented and cannot overstate capability;
6. otherwise: `UNOBSERVED`, `UNKNOWN`, or omit the label.

A convenient assumption never outranks missing evidence.

## Existing Orion HUD observations

Current `hud/static/app.js` and `hud/orion_hud_bridge.py` already expose or mirror:

- Bridge state;
- Hermes liveness and detailed readiness;
- COMPANION API credential availability without exposing the credential;
- lifecycle authority = none for the HUD;
- current Hermes session id;
- Core state;
- capabilities;
- skills count;
- jobs count;
- current run/tool/approval activity.

The bridge's session-chat SSE path forwards upstream event bytes incrementally rather than reconstructing event payloads. Therefore supported Hermes event fields already present in the session stream can reach browser `app.js` without adding a new generic backend proxy.

Current `app.js` handles `assistant.completed` and `run.completed` but does not currently consume their `runtime` fields.

## Accepted Hermes v0.20.6 exact-tag findings

The accepted Hermes baseline is:

- release tag `v2026.8.27`;
- package `0.20.6`;
- accepted Orion source baseline commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5b`.

Primary exact-tag references inspected:

- `gateway/platforms/api_server.py`;
- `website/docs/user-guide/features/api-server.md`;
- `hermes_cli/inventory.py`;
- `hermes_cli/model_switch.py`;
- `tests/gateway/test_session_api.py`.

### Source question: CLOSED

The exact accepted Hermes tag **does expose sanitized effective provider/model metadata on supported session-stream completion events when Hermes has a non-global runtime selection to report**.

For `POST /api/sessions/{id}/chat/stream`:

- `run.started` includes a `runtime` object derived before execution from requested/route state;
- after the turn completes, Hermes reads runtime metadata from the agent result/usage;
- `assistant.completed` includes `runtime: effective_runtime`;
- `run.completed` includes the same `runtime: effective_runtime`.

The runtime sanitizer uses fields including:

- `provider`;
- `model`;
- `route_source`;
- requested runtime when applicable;
- model-lock state when applicable.

When actual runtime metadata is emitted, `_run_agent` reads the real constructed agent's `provider` and `model` and overwrites requested placeholders with the actual values. The exact-tag tests explicitly verify that actual provider/model win over requested metadata.

This means Orion does **not** need a new backend endpoint merely to receive supported provider/model metadata for turns where Hermes emits it.

### Important limitation: ordinary global-default turns

Hermes intentionally includes actual runtime metadata from `_run_agent` only when at least one of these is true:

- `requested_runtime` exists;
- a model route exists;
- a confirmed runtime lock exists;
- `route_source` is non-global.

For a plain session turn using only the global default, the exact-tag test suite verifies that `usage` contains no `runtime` field. The session-stream wrapper consequently sanitizes an empty runtime object with `route_source: global`, but does not gain actual global provider/model values from `_run_agent`.

Therefore the normal Orion path — which sends only `{input: ...}` and does not request a provider/model — cannot assume that every completed turn will carry effective provider/model identity.

This is the decisive P3-04 finding.

### Provider/model identity is not the same as local/cloud origin

Even when Hermes emits an actual provider/model pair, that pair is **runtime identity**, not necessarily proof of execution locality.

Reasons:

- provider endpoints may be configurable;
- custom providers can be local or remote;
- a built-in provider slug does not by itself prove where the endpoint actually resides;
- the supported completion runtime metadata does not expose the resolved inference endpoint/base URL.

P3-04 may display an observed `PROVIDER` or `MODEL` when Hermes supplies it. It must not mechanically translate an arbitrary provider/model name into `LOCAL` or `CLOUD` without a separately accepted evidence rule.

### `/api/model/options` is useful but not network-silent

The exact accepted tag exposes authenticated:

`GET /api/model/options`

It returns the current configured provider/model plus the richer picker inventory used by Hermes UI surfaces.

However the exact implementation is not a zero-network status probe:

- the model-options builder enables pricing enrichment;
- pricing enrichment may perform network calls, including pricing fetch / Nous tier checks;
- normal opens may probe the currently selected custom provider;
- `?refresh=1` performs broader custom-provider probing and cache refresh.

Therefore P3-04 should **not** poll `/api/model/options` merely to paint a provenance badge, and a future "read-only/no-external-call" smoke must not use this route while claiming no external network activity.

This corrects the earlier candidate probe plan.

### `/v1/models` is not sufficient provenance

The exact tag explicitly describes `/v1/models` as the cheap OpenAI-compatible discovery surface. It does not enumerate every authenticated provider/model combination and may advertise a stable profile/model alias rather than the effective provider for a particular turn.

Therefore `/v1/models` or `model: "hermes-agent"` is **not** sufficient evidence for `LOCAL` or `CLOUD` origin.

### Session metadata is intentionally narrow

`GET /api/sessions/{id}` exposes a safe session representation including a `model` field and boolean `has_model_config`, while intentionally hiding the full `model_config`.

This is useful for detecting that session-level model state may exist, but it does not expose enough provider/endpoint detail to prove local/cloud origin by itself.

## Provenance state model

### Evidence class

P3-04 should explicitly distinguish evidence class in internal presentation state:

- `OBSERVED_RUNTIME` — value came from the current Hermes event/runtime payload;
- `ACCEPTED_BASELINE` — value comes from current source-controlled Orion acceptance state;
- `SOURCE_VERIFIED` — exact accepted vendor source/docs prove the behavior or contract;
- `UNOBSERVED` — no supported current evidence proves the value.

The UI does not need to display these long names everywhere, but System/provenance drill-down should be able to explain them.

### Response origin

Initial state vocabulary:

- `LOCAL` — only when effective inference origin is positively proven local by an accepted evidence rule;
- `CLOUD-ASSISTED` — used for the explicit bounded cloud-escalation path when Phase 6 exists and that path is actually invoked;
- `UNOBSERVED` — default when the current supported surface does not prove effective inference origin;
- `UNAVAILABLE` — optional when the provenance source itself is unavailable/degraded and the UI needs to distinguish that from simply unobserved.

Do not introduce `MIXED` unless a concrete supported workflow requires it and the evidence can identify both contributors.

For the first P3-04 implementation, ordinary global-default typed turns should remain `ORIGIN · UNOBSERVED` unless new evidence is explicitly supplied. The accepted Ollama baseline may be shown separately as `DEFAULT/BASELINE · LOCAL OLLAMA`, not misrepresented as observed per-turn origin.

### Provider/model runtime identity

When a completed Hermes event includes non-empty actual runtime metadata, Orion may show:

- `PROVIDER · <observed-provider>`;
- `MODEL · <observed-model>`.

When absent:

- do not backfill a fake value from `hermes-agent`;
- omit the field or show `UNOBSERVED` in provenance detail;
- keep accepted baseline configuration visually distinct from observed runtime identity.

### Source indicators

A source label identifies where relevant context/evidence came from, not where the model executed.

Examples that may become valid when actually observed:

- `MEMORY · IAI`;
- `SOURCE · GITHUB`;
- `SOURCE · OBSIDIAN`;
- `SOURCE · HERMES SESSION`;
- `SOURCE · TOOL OUTPUT`.

Rules:

- source labels require an observable event/result or accepted static ownership fact;
- memory authority `iai` is an ownership fact and does not imply a particular response retrieved memory;
- tool inventory/capability availability does not prove a tool was used;
- a GitHub project context selected in the UI does not prove the current answer used GitHub evidence.

### Descriptive authority

Authority labels describe the current action boundary. They never grant permission.

Candidate normalized presentation states:

- `AUTHORITY · OBSERVE` — currently displayed interaction is read-only/observational;
- `AUTHORITY · ASSIST` — Orion/Hermes is actively reasoning/tooling within already granted non-consequential capability; exact use requires testable state rules;
- `AUTHORITY · ACT WITH APPROVAL` — a consequential action requires and is waiting on an explicit Hermes/operator approval boundary;
- `AUTHORITY · CONTROL` — reserve only for already-supported bounded controls such as STOP when the active run id and backend capability are known; final wording requires implementation review;
- `AUTHORITY · NONE` / `UNAVAILABLE` — no applicable supported action is available.

Do not create a generic `AUTHORIZED` badge. Authorization is action/target/state-specific.

## First implementation architecture

The source investigation supports a **frontend-owned P3-04 classification/presentation slice with no new Hermes API or upstream proxy route required**.

Recommended new pure module:

`hud/static/provenance-state.js`

Responsibilities:

- normalize completion-event runtime metadata;
- retain only bounded display-safe provider/model/route information;
- classify response origin only from explicit accepted evidence;
- classify descriptive authority from existing UI/runtime observations;
- track evidence class;
- produce stable labels/data attributes;
- contain no fetch, filesystem, shell, storage, lifecycle, model, or memory authority.

`app.js` integration should:

- feed `assistant.completed.runtime` and/or `run.completed.runtime` into the pure module;
- never treat `run.started.runtime` as final actual-runtime proof;
- reset per-turn observed-runtime state at the start of a new run;
- keep accepted baseline default separate from observed turn runtime;
- mirror authority state from existing run/approval/control observations;
- preserve current conversation/session reconciliation behavior.

Because Orion serves browser modules through an explicit static-file allowlist, adding `provenance-state.js` also requires a **minimal static-asset registration** in `hud/orion_hud_bridge.py`. That is a file-serving change only; it does not add an Orion API route, Hermes proxy route, credential path, lifecycle authority, or network behavior.

Likely UI additions:

- compact top-edge provenance/authority strip;
- System workspace provenance card showing response origin, observed provider/model when available, and evidence class;
- optional restrained per-response provenance footer later, after the base state model is visually accepted.

No model/provider picker is part of P3-04.

## Current HUD test inventory: CLOSED

All seven current HUD test files on accepted `main` were reviewed before source implementation planning:

- `test_bridge.py`;
- `test_frontend_hardening.py`;
- `test_phase3_core_state.py`;
- `test_phase3_memory_lens.py`;
- `test_phase3_workspace.py`;
- `test_post_connection_close.py`;
- `test_stream_delivery.py`.

Findings:

1. `test_phase3_workspace.py` asserts exactly three workspace targets. P3-04 does not add a workspace, so this assertion remains correct and should not be changed.
2. Core and Memory tests assert their existing module allowlists and authority boundaries. P3-04 can preserve them unchanged.
3. `test_frontend_hardening.py` protects persisted-transcript behavior, degraded state, terminal states, and startup history loading. P3-04 integration must preserve all of those exact behaviors.
4. `test_stream_delivery.py` deliberately supplies SSE completion events with no runtime metadata. This is a useful regression anchor: P3-04 must tolerate missing runtime metadata and remain `UNOBSERVED` without breaking streaming.
5. `test_bridge.py` does not require a fixed total number of static files. Adding one exact `provenance-state.js` static allowlist entry does not require weakening its security tests.
6. `test_post_connection_close.py` is unrelated to provenance and should remain unchanged.
7. No existing test contains a stale P3-04 placeholder or an assertion that provenance/authority must be absent.

Recommended test strategy:

- add new `hud/tests/test_phase3_provenance.py` for the P3-04 contract;
- do not edit existing tests unless implementation reveals a genuinely stale assertion;
- new test should explicitly verify the bridge serves/allowlists only the new static module, not a new API/proxy route;
- new test should enforce pure-module authority scanning, default `UNOBSERVED`, completion-runtime normalization, final-vs-start event semantics, and preservation of accepted baseline/observed-runtime distinction.

This pre-review removes the stale-test discovery risk that affected earlier Phase 3 work.

## Expected first implementation file scope

Subject to exact preflight when the Windows machine is available, the expected implementation scope is six files:

1. `hud/orion_hud_bridge.py` — add static asset allowlist entry only;
2. `hud/static/provenance-state.js` — new pure presentation classifier;
3. `hud/static/app.js` — event/state integration only;
4. `hud/static/index.html` — provenance/authority presentation nodes;
5. `hud/static/styles.css` — restrained presentation styles;
6. `hud/tests/test_phase3_provenance.py` — new focused contract tests.

Existing test files are expected to remain unchanged. If implementation requires any seventh path, stop and review the reason before broadening scope.

## No Windows discovery probe required for architecture

The central source question is closed from the exact accepted Hermes tag and tests. A broad Windows discovery probe is no longer needed before implementation.

When the PC is available, Windows is needed for:

1. running the focused and full HUD synthetic tests on the actual feature head;
2. controlled live visual smoke;
3. optionally confirming that the accepted baseline configuration still matches the running COMPANION profile, if a later UI wants to show it as current rather than accepted-baseline information.

Do **not** use `/api/model/options` in a smoke that is supposed to prove "no external network calls".

Do not use `iai-mcp-core --help`; it is unrelated to P3-04 and can instantiate the memory store.

## What P3-04 does not do

P3-04 does not:

- switch models/providers;
- add provider selection UI;
- add cloud escalation;
- expose credentials/config values;
- claim a response is local because the HUD and Hermes communicate over loopback;
- claim a response is local because Ollama is running;
- scrape private Hermes Python internals at runtime;
- reimplement provider routing;
- poll model inventory/pricing endpoints just for decoration;
- add voice/privacy controls;
- add vault/tasks/reminders;
- add a second approval system;
- add a new framework/build pipeline.

## Synthetic acceptance plan

Implementation tests should prove at minimum:

- unknown evidence renders `UNOBSERVED` rather than `LOCAL`;
- loopback-only bridge/Hermes input alone cannot classify model origin as local;
- Ollama availability alone cannot classify model origin as local;
- accepted baseline model/provider is not mislabeled as observed current-turn runtime;
- `assistant.completed.runtime` actual provider/model is normalized when present;
- missing/empty runtime metadata remains unobserved;
- requested runtime cannot outrank actual runtime metadata;
- `run.started.runtime` is not treated as final actual-runtime evidence;
- memory authority iai alone does not claim memory was used in a turn;
- source indicators appear only when their evidence flag/event is present;
- authority classification is deterministic from existing supported UI state;
- authority text cannot grant a backend capability;
- provenance module has no network/storage/process authority;
- Conversation remains default;
- System and Memory workspaces remain intact;
- Core state/gaze/reduced-motion behavior remains intact;
- existing STOP/approval behavior remains intact;
- full HUD suite remains green.

## Live acceptance plan

Once implementation is synthetic-green and the PC is available:

- controlled live smoke against the exact tested feature head;
- no need to generate a model call solely to make the origin badge look interesting;
- confirm default state is truthful with no observed per-turn runtime evidence;
- confirm accepted baseline configuration is visually distinguished from observed runtime evidence;
- confirm existing persisted conversation, System, and Memory surfaces remain intact;
- confirm degraded Hermes state remains truthful;
- confirm approval/STOP authority presentation does not imply broader control;
- return to accepted manual-off clean state;
- no merge until the visual/evidence behavior is accepted.

A later separately authorized turn may exercise real completion-event runtime metadata if needed, but that is not required to accept the default unobserved state.

## Stop conditions

Stop P3-04 and report before implementation if proving origin would require:

- guessing from provider/model names without a documented mapping;
- reading secrets into browser assets;
- arbitrary Hermes proxying;
- patching Hermes merely to obtain a cosmetic indicator;
- importing Hermes private runtime internals into Orion;
- creating a second model router;
- adding model/provider mutation controls;
- widening lifecycle/process authority;
- performing cloud/model calls only for discovery without explicit authorization.

If the accepted Hermes version does not provide sufficient evidence to classify execution locality for a turn, the correct P3-04 behavior is `ORIGIN · UNOBSERVED` while still showing any separately observed provider/model identity truthfully.

## Next bounded action

When the Windows machine is available for immediate execution:

1. preflight exact main/feature refs and clean-off state;
2. implement the expected six-file P3-04 scope;
3. run focused P3-04 tests;
4. run the full HUD suite;
5. commit/push only after both suites pass and file scope is exact;
6. perform bounded live visual smoke before merge.

Until the PC is available, avoid committing unexecuted HUD code merely to advance the branch. Source and test discovery are now complete enough to begin implementation directly when testing is available.

Core Intent Preservation: **PRESERVED**.
