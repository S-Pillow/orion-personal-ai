# Phase 2 Status — HUD / Companion Interface

Status: **PHASE 2A TYPED-CONTROL SLICE ACCEPTED / MERGED; PRD PHASE 2 REMAINS ACTIVE**

Date: 2026-09-10

Controlling baseline: **ORION — Master PRD v2.8**, approved 2026-09-10.

PRD v2.8 supersedes v2.7 and is the current normative specification. Historical repository labels such as `Phase 2A` through `Phase 2F` are subordinate planning subdivisions and must not override the PRD v2.8 phase table.

## Entry condition and accepted foundation

Phase 0 is **PASS / CLOSED** on the accepted native-Windows/manual-off baseline.

Phase 1 is **PASS / CLOSED**. Closure was merged to `main` in PR #6 at commit:

`7c55493e0401f1003b3f0f2438e684a5fb144227`

The accepted lifecycle/memory foundation remains unchanged unless contradictory evidence or a dependency/configuration change invalidates its premise.

## Current checkpoint

The internal **Phase 2A compatibility + typed-control HUD bridge slice** is **PASS / ACCEPTED / MERGED**.

Accepted feature head:

`faec8769a34e049cd48408be2445198f7647765b`

Merged through PR #9 into `main` at:

`55a229ef77972491eff8765727ddbe26f2920b95`

The final synthetic HUD suite passed **25/25** tests. Controlled live acceptance covered loopback serving, persistent COMPANION typed-session continuity, progressive SSE streaming, STOP, browser credential isolation, DEFAULT-vs-COMPANION credential separation, Hermes-routed iai `memory_recall`, truthful degraded-state presentation, blank transcript suppression, automatic persisted-session transcript load on restart, and return to clean manual-off state.

Detailed record:

`evidence/phase2a/live-acceptance-2026-09-10.md`

This closes the **internal Phase 2A typed-control slice only**. Do not mark the entire PRD Phase 2 acceptance plan closed yet.

## Why PRD Phase 2 is still administratively open

PRD v2.8 §16.3 Typed HUD acceptance contains requirements not exercised by the accepted Phase 2A bridge slice, including:

- visible summoned content through an explicit display path;
- deterministic Orion Core gaze/state behavior tied to active UI/system state;
- Memory Lens handoff to the installed iai-native IAI Brain surface with installed-version-supported health/provenance context.

Those requirements align materially with the PRD Phase 3 presentation/workspace scope. They remain open until implemented and accepted; Phase 2A merge evidence must not be stretched to cover them.

## Product direction

Orion's HUD is a distinct companion interface, not a reskinned Jarvis clone.

The approved direction remains:

- a persistent **Orion Core** as the assistant's visual presence;
- subtle celestial/masked-face identity rather than a literal Iron-Man reactor;
- lightweight state-driven motion such as blink, micro-saccade, small head/parallax drift, breathing/pulse, and gaze toward active UI targets;
- adaptive center workspace that expands when useful content needs focus;
- compact status/activity/approval surfaces;
- explicit **Memory Lens -> native IAI Brain** handoff rather than a second memory-management system;
- first-class visible agent activity, STOP/cancel, and approval boundaries;
- explicit display/summon paths for content shown to the user;
- truthful local/cloud/source, authority, and voice-privacy indicators;
- reduced-motion/performance behavior from the start.

Full 3D facial rigging, photorealistic lip sync, or heavyweight Unreal/MetaHuman rendering is not required for V1.

## Governing architecture

The accepted ownership model is unchanged:

- **Hermes owns the agent runtime and native voice/wake path.**
- **iai owns persistent memory.**
- **Orion owns the living visual companion, presentation, and authorized control surface.**

Orion must not duplicate those authorities for convenience.

The accepted Phase 2A bridge preserves this split: it is a narrow loopback presentation/control adapter with no subprocess/shell/process-management authority and no independent memory or voice runtime.

## Dependency posture

No upstream dependency upgrade is authorized by this status record.

Accepted baselines remain:

- Hermes: `v2026.8.27` / package `0.20.6`
- iai: `iai-pme==3.0.8`
- accepted operator publication: `2.7.4-candidate1`
- installed Ollama observed during Phase 2A preflight: `0.32.15`

Newer Hermes, iai, Ollama, or presentation dependencies require their own evidence-backed qualification gate.

## Roadmap reconciliation

The earlier repository status document used internal labels `Phase 2A` through `Phase 2F` to subdivide HUD implementation. After PRD v2.8 approval, the **PRD phase table is controlling**.

Use the following mapping going forward:

- internal **Phase 2A** = the now-accepted compatibility + typed-control bridge slice within PRD Phase 2;
- former internal **2B/2C/2D** concepts are not future peer phase numbers; their remaining shell/Core/workspace/memory-transparency work belongs under **PRD Phase 3**;
- former internal **2E** voice/wake work belongs under **PRD Phase 4**;
- remaining mutating vault/display, cloud/reminder, and device/LAN/proactivity/hardening work follows PRD Phases **5–7**.

This prevents two competing phase-number systems from driving execution.

## Next authorization target

The next product-development target is **PRD Phase 3 — Orion Core + adaptive workspace + memory transparency**.

Begin with a bounded **read-only design/source inventory** before changing presentation code. The inventory should establish the smallest implementation plan for:

1. Orion Core state machine and deterministic gaze/state mapping;
2. adaptive center workspace and summonable-panel shell;
3. Memory Lens health/provenance surface and native IAI Brain handoff on the actually installed iai version;
4. truthful local/cloud/source and descriptive authority indicators;
5. modular frontend decomposition, responsive/reduced-motion constraints, and the least-complex rendering approach that preserves product intent.

Rive MAY be prototyped only if a small isolated comparison demonstrates material UX/maintainability value; SVG/Canvas remains an acceptable fallback. Do not introduce a broad frontend framework or build pipeline without a separate owner decision.

Voice/wake is not the next implementation unit. PRD Phase 4 comes after the typed/Core/workspace path is stable and should reuse Hermes-native voice/wake unless a demonstrated gap is separately approved.

No HUD convenience feature may mutate the accepted manual-off lifecycle or silently create a second gateway, memory system, voice stack, or supervisor.

Core Intent Preservation: **PRESERVED**.
