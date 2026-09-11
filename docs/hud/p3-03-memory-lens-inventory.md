# P3-03 Memory Lens / IAI Brain — Read-Only Design and Source Inventory

Status: **INVENTORY COMPLETE / IMPLEMENTATION NOT YET STARTED**

Date: 2026-09-10

Branch: `feature/orion-phase3-memory-lens`

Base `main`: `8ce0b1c9da4889abfe5e1561e7488a33dd8b4ab1`

Controlling baseline: **ORION — Master PRD v2.8**.

## Purpose

Define the smallest Phase 3 Memory Lens implementation that preserves the accepted ownership model:

- Hermes owns the agent/session/runtime and native voice/wake path.
- iai owns persistent memory and detailed memory administration.
- Orion owns presentation and an explicitly authorized control surface.

The Memory Lens must explain memory state/context without becoming a second memory engine, store, ranking system, or administrative UI.

## Accepted entry state

The following current-HUD slices are already accepted and merged:

- P3-01 Orion Core state foundation: PR #10.
- P3-02 adaptive workspace foundation: PR #11.
- Current `main`: `8ce0b1c9da4889abfe5e1561e7488a33dd8b4ab1`.

The current HUD already provides:

- `core-state.js` with deterministic presentation/gaze state and reduced-motion behavior;
- `workspace-state.js` with Conversation/System workspace switching and approval focus;
- the persistent typed Hermes session path;
- progressive SSE streaming, STOP, approvals, activity, readiness/degraded state, capabilities, skills, and jobs;
- a disabled IAI Brain control placeholder in the left Memory rail.

No new framework or build pipeline is needed for P3-03.

## iai 3.0.8 source findings

The accepted Orion iai runtime remains `iai-pme==3.0.8`.

Important finding: **an iai upgrade is not required merely to obtain IAI Brain**.

The upstream `v3.0.8` release already publishes IAI Brain 1.0.0 artifacts, including Windows x64 setup EXE and MSI assets.

The v3.0.8 desktop app contract is:

- Tauri desktop wrapper named `IAI Brain`;
- default dashboard port `4477`;
- loopback dashboard identity before navigation;
- starts `iai brain --no-open --port <port>` when the dashboard is not already running;
- closing the desktop window stops the dashboard child that the app started;
- the iai sleep daemon is not stopped by closing IAI Brain.

This behavior preserves iai as the memory authority and makes the vendor Brain surface the correct detailed-management destination.

## Brain HTTP surface at v3.0.8

The vendor Brain server is loopback-only and separates read-only GET observations from POST mutation/admin actions.

Read-only GET surfaces observed in v3.0.8:

- `/api/overview`
- `/api/graph`
- `/api/events`
- `/api/economy`
- `/api/browse`

Mutation / administrative POST surfaces include capture, teach, forget, rescue, pin, surface, search, browse-with-input, and daemon actions. Those POST surfaces are **out of scope for Orion Memory Lens**.

## Recommended P3-03 architecture

### P3-03A — Memory Lens observation surface

Add a third workspace named `memory` using the existing workspace controller.

The Lens should remain read-only and show only information that can be truthfully observed from accepted sources, for example:

- memory authority: iai;
- Hermes-side iai/MCP availability when exposed by accepted Hermes readiness/capability data;
- IAI Brain dashboard reachability/identity on loopback;
- high-level read-only Brain overview fields that are safe and useful to show;
- whether displayed information is live, stale, degraded, or unavailable;
- most recent memory-tool activity observed through the existing Hermes event path;
- explanatory text that detailed search/pin/fade/rescue/teach/admin work belongs in IAI Brain.

The Orion bridge may add only explicit, fixed, read-only Memory Lens routes. It must not expose an arbitrary proxy to port 4477 and must not forward vendor POST endpoints.

### P3-03B — Native Brain handoff

Do **not** add a generic shell/process launcher to the HUD bridge.

First perform a read-only Windows inventory of whether IAI Brain 1.0.0 is actually installed and how the installed package exposes its launch target.

Preferred handoff order:

1. If the vendor Brain dashboard is already running and its identity is verified, open/link to the vendor loopback surface.
2. If the native desktop app is installed, use a separately reviewed, exact-target handoff mechanism only if it can be implemented without creating general process-launch authority.
3. If no safe exact-target handoff exists, keep the Lens truthful: show Brain as installed/not-running or unavailable and direct the operator to the vendor Brain app/CLI rather than inventing a broad launcher.

A generic executable path, arbitrary command, or shell endpoint is prohibited.

## Security / authority boundaries

P3-03 must preserve all of the following:

- no second memory store or memory semantics;
- no direct writes to the iai store;
- no forwarded Brain POST/admin endpoints;
- no arbitrary upstream proxy;
- no Hermes credential exposure to browser JavaScript;
- no lifecycle/supervisor authority;
- no dependency upgrade;
- no broad subprocess/shell authority;
- no claim that Brain is installed until the Windows machine proves it.

## Frontend decomposition

Do not expand `app.js` with all Memory Lens logic inline.

Recommended module boundary:

- `memory-lens.js` — pure normalization/render/state helpers plus narrow fetch orchestration;
- `workspace-state.js` — only workspace selection/focus logic;
- `core-state.js` — only Core presentation/state logic;
- `app.js` — integration wiring and Hermes event handoff.

The Memory Lens module should be independently testable without network authority when its data/fetch functions are injected or separated.

## Acceptance plan

Synthetic/source acceptance should prove:

- Memory workspace is deterministic and accessible;
- Conversation and System workspaces remain unchanged;
- Memory Lens routes are fixed read-only routes only;
- vendor Brain POST surfaces cannot be reached through Orion;
- foreign processes on port 4477 are not trusted merely because the port is open;
- unavailable Brain produces an honest unavailable state, not an error cascade;
- no memory content is logged to console/server logs by default;
- reduced-motion and existing Core behavior remain intact;
- full existing HUD test suite remains green.

Live smoke should then prove, without memory mutation:

- accepted Start Orion / Stop Orion lifecycle remains unchanged;
- Memory workspace renders;
- iai/MCP state is truthful;
- Brain reachability/identity is truthful;
- opening/linking to Brain does not alter the canonical memory store or daemon lifecycle unexpectedly;
- final cleanup returns to accepted manual-off state.

## Stop conditions

Stop P3-03 implementation if any of the following becomes necessary:

- iai upgrade or store migration;
- generic process/shell execution from the HUD;
- direct store access by Orion;
- forwarded Brain mutation/admin endpoint;
- new frontend framework/build pipeline;
- lifecycle change;
- duplicate memory ranking/explanation semantics that compete with iai.

Any of those requires a separate design/authorization decision.

## Next bounded action

Run a **read-only Windows installed-surface inventory** for IAI Brain 1.0.0 / `iai brain` on the accepted machine. Do not install, upgrade, launch, or modify iai during that inventory.

If the installed surface is confirmed, proceed with P3-03A read-only Memory Lens implementation first. P3-03B handoff follows only after the exact vendor launch/link surface is proven.

Core Intent Preservation: **PRESERVED**.
