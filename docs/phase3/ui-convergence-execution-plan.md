# UI Convergence Execution Plan

Status: **STRUCTURAL FOUNDATION MERGED / FINAL VISUAL DESIGN PASS NEXT**

Date: 2026-09-27  
Foundation merge: `d32137066a6ef20b57e1045fb8a827779cc47440`

## 1. Objective

Converge the Orion HUD from the current observatory/diagnostic composition into the intended companion experience while preserving all accepted Phase 3 and Phase 5 authority boundaries.

This is a visual/product convergence unit, not a runtime-authority redesign.

The target experience must preserve:

- a persistent Orion Core as the central visual presence;
- Conversation as the default center workspace;
- adaptive focus for approvals, memory context, system detail, vault evidence, and summoned content;
- visible provenance/authority/truth states;
- exact approval/action evidence from the accepted P5-03A/P5-03B projection;
- no browser-owned action truth, approval authority, session authority, or durable state.

## 2. Current-state finding

The current accepted HUD on main contains:

- P3-05A composition convergence;
- Conversation/System/Memory adaptive workspace;
- Orion Core state/presence foundation;
- provenance/authority indicators;
- P5-03A browser-safe projection;
- P5-03B Action Evidence / approval truth UX.

It does **not** yet implement the broader visual convergence expected for the final companion-facing HUD.

Former draft PR #26 (`P3-05B: bounded summonable presentation shell`) is **closed as superseded** and must not be merged.

Observed branch relationship:

- branch head: `04a86f14336edd224f1362a83fbc633b9b6ce1b8`;
- merge base with current main: `33c39d4bb3a685826890a387890564a44ce48ad3`;
- current main is 361 commits ahead;
- old P3-05B branch remains 10 commits ahead of that old base.

PR #26 was donor/reference material only. Its useful bounded summon behavior was selectively reconciled on current main through PR #49.

## 3. Controlling requirements

The implementation must preserve the approved HUD intent:

- Orion Core remains the central visual presence.
- Conversation remains the default workspace.
- Approval, memory, system detail, vault evidence, and summoned content may take focus without forcing unrelated navigation.
- Core state/gaze reflects observed presentation/system state only.
- Summoned content uses explicit display semantics.
- Authority indicators are descriptive only.
- No new broad frontend framework is required merely for animation.
- Browser-facing consequential state continues to come only from the accepted P5-03A projection.

## 4. Design direction

### 4.1 Visual hierarchy

The converged HUD should read in this order:

1. **Orion Core / active state**
2. **Current conversation or focused task surface**
3. **Approval / consequential action surface when present**
4. **Contextual evidence / summoned content**
5. **Secondary system/memory diagnostics**

The current dense observatory rails should be visually demoted. Diagnostic information remains available but should no longer define the first impression.

### 4.2 Center workspace

The center workspace becomes the product's primary canvas.

Supported focus modes:

- conversation;
- approval;
- action evidence;
- memory context;
- system detail;
- summon/display content.

These are presentation focus modes, not new runtime states.

### 4.3 Orion Core

The Core remains continuously present and should gain a clearer companion identity through:

- stronger central scale/presence;
- restrained idle motion;
- deterministic gaze/focus cues;
- state-driven transitions for READY / THINKING / ACTING / WAITING / DEGRADED / ERROR / STOPPING;
- reduced-motion fallback.

No camera/vision implication.

### 4.4 Approval and action evidence

P5-03B semantics remain controlling.

The convergence pass may change composition, typography, spacing, panel treatment, and responsive placement, but it must not:

- summarize away exact approval content;
- hide canonical target/diff;
- imply approval equals execution;
- fabricate success/recovery;
- move decision controls behind contextual evidence.

### 4.5 Summon/display surface

Do not merge the old P3-05B implementation directly.

Rebuild the summon surface on current main using the old branch only for bounded interaction patterns:

- preserve selected workspace underneath;
- approval focus outranks summon focus;
- dismiss returns to prior workspace;
- literal text/evidence rendering;
- HTTP/HTTPS links only unless a later approved media policy expands the contract;
- no raw HTML, iframe, arbitrary fetch, or browser-side privileged proxy.

A later explicit Hermes display-tool seam may drive this surface; presentation work must not invent transport authority.

## 5. Implementation sequence

### UI-01 — Reference and baseline freeze

Produce a short source-controlled visual contract before code changes:

- current accepted screenshots at desktop and narrow widths;
- owner-approved reference artifacts, existing Orion surfaces, sketches/wireframes, or design-system examples;
- exact hierarchy, spacing, typography, Core treatment, rail behavior, and focus transitions;
- no AI-generated visual reference is required.

Acceptance:
- owner confirms the direction before broad CSS restructuring.

### UI-02 — Structural shell convergence — COMPLETE

Refactor layout only:

- central Core/workspace hierarchy;
- secondary diagnostics;
- responsive shell;
- no new data flow;
- no projection changes.

Acceptance:
- existing HUD tests pass;
- Conversation remains default;
- System/Memory remain reachable;
- no approval/action semantics regress.

### UI-03 — Approval/action integration — COMPLETE FOR FOUNDATION

Recompose P5-03B surfaces inside the converged shell.

Acceptance:
- exact diff complete/readable;
- approval controls remain primary;
- ALLOW ONCE remains execution-unproven;
- terminal success/failure/stale/refused semantics unchanged;
- responsive checks pass.

### UI-04 — Summon/display shell reconciliation — COMPLETE FOR FOUNDATION

Reimplement the useful P3-05B behavior on current main.

Acceptance:
- workspace preserved beneath summon;
- approval outranks summon;
- dismiss restores previous focus;
- literal rendering;
- unsafe schemes rejected;
- no hidden transport or persistence authority.

### UI-05 — Core presence and motion polish — NEXT

Add restrained visual-state transitions and gaze/focus behavior.

Acceptance:
- deterministic state mapping;
- reduced-motion support;
- no fabricated perception/activity;
- no dependency on camera/vision.

### UI-06 — Final visual convergence acceptance — AFTER UI-05

Run:

- full HUD Python suite;
- all Node rendering/semantic suites;
- syntax/parse checks;
- bounded browser fixture;
- desktop visual smoke;
- narrow/tablet visual smoke;
- keyboard/focus smoke;
- approval/action truth smoke.

Capture acceptance screenshots for at least:

- desktop wide;
- standard laptop;
- narrow/tablet;
- one approval-focused state;
- one action-evidence state;
- one summon state.

## 6. Files likely affected

Expected UI-only implementation scope:

- `hud/static/index.html`
- `hud/static/styles.css`
- `hud/static/app.js`
- `hud/static/workspace-state.js`
- `hud/static/core-state.js`
- new or reconciled bounded summon presentation module
- focused HUD tests

The bridge may receive only the minimum static-module allowlist or display seam required by a separately approved summon transport slice.

## 7. Explicit non-goals

This convergence pass shall not:

- replace Hermes;
- replace iai;
- change vault mutation semantics;
- change approval authority;
- add a general event bus;
- add a second transcript/session store;
- solve reconnect/hydration by browser persistence;
- introduce multi-display routing;
- redesign voice transport;
- add arbitrary embedded browsing;
- merge old PR #26 wholesale.

## 8. Stop conditions

Stop and split the work if any visual requirement would require:

- browser-local consequential state to become authoritative;
- raw provider/private payloads;
- a generalized backend event system;
- a new approval engine;
- a new durable action/session store;
- mutation/recovery semantic changes;
- broad framework migration unrelated to the visual objective.

## 9. Branch strategy

Create a fresh implementation branch from the then-current accepted main.

Recommended branch:

`feature/orion-ui-visual-convergence-pass`

PR #26 is closed as superseded. PR #49 is merged as the structural convergence foundation.

## 10. Completion definition

UI convergence is complete when the HUD visually matches the owner-approved Orion companion direction **and** all previously accepted functional/truth boundaries remain green.

Visual quality is not accepted merely because the existing panels were restyled; the hierarchy must materially shift from diagnostic observatory toward companion-first interaction.


## 11. Foundation acceptance record

Structural foundation merged by PR #49 at:

`d32137066a6ef20b57e1045fb8a827779cc47440`

Accepted candidate:

`b1926d6ae996add2243b603b3e8fc7f21950755a`

Foundation acceptance included:

- source acceptance;
- recovery qualification for the Windows rejected-POST socket flake;
- bounded visual acceptance;
- companion-first hierarchy;
- summon composition and literal rendering;
- approval-over-summon priority;
- narrow responsive approval behavior;
- Hermes and rollback evidence unchanged;
- clean Orion worktree.

This merge is **not** the final Orion visual design. It establishes the safe structural shell and interaction contracts required for the subsequent visual-design convergence pass.

The next implementation unit is the actual visual-design pass: Core presence/polish, typography, spacing, composition, workspace treatment, and final companion identity. P5-03C reconnect/hydration follows after that visual pass is accepted.
