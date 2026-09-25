# Nanobot Bounded Donor Evidence for Orion

Status: REFERENCE / DESIGN EVIDENCE ONLY

Pinned source: `HKUDS/nanobot`

Pinned commit: `1457904e8d6e86088e83498b239fce1b243bec5d`

PRD linkage: Orion Master PRD v2.9, especially §§6, 10.7–10.9, 10.12, 10.15, 16.3–16.5, 16.10–16.11, 20–23.

## Purpose

This document preserves the specific nanobot patterns that informed Orion PRD v2.9. It does **not** authorize importing nanobot as a runtime, dependency, gateway, scheduler, memory system, speech stack, approval engine, or autonomous-agent framework.

Orion's accepted authority model remains controlling:

- Hermes owns runtime/orchestration and preferred native voice/wake behavior.
- iai owns persistent memory.
- Obsidian is the durable human-authored vault.
- Orion owns truthful presentation/control and narrowly scoped integration.
- Manual-off remains the default lifecycle.

Code reuse from nanobot, if ever proposed, requires a separate explicit implementation authorization and an Intent Preservation Check.

## 1. Typed runtime facts, browser-safe projection, and durability

Pinned references:

- `nanobot/bus/runtime_events.py`
- `nanobot/webui/outbound_wire.py`
- `nanobot/webui/session_projection.py`
- `docs/webui.md`

Observed donor lessons:

1. Runtime facts, browser presentation payloads, and persistence/delivery policy are separate concerns.
2. Stable browser-facing projection can deliberately expose fewer fields than internal runtime events.
3. Projection should remove unnecessary binary payloads, credentials, raw provider detail, and internal metadata.
4. Reconnect should hydrate from persisted/session truth where available instead of reconstructing consequential state from DOM/browser memory.
5. Activity, retry/recovery, context, usage, latency, failure, and goal information can be inspectable without making the WebUI authoritative.

Orion bounded adoption:

- P5-03 may define a small Orion presentation vocabulary over existing Hermes/plugin facts.
- The existing narrow loopback bridge remains the preferred boundary.
- Browser presentation state never grants or widens authority.
- A new Orion event bus, broker, or durable presentation store is not authorized merely for convenience.
- Exact approval material such as a canonical operation/diff may be collapsed visually but must remain complete and inspectable.

## 2. Phase 5 action/diff/evidence presentation

Nanobot's activity/context presentation supports the design lesson that tool activity, file edits, diffs, outputs, and completed evidence can be inspectable without making the browser the execution authority.

Orion application:

- show the exact operation and canonical target;
- present the exact unified diff in a focused approval/evidence surface;
- distinguish preview, approval request/response, execution, stale refusal, success/failure, and recovery availability;
- retain a compact completed evidence record with expandable technical detail;
- never display successful approval submission as proof of successful mutation;
- derive success/recovery labels from authoritative plugin/runtime evidence.

This presentation work is P5-03 scope and does not expand P5-02 mutation authority.

## 3. Phase 4 browser recorder hardening

Pinned references:

- `webui/src/hooks/useVoiceRecorder.ts`
- `nanobot/audio/transcription.py`

Useful donor lessons:

- explicit idle/recording/transcribing states;
- serialize capture or correlate requests so stale transcription cannot submit after newer user activity;
- test and reject accidental recordings below an evidence-backed minimum;
- distinguish materially different capture/transcription errors;
- test browser MIME negotiation, including `audio/mp4` where useful;
- keep client/bridge/Hermes duration and payload constraints compatible;
- perform WAV conversion only if the accepted Hermes STT path demonstrates a real need.

Not adopted:

- nanobot's multi-provider STT registry;
- nanobot credentials/providers;
- an independent Orion transcription service;
- nanobot's exact duration threshold as a permanent Orion constant.

Hermes remains speech authority. This is a bounded hardening pass for the existing Phase 4 PR #16 path.

## 4. Phase 6 durable scheduling and corrupt-store recovery

Pinned references:

- `docs/automations.md`
- `nanobot/cron/service.py`

Useful donor lessons:

- crash-safe persistence using atomic replacement and durable flush behavior where supported;
- never treat an existing corrupt job store as a valid empty store when doing so could erase scheduled work;
- preserve corrupt state in a recoverable/operator-inspectable form;
- retain last-known-good in-memory state after successful startup when later disk corruption appears;
- after persistence failure, do not blindly reload older disk state in a way that can repeat an already-performed side effect;
- keep bounded per-run audit evidence;
- ensure a failed timer/tick does not silently stop unrelated future reminders;
- define duplicate/idempotency and missed-run recovery semantics explicitly.

Not adopted:

- nanobot's cron service as Orion's scheduler;
- a second general gateway/daemon solely because the donor has one.

Phase 6 must determine scheduler ownership first, preferring a supported Hermes surface or bounded Hermes plugin when sufficient.

## 5. Persistent Goal Mode

Pinned references:

- `nanobot/agent/tools/long_task.py`
- `nanobot/session/goal_state.py`

Useful donor lessons:

- explicit activation rather than automatic goal creation;
- one active bounded goal per session in the initial design;
- explicit persisted lifecycle including active/completed/cancelled/blocked/replaced concepts;
- reconnect-visible goal state from durable evidence;
- explicit completion rather than treating elapsed effort as success;
- ordinary tools remain the execution path while the goal record supplies continuity.

Orion intentionally retains a stronger future contract:

- explicit success criteria;
- bounded work allowance;
- permission boundaries;
- confirmed findings;
- failed approaches and reasons;
- parked approval-dependent branches;
- tactic/change tracking;
- compact next-action/checkpoint state;
- no manual-off, approval, cloud, filesystem, communications, or tool-authority bypass.

Persistent Goal Mode remains deferred and separately authorization-gated.

## Explicit bounded-use decision

Use nanobot in three primary bounded ways:

1. preserve its runtime-fact / safe-projection / durability separation as reference material for Orion HUD refinement;
2. use its durable scheduling and corrupt-store behavior as Phase 6 reminder design evidence;
3. preserve its explicit sustained-goal state model as evidence for deferred Persistent Goal Mode.

Two additional donor opportunities remain bounded inside already-open work:

- richer Phase 5 activity/diff/evidence presentation;
- small Phase 4 recorder hardening.

## Non-adoption summary

This evidence does **not** authorize:

- nanobot as an Orion runtime;
- a second general event bus or browser-owned authority model;
- a second gateway;
- a second memory system;
- a second approval engine;
- a second STT/TTS provider stack;
- automatic unapproved cloud fallback;
- unrestricted filesystem/shell capability;
- silent multi-agent operation;
- nanobot's scheduler as an additional Orion scheduler;
- implementation of Persistent Goal Mode during current Phase 4/5 execution work.
