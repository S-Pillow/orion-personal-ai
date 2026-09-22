# Orion Phase 5 Completion + UI Convergence Plan

Status: **SOURCE-ONLY EXECUTION PLAN / UI CONVERGENCE REQUIRED BEFORE PHASE 5 CLOSURE**  
Date: 2026-09-22  
Controlling product baseline: **ORION Master PRD v2.8**  
Visual north star: `docs/hud/orion-final-interface-visual-contract.md`  
Related UI closure issue: **#24 — P3-05B summonable HUD presentation path**  
Related draft UI PR: **#26 — P3-05B bounded summonable presentation shell**  
Current Phase 5 qualification baseline: **P5-02I COMPLETE**  
Installed COMPANION Orion plugin source pin: `ce676a263f3dd2c18a7d7700b17a6023c6845904`

## Purpose

This plan prevents the remaining Phase 5 work from closing as a backend-only
vault/action milestone while the owner-approved Orion interface remains only a
functional skeleton.

The approved visual contract already defines the product direction:

- calm private observatory / command deck;
- persistent Orion Core as the visual identity;
- Conversation as home;
- contextual left rail;
- consequential/action right rail;
- one persistent bottom command surface;
- evidence-backed provenance and authority;
- Memory Lens rather than a second memory application;
- contextual summoned workspaces instead of multiplying permanent tabs;
- richer approval/action composition only when the underlying capabilities are
  real.

Phase 5 is the point where those product ideas gain real backend semantics:
previewed document actions, approval, recovery, restore, draft creation,
deletion, and explicit display/summon tooling.

Therefore Phase 5 closure must include **both**:

1. safe production action capability; and
2. UI convergence sufficient to expose that capability through the approved
   Orion interaction model.

A backend PASS without the UI convergence gate is **not Phase 5 complete**.

## Current position

P5-02I is accepted and proves the installed runtime on disposable Windows roots:

- exact edit/move previews;
- real human DENY and fresh ALLOW ONCE;
- approval evidence isolation/consumption;
- stale/replay/mismatched-evidence refusal;
- Windows source identity protection;
- committed recovery + receipt records;
- restart-safe disk classification;
- historical edit and move-source restore as independent approvals;
- controlled `prepared_no_effect` and `applied_unfinalized` failure states;
- no automatic retry/repair;
- registered public apply still fail-closed;
- no real vault/inbox mutation.

Production mutation remains disabled and unauthorized.

## Phase 5 completion sequence

### P5-03 — production recovery-root design and ACL acceptance

Goal: establish the real production recovery boundary before any production
handler can mutate.

Source/read-only work may prepare:

- exact recovery-root candidate location;
- containment and overlap rules;
- required Windows ACL model;
- ownership/identity checks;
- bounded inventory behavior;
- backup/retention semantics;
- rollback/runbook.

Live work requires separate explicit owner authorization before:

- creating the production recovery directory;
- changing ACLs;
- persisting `ORION_P5_PRODUCTION_RECOVERY_ROOT`;
- restarting/reloading runtime to consume it.

Acceptance:

- recovery root is outside vault and inbox;
- not a reparse point;
- current user/runtime can create recovery artifacts;
- unrelated principals do not gain unnecessary write authority;
- production preflight passes;
- COMPANION config/runtime state remains otherwise unchanged;
- rollback procedure is proven.

### P5-04 — production apply activation design

Goal: promote the already-qualified production-shaped mutation executor into
the public `orion_vault_apply_plan` path without weakening approval rules.

Implementation order:

1. source-only handler activation behind explicit production mode;
2. tests proving disabled/preview-only modes remain fail-closed;
3. tests proving private executor is reached only when all production
   preconditions are valid;
4. exact approval evidence is consumed before stale revalidation;
5. result schema exposes mutation/recovery state truthfully;
6. no automatic retry after ambiguous/applied-unfinalized results.

Do **not** enable `mutation_enabled` merely because the handler is registered.

Live installation/update and runtime activation require separate authorization.

### P5-05 — production no-write / first-live preflight

Before any real vault mutation:

- installed production handler discovered;
- production mode still disabled or preview-only;
- production recovery root accepted;
- doctor/health PASS;
- exact preview against a named real file/draft;
- real approval presentation visually verified;
- DENY produces no write;
- stale/replay remains no-write;
- return to manual-off.

This confirms the production-shaped handler, path identities, recovery root, and
approval UX before crossing the first real-write boundary.

### P5-06 — first bounded real-vault mutation

Requires a new exact authorization unit naming:

- one target file or one draft;
- the exact allowed action;
- maximum mutation count;
- recovery expectation.

Recommended first acceptance is **one small edit**, not a bundled edit + move +
delete smoke.

Acceptance:

- exact pre-approval diff;
- human ALLOW ONCE;
- exact target bytes/hash;
- Obsidian-visible result;
- committed recovery + receipt;
- explicit restore/rollback verification;
- clean return to manual-off.

Only after the first edit is accepted should a separate bounded move acceptance
run occur.

### P5-07 — production restore and move acceptance

Qualify production behavior already proven on disposable roots:

- edit restore with a new approval and independent recovery record;
- move draft with held Windows source identity;
- move-source restore without altering destination;
- stale/race/replay refusal;
- recovery-required classification where appropriate.

Do not include delete yet.

### P5-08 — inbox draft creation

Implement the PRD's low-risk automatic creation path separately from edit/move
authority.

Contract:

- create only beneath the dedicated Orion inbox;
- exclusive create / never overwrite;
- deterministic filename collision behavior;
- structured Markdown metadata where useful;
- result reports canonical path;
- no mutation outside the inbox;
- no approval required only because the PRD specifically allows dedicated
  inbox creation.

UI implication: this is the first real **Create** capability, but it should not
automatically become a permanent CREATE tab. Prefer Conversation + a summoned
draft/document surface unless repeated workflows justify a stable workspace.

### P5-09 — delete + recovery semantics

Delete remains a separate approval class.

Preferred first production contract:

- exact target;
- clear preview of what will disappear;
- fresh ALLOW ONCE;
- recoverable quarantine/backup semantics where compatible with the user-facing
  word "delete";
- explicit receipt/recovery state;
- restore requires a new approval;
- denied/stale/replay -> no deletion.

Do not inherit edit/move approval authority implicitly.

### P5-10 — P3-05B summon shell completion

This is the start of the concentrated UI implementation pass.

Use draft PR #26 as the source candidate rather than restarting from scratch.

Finish and accept:

- bounded center-workspace summon surface;
- title;
- content kind;
- source/provenance;
- literal safe text rendering;
- safe HTTP/HTTPS links;
- visible dismiss;
- keyboard focus/accessibility;
- reduced-motion behavior;
- Conversation/System/Memory state preserved underneath;
- approval focus outranks summon focus;
- Orion Core gaze/focus cue follows summon state.

Keep the accepted stable workspace set small. A summon is **not** a fourth
permanent workspace.

### P5-11 — explicit Hermes display tool / P3-05C integration

Add a capability-bounded display tool separate from vault mutation authority.

Preferred implementation:

- reuse existing Hermes session/tool event flow;
- typed bounded payload: `text`, `evidence`, `link` first;
- no arbitrary HTML;
- no arbitrary iframe;
- no broad HTTP proxy;
- no browser Hermes credential;
- one local intended HUD target for V1;
- future rich media/device targeting remains a later gate.

The accepted Hermes stream already exposes display-safe tool arguments on
`tool.started`, so the MVP should prefer carrying the summon payload through
that existing event path rather than creating a second callback server/token.

Acceptance:

- a real Hermes tool call visibly summons content in the actual Orion HUD;
- dismiss restores prior workspace;
- malformed/oversized/unsafe payload refuses safely;
- approval still outranks summon;
- no new filesystem/lifecycle authority is introduced.

Closing this gate also closes the lingering Phase 3 summon/display acceptance
criterion.

## Mandatory UI convergence gate before Phase 5 closure

After P5-10/P5-11 and once the underlying action semantics are real, perform a
dedicated visual/product convergence pass against:

`docs/hud/orion-final-interface-visual-contract.md`

and the owner-approved concept reference.

This is **not cosmetic cleanup**. It is the Phase 5 user-facing integration of
the real action model.

### Required composition

#### Orion Core

- significantly more visually dominant than the current prototype;
- preserve deterministic state/gaze semantics already accepted;
- blend celestial instrument / aperture / abstract masked presence;
- restrained blink, micro-saccade, breathing, gaze;
- no meaningless spinning/particle overload;
- reduced-motion remains truthful.

#### Top edge

Keep low-noise:

- Orion identity;
- active workspace/context;
- evidence-backed provenance/authority;
- privacy/voice state only when actually implemented;
- clock.

Never show `ORIGIN · LOCAL` merely because loopback/Ollama exists.

#### Left rail — context

Converge toward:

- current Hermes session;
- selected/resolved project/context only when evidenced;
- memory authority / IAI Brain handoff;
- compact navigation/context;
- inactive information visually recedes.

#### Right rail — consequence

Converge around real action semantics:

- current activity;
- pending approval;
- recovery/reconciliation state when relevant;
- current evidence/provenance;
- temporary state that matters now.

The approval card should implement the visual contract structure:

- `WHAT ORION WANTS TO DO`
- `WHY`
- `TARGET`
- `EFFECT`
- `AUTHORITY REQUESTED`

with DENY as a first-class outcome.

The backend now has the data needed to present stale, committed,
prepared-no-effect, applied-unfinalized, recovery-required, and restored states
truthfully. Use those states instead of a generic approval/error block.

#### Center workspace

Conversation remains home.

Use summoned contextual content for:

- document preview;
- evidence;
- comparison;
- research result;
- created draft;
- recovery/restore result;
- other bounded outputs.

Do not create permanent RESEARCH/CREATE tabs simply to match concept art.
Permanent modes require real repeated workflows and evidence.

#### Memory Lens

Evolve from the current static explanatory workspace toward contextual,
evidence-backed memory presentation:

- iai remains authoritative;
- show actual source/provenance when known;
- show UNOBSERVED when not known;
- surface recent/relevant references only when actually evidenced;
- detailed memory administration remains native iai Brain.

#### Bottom command surface

Keep one persistent command surface:

- typed input;
- SEND;
- STOP while a run is active;
- voice later through the same conversation;
- add/summon affordance only when implemented.

## Best implementation approach for the UI

### 1. Keep the existing modular vanilla HUD for Phase 5

Do not introduce React/Vue/Svelte or a new build pipeline solely for visual
convergence.

Reasons:

- current HUD is already modular: `app.js`, `core-state.js`,
  `workspace-state.js`, `provenance-state.js`, and the P3-05B
  `summon-state.js` candidate;
- the bridge uses an explicit static allowlist;
- synthetic tests already exercise architecture/state contracts;
- adding a framework would enlarge dependency, CSP, build, and runtime surface
  without solving a demonstrated product problem.

Reconsider a framework only after Phase 5 if actual maintainability evidence
justifies it.

### 2. Separate state semantics from visual rendering

Preserve deterministic modules for:

- Core operational state;
- workspace/focus state;
- provenance/authority;
- summon state;
- approval/action presentation state.

CSS/DOM should render those states; it must not infer authority.

For Phase 5 add a small pure presentation reducer such as
`action-state.js` rather than embedding growing approval/recovery conditionals
directly into `app.js`.

### 3. Upgrade the Core with SVG/CSS before adding a 3D runtime

Best Phase 5 implementation path:

- semantic HTML + layered SVG/CSS;
- local gradients/masks/strokes;
- CSS custom properties driven by deterministic state;
- optional lightweight local raster background/texture only if needed;
- no Three.js/VRM dependency for Phase 5.

This can reach the concept's aperture/masked/celestial look while preserving the
existing deterministic gaze and reduced-motion contract.

A full 3D/VRM avatar remains a later visual spike if the owner still wants it.

### 4. Treat the concept image as composition reference, not literal capability truth

Preserve:

- dramatic persistent Core;
- quiet contextual left rail;
- action-heavy right rail;
- center conversation/workspace;
- bottom command surface;
- observatory/command-deck atmosphere.

Adapt:

- `RESEARCH` and `CREATE` become contextual summons first;
- `ORIGIN · LOCAL` appears only when evidenced;
- project/context appears only when selected/resolved;
- privacy/mic states appear only when the actual Phase 4 path supports them.

### 5. Use rendered side-by-side visual evidence for acceptance

For the final convergence pass, require:

- accepted concept reference;
- current HUD screenshot;
- candidate HUD screenshot;
- same resolution where practical;
- side-by-side review of hierarchy, rail density, Core prominence, transcript
  measure, approval emphasis, spacing, and visual restraint.

Do not accept UI work from source diff alone.

### 6. Keep responsive/reduced-motion and truthful-state tests as hard gates

Every visual slice must preserve:

- typed conversation/session path;
- STOP;
- approvals;
- activity;
- workspace state;
- Memory Lens handoff;
- provenance truthfulness;
- reduced-motion;
- responsive behavior;
- no new credential/filesystem/lifecycle authority.

## Recommended source-ticket split

To move quickly without losing control:

- **P5-03** production recovery root + ACL readiness;
- **P5-04** production apply activation source candidate;
- **P5-05** installed production no-write/preflight;
- **P5-06** first bounded real edit;
- **P5-07** move + restore production acceptance;
- **P5-08** inbox draft creation;
- **P5-09** delete/recovery;
- **P5-10** P3-05B summon shell acceptance;
- **P5-11** P3-05C bounded display-tool integration;
- **P5-12** Phase 5 UI/action convergence against the visual north star;
- **P5-13** final Phase 5 regression, operator visual acceptance, docs/status
  closure.

Ticket numbering may be adjusted if existing issue history requires it; the
sequence and gates are more important than the exact labels.

## Fast-path execution strategy

Source-only work can be prepared ahead of live authorization boundaries.

For each production gate:

1. inspect current source and runtime contract;
2. implement source candidate;
3. run focused + regression tests;
4. prepare rollback/runbook;
5. stop at live authorization boundary;
6. execute the smallest live acceptance unit;
7. record evidence immediately;
8. proceed only if classification is unambiguous.

For UI work:

1. finish P3-05B source candidate from PR #26;
2. test it without live transport;
3. implement bounded display transport separately;
4. live-smoke real summon;
5. add Phase 5 action-state presentation;
6. do the visual convergence pass using side-by-side evidence;
7. run final full HUD regression and controlled live acceptance.

## Tomorrow's recommended starting sequence

1. **Read-only/source-only P5-03 discovery**
   - inspect accepted production recovery-root assumptions;
   - choose candidate location and ACL contract;
   - prepare the exact creation/ACL runbook;
   - stop before any live directory/ACL/config mutation.

2. **In parallel, finish P3-05B source review**
   - rebase/check draft PR #26 against current main;
   - run the full Windows HUD tests + Node rendering tests;
   - fix only source-level defects;
   - prepare browser visual-smoke checklist;
   - do not merge/activate without authorization.

3. **Prepare P5-04 production-handler activation source candidate**
   - public handler behind production mode;
   - disabled mode remains default/fail-closed;
   - regression tests;
   - no live activation yet.

4. **Prepare UI action-state contract**
   - derive fields from real Phase 5 result/approval/recovery data;
   - define the structured approval card and recovery/reconciliation
     presentations;
   - source-only, no fake runtime data.

This front-loads the safe engineering work so live owner time is spent only on
the few actions that actually require authorization or visual judgment.

## Phase 5 closure rule

Do not declare Phase 5 complete until all of the following are true:

- production recovery boundary accepted;
- production apply path safely activated;
- at least one bounded real edit accepted;
- move + restore accepted;
- inbox draft creation accepted;
- delete/recovery accepted;
- real Hermes display action visibly drives the HUD summon shell;
- approval/action/recovery UI reflects real backend state;
- HUD has undergone a deliberate convergence pass against the approved Orion
  visual contract/concept;
- side-by-side visual acceptance is recorded;
- full Phase 5 + HUD regression is green;
- manual-off lifecycle remains intact;
- no unresolved recovery-required fixture/state remains;
- docs/status reflect the true final state.

## Authorization boundary

This document is planning only.

It does not authorize:

- production recovery-root creation;
- ACL mutation;
- `ORION_P5_MUTATION_MODE=mutation_enabled`;
- public production handler activation in the live COMPANION runtime;
- real vault/inbox mutation;
- delete;
- restore against production data;
- merge/deploy;
- Hermes/Ollama/iai dependency upgrades.

Each live boundary still requires its own explicit owner authorization.

Core Intent Preservation: **PRESERVED**.
