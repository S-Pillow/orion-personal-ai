# Nanobot Bounded Donor Evidence — 2026-09-24

Status: **REFERENCE / DESIGN EVIDENCE ONLY**

Pinned donor source:

`HKUDS/nanobot@1457904e8d6e86088e83498b239fce1b243bec5d`

This document records the exact nanobot patterns reviewed while preparing Orion Master PRD v2.9. It is not authorization to install, vendor, execute, or copy nanobot as an Orion runtime component.

## Authority boundary

Orion retains its accepted split:

- **Hermes** — agent runtime, session/run/tool/approval authority, and preferred native voice/STT/TTS/wake authority.
- **iai** — persistent-memory authority.
- **Obsidian** — durable human-authored document vault.
- **Orion** — local presentation/control layer and bounded plugins/adapters where separately accepted.

Nanobot has **no Orion runtime authority**.

## 1. Typed runtime facts, safe projection, and reconnect state

Reviewed exact files:

- `nanobot/bus/runtime_events.py`
- `nanobot/webui/outbound_wire.py`
- `nanobot/webui/session_projection.py`
- `docs/webui.md`

Observed donor patterns:

- immutable typed runtime facts for turn/session state;
- a smaller browser-facing wire projection rather than direct exposure of every internal object;
- explicit persistence/delivery classification at the projection boundary;
- inline binary/base64 content omission from projected tool events;
- reconnect hydration from persisted session metadata where available;
- same-process active-turn state kept distinct from durable persisted state.

Orion application:

- use a narrow presentation vocabulary over existing Hermes/plugin facts;
- do not introduce a second general event bus merely to imitate nanobot;
- redact secrets, binary payloads, raw provider errors, and unnecessary internal metadata;
- browser state describes observed authority and never grants authority;
- reconnect should use supported persisted truth; otherwise show unknown/unobserved.

Candidate Phase 5 presentation concepts include preview readiness, approval request/response, apply start/outcome, stale-plan refusal, and recovery availability. Exact public names belong in the P5-03 presentation contract rather than the master PRD.

## 2. Phase 5 diff/activity/evidence presentation

Reviewed:

- `docs/webui.md#activity-and-context-usage`
- Orion's existing Phase 5 approval/HUD source and evidence.

Useful donor lesson:

A browser can make tool activity, edits, diffs, command output, artifacts, failures, retry/recovery state, usage, and completed evidence inspectable without becoming the authority that executes those actions.

Orion-specific constraint is stronger for approvals:

- the exact canonical operation/diff used for approval must remain complete and inspectable;
- visual collapse/scrolling is acceptable;
- silent truncation or substitution of the authoritative approval material is not.

P5-03 should distinguish at least:

- preview produced;
- Hermes approval requested;
- approval response accepted by the Hermes surface;
- authoritative execution start/outcome when observable;
- stale/refused plan;
- recovery evidence available.

A successful approval HTTP response is not itself proof that the protected mutation succeeded.

## 3. Phase 4 bounded browser-recorder hardening

Reviewed exact files:

- `webui/src/hooks/useVoiceRecorder.ts`
- `nanobot/audio/transcription.py`

Observed donor patterns:

- explicit `idle`, `recording`, and `transcribing` UI states;
- second capture prevented while transcription is pending;
- tested minimum-duration rejection (nanobot uses 650 ms);
- bounded maximum duration;
- structured errors for insecure context, permission/no-device/unsupported conditions, excessive duration, and transcription failures;
- browser MIME negotiation including WebM, MP4, and Ogg options;
- optional WAV conversion;
- ingress validation for MIME, duration, and upload size.

Orion disposition:

- small hardening pass only when Phase 4 PR #16 resumes;
- do not replace Hermes STT/TTS or delay the existing live acceptance gate with a voice redesign;
- 650 ms is donor evidence, not an Orion constant;
- `audio/mp4` is a compatibility candidate, not a mandated first choice;
- add WAV conversion only if qualified Hermes STT behavior demonstrates that browser-native formats are insufficient;
- keep client, Orion bridge, and Hermes limits compatible and predictable;
- do not import nanobot's multi-provider transcription registry or provider credentials.

Current Orion evidence remains that PR #16's final blocker is live TTS/provider-path acceptance, not a demonstrated need for a new transcription architecture.

## 4. Phase 6 durable scheduling and corrupt-store recovery

Reviewed exact files:

- `docs/automations.md`
- `nanobot/cron/service.py`

Observed donor patterns:

- temp-file write + flush/fsync + atomic replace;
- parent-directory flush where supported;
- corrupt store preserved with a timestamped recovery suffix;
- corrupt parse result is not silently converted into an empty valid job set;
- fail-closed startup behavior where continuing could overwrite scheduled work;
- last-known-good in-memory snapshot retained after later corruption;
- dirty in-memory state retained after persistence failure so an already-executed action is not made due again merely by reloading older disk state;
- bounded per-job run history;
- scheduler timer rearming/service continuation after errors;
- persisted routing metadata and explicit handling for invalid/unbound jobs.

Orion Phase 6 use:

- treat these as durability/recovery design evidence;
- first decide the actual scheduler owner against the accepted Hermes version;
- prefer a Hermes-supported mechanism or bounded Hermes plugin if sufficient;
- do not run nanobot cron beside Hermes merely because it exists;
- define duplicate/idempotency semantics, missed-run recovery, per-run audit, and operator-visible needs-attention state before implementation.

## 5. Deferred Persistent Goal Mode

Reviewed exact files:

- `nanobot/agent/tools/long_task.py`
- `nanobot/session/goal_state.py`
- reconnect behavior in `nanobot/webui/session_projection.py`

Observed donor patterns:

- explicit user opt-in;
- one active sustained objective per session;
- self-contained bounded objective;
- persisted lifecycle state;
- explicit complete/cancel/block/replace transitions;
- completion requires an explicit terminal transition rather than elapsed time;
- ordinary tools continue doing the work;
- the durable goal record carries continuity rather than becoming a second runtime;
- active/blocked state can be projected again after reconnect.

Orion disposition:

Persistent Goal Mode remains deferred. Orion's future model is intentionally stronger and should retain:

- explicit success criteria;
- work allowance/resource boundary;
- permitted/prohibited actions;
- strongest current approach;
- confirmed findings;
- failed methods with reasons;
- parked approval-dependent branches;
- next useful action;
- compact completion/blocker recap.

Persistent Goal Mode must not:

- keep Orion running after Stop Orion;
- bypass normal approvals;
- expand filesystem/cloud/tool rights;
- become a second memory engine;
- silently create subagents;
- imply autonomous completion from elapsed time or token use.

## Explicit non-adoption list

The following are not approved by this donor review:

- nanobot as Orion's runtime;
- nanobot gateway alongside Hermes;
- nanobot Dream or another memory authority;
- a second MCP/plugin lifecycle;
- nanobot's transcription-provider registry or credentials;
- nanobot cron as a second scheduler without an accepted architecture decision;
- automatic unapproved cloud fallback;
- autonomous/silent subagent swarms;
- unrestricted shell/filesystem access;
- silent marketplace skill installation.

## Phase mapping

- **Phase 4 / PR #16:** bounded recorder hardening only; final live TTS/barge-in gate remains controlling.
- **Phase 5 / P5-03:** typed fact/projection/durability contract, richer action evidence UX, then reconnect/hydration qualification.
- **Phase 6:** durability-first reminder/scheduler discovery and implementation.
- **Deferred:** Persistent Goal Mode after active Phase 4/5 execution work closes and only through separate authorization.

## Source links

Exact pinned sources:

- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/nanobot/bus/runtime_events.py
- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/nanobot/webui/outbound_wire.py
- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/nanobot/webui/session_projection.py
- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/docs/webui.md
- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/webui/src/hooks/useVoiceRecorder.ts
- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/nanobot/audio/transcription.py
- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/docs/automations.md
- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/nanobot/cron/service.py
- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/nanobot/agent/tools/long_task.py
- https://github.com/HKUDS/nanobot/blob/1457904e8d6e86088e83498b239fce1b243bec5d/nanobot/session/goal_state.py

Related Orion evidence:

- issue #19 — P4-04B native TTS/live voice acceptance
- draft PR #16 — Phase 4 PTT voice foundation
- PR #33 — P5-02S production-move readiness
