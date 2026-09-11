# P3-04 Provenance / Origin / Authority — Read-Only Source Inventory and Execution Contract

Status: **SOURCE INVENTORY IN PROGRESS / NO HUD IMPLEMENTATION YET**

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

Current Orion source does **not** expose a first-class per-turn field that proves:

- effective model provider;
- local versus remote inference execution;
- whether a response used a particular provider after Hermes routing precedence resolved;
- a generic "confidence" score for an answer.

Therefore P3-04 must not derive `ORIGIN · LOCAL` from loopback topology, Hermes liveness, or an Ollama process alone.

## Accepted Hermes v0.20.6 exact-tag findings

The accepted Hermes baseline is:

- release tag `v2026.8.27`;
- package `0.20.6`;
- accepted Orion source baseline commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5b`.

Primary exact-tag references:

- `gateway/platforms/api_server.py`
- `website/docs/user-guide/features/api-server.md`

### Provider/model inventory exists

The exact accepted tag documents authenticated:

`GET /api/model/options`

This returns the richer Hermes provider/model inventory used by the dashboard/TUI, including provider rows, curated model lists, pricing, and capability hints.

Important safety behavior:

- normal `GET /api/model/options` is intentionally conservative;
- for custom providers it probes only the currently selected endpoint;
- `?refresh=1` performs broader probing and cache busting.

P3-04 discovery should **not** use `refresh=1` unless a later, separately justified test specifically needs it.

### Request model/provider selection is deterministic

The exact tag documents request fields:

- `model`;
- `provider`;
- `model_options`.

Those fields are accepted by the Hermes-native session chat/stream path used by Orion as well as runs and OpenAI-compatible endpoints.

Selection precedence is documented as:

1. existing session `/model` override;
2. configured `model_routes` alias;
3. direct request model/provider when no route alias matches;
4. global gateway config/environment defaults.

This proves that response origin cannot safely be inferred from a single generic model alias without knowing the effective resolution path.

### `/v1/models` is not sufficient provenance

The exact tag explicitly describes `/v1/models` as the cheap OpenAI-compatible discovery surface. It does not enumerate every authenticated provider/model combination and may advertise a stable profile/model alias rather than the effective provider for a particular turn.

Therefore `/v1/models` or `model: "hermes-agent"` is **not** sufficient evidence for `LOCAL` or `CLOUD` origin.

### Run status is useful but not yet proven sufficient

The exact tag documents `GET /v1/runs/{run_id}` for reconciliation and shows a stable `model` field in the example response.

The published contract does not, by itself, prove that run status includes the effective provider for every completed session-chat turn.

This remains the central P3-04 source question.

## Central source question

Before implementing per-turn origin labels, determine from the exact accepted Hermes tag:

> After Hermes resolves session/model/provider precedence for `POST /api/sessions/{id}/chat/stream`, is the **effective provider and effective model** surfaced through any stable, supported response/event/session/run field available to an external UI?

Preferred proof order:

1. exact-tag API-server/session-chat source;
2. exact-tag event/run data structures;
3. exact-tag public docs/tests;
4. only if source remains ambiguous, one bounded installed-runtime read-only probe.

Do not start with broad Windows filesystem/process discovery.

## Remaining source-inspection targets

Read-only exact-tag inspection should focus only on:

- session-chat request normalization;
- model/provider resolution helper call;
- run/event object construction;
- `run.started`, `assistant.completed`, `run.completed`, or equivalent session-stream payloads;
- persisted session metadata returned by `GET /api/sessions/{id}`;
- `GET /v1/runs/{run_id}` serialization;
- existing tests that assert model/provider fields.

The goal is to answer one question: **what supported field, if any, proves effective origin for the turn?**

## Runtime probe only if source cannot close the question

If exact-tag source still leaves ambiguity, the later Windows probe must be narrow and read-only.

Candidate probe, subject to explicit execution authorization when the PC is available:

1. accepted manual-off clean state preflight;
2. start accepted Orion/Hermes runtime using existing operator controls;
3. authenticated server-side `GET /api/model/options` using the COMPANION credential without printing/logging it;
4. no `refresh=1`;
5. inspect one existing persisted session's read-only metadata and/or one already-completed run if available;
6. no POST, no new session, no message, no model invocation, no iai call;
7. stop accepted runtime and return to clean-off.

Do not use `iai-mcp-core --help`; it is not part of this ticket and can open the memory store.

## Provenance state model

### Response origin

Initial state vocabulary:

- `LOCAL` — only when effective inference origin is positively proven local by an accepted evidence rule;
- `CLOUD-ASSISTED` — used for the explicit bounded cloud-escalation path when Phase 6 exists and that path is actually invoked;
- `UNOBSERVED` — default when the current supported surface does not prove effective inference origin;
- `UNAVAILABLE` — optional when the provenance source itself is unavailable/degraded and the UI needs to distinguish that from simply unobserved.

Do not introduce `MIXED` unless a concrete supported workflow requires it and the evidence can identify both contributors.

### Source indicators

A source label identifies where relevant context/evidence came from, not where the model executed.

Examples that may become valid when actually observed:

- `MEMORY · IAI`
- `SOURCE · GITHUB`
- `SOURCE · OBSIDIAN`
- `SOURCE · HERMES SESSION`
- `SOURCE · TOOL OUTPUT`

Rules:

- source labels require an observable event/result or accepted static ownership fact;
- memory authority `iai` is an ownership fact and does not imply a particular response retrieved memory;
- tool inventory/capability availability does not prove a tool was used;
- a GitHub project context selected in the UI does not prove the current answer used GitHub evidence.

### Descriptive authority

Authority labels describe the current action boundary. They never grant permission.

Candidate normalized presentation states:

- `AUTHORITY · OBSERVE` — currently displayed interaction is read-only/observational;
- `AUTHORITY · ACT WITH APPROVAL` — the consequential action requires and is waiting on an explicit Hermes/operator approval boundary;
- `AUTHORITY · CONTROL` — reserve only for already-supported bounded controls such as STOP when the active run id and backend capability are known; final wording requires implementation review;
- `AUTHORITY · NONE` / `UNAVAILABLE` — no applicable supported action is available.

Do not create a generic `AUTHORIZED` badge. Authorization is action/target/state-specific.

## Deterministic classification rules

P3-04 implementation should use a pure presentation module rather than scatter label decisions through `app.js`.

Recommended module:

`hud/static/provenance-state.js`

Responsibilities:

- normalize evidence inputs;
- classify response origin only from explicit evidence;
- classify descriptive authority from existing UI/runtime observations;
- produce stable display labels/data attributes;
- contain no fetch, filesystem, shell, storage, lifecycle, model, or memory authority.

`app.js` should only feed observed state into the pure classifier and render the result.

If a read-only Hermes endpoint must later be exposed through Orion, the bridge change must be a fixed explicit allowlist route with existing server-side credential handling; no arbitrary proxy is permitted.

## UI placement

Target presentation should align with the approved Orion visual contract:

- compact top-edge provenance/authority strip;
- optional per-response provenance footer when turn-specific evidence exists;
- System workspace can show the evidence source and current classification details;
- detailed explanation available without dominating the conversation.

Critical states require text/icon semantics; color alone is insufficient.

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
- add voice/privacy controls;
- add vault/tasks/reminders;
- add a second approval system;
- add a new framework/build pipeline.

## Synthetic acceptance plan

Implementation tests should prove at minimum:

- unknown evidence renders `UNOBSERVED` rather than `LOCAL`;
- loopback-only bridge/Hermes input alone cannot classify model origin as local;
- Ollama availability alone cannot classify model origin as local;
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
- do not generate a model call merely to make the origin badge look interesting unless separately authorized;
- confirm default state is truthful when no per-turn origin evidence exists;
- confirm existing persisted conversation, System, and Memory surfaces remain intact;
- confirm degraded Hermes state remains truthful;
- return to accepted manual-off clean state;
- no merge until the visual/evidence behavior is accepted.

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

If the accepted Hermes version does not expose effective provider/model provenance to an external UI, the correct P3-04 behavior is to display `ORIGIN · UNOBSERVED` and document the limitation rather than inventing certainty.

## Next bounded action

Continue exact-tag source inspection of the accepted Hermes session-chat/run/event serialization to determine whether effective provider/model provenance is already exposed.

No Windows probe and no HUD implementation is needed until that source question is exhausted.

Core Intent Preservation: **PRESERVED**.
