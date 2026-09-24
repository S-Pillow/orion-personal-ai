# Orion v2.9 — Nanobot Bounded Donor Evidence

Status: **OWNER-DIRECTED DESIGN EVIDENCE / NO DONOR RUNTIME ADOPTION**

Date: 2026-09-24

Pinned donor revision:

```text
HKUDS/nanobot
1457904e8d6e86088e83498b239fce1b243bec5d
```

## Purpose

Record the bounded architectural lessons used to prepare Orion Master PRD v2.9
without importing nanobot as an Orion runtime, gateway, memory engine,
scheduler, STT/TTS provider stack, plugin lifecycle, or authority source.

The controlling Orion authority split remains:

- Hermes: conversation/orchestration, tool/run/approval, and preferred native voice/wake authority;
- iai: persistent-memory authority;
- Obsidian: durable human-authored vault;
- Orion: visual presentation/control plus narrow Orion-owned plugins/glue;
- Windows manual-off lifecycle: operator-controlled runtime boundary.

## 1. Typed facts, safe projection, and durability

Pinned nanobot sources:

- `nanobot/bus/runtime_events.py`
- `nanobot/webui/outbound_wire.py`
- `nanobot/webui/session_projection.py`

Useful donor pattern:

1. typed internal/runtime facts describe what happened;
2. a smaller allowlisted browser projection exposes only what the UI needs;
3. projection/persistence policy is explicit rather than inferred by browser state;
4. reconnect hydrates from persisted session truth where available;
5. inline binary content is omitted from projected tool activity.

Orion adoption boundary:

- do **not** add a second event bus merely to copy nanobot;
- project existing Hermes/plugin facts through the current narrow bridge wherever practical;
- a displayed state describes authority but never grants it;
- DOM, localStorage, and JavaScript memory are not durable evidence;
- unknown/unobserved is preferable to reconstructing a stronger state than the source can prove.

Candidate Phase 5 presentation vocabulary may include semantic states such as
preview available, approval requested, approval response accepted, apply
started, apply succeeded/failed, stale refusal, and recovery available. Exact
wire names belong in a P5-03 presentation contract, not in the master PRD.

## 2. Phase 5 approval/activity/evidence presentation

Pinned reference:

- `docs/webui.md#activity-and-context-usage`

Use nanobot only as UX evidence that tool activity, file edits, diffs, command
output, artifacts, and completion evidence can be inspectable without making
the browser authoritative.

For Orion:

- keep mutation authority exclusively in Hermes + the vault-actions plugin;
- show a readable WHAT / WHY / TARGET / EFFECT / AUTHORITY REQUESTED layer;
- keep exact unified diff/operation inspectable;
- show plan token, canonical path, hashes, file identity when relevant, and
  recovery linkage in expandable technical evidence;
- distinguish preview, approval, protected execution, stale refusal, verified
  outcome, and recovery state;
- an accepted approval POST is not itself proof that the protected operation
  succeeded.

Authoritative Phase 5 approval material may be collapsed/scrollable visually,
but must not be altered or truncated in a way that changes what was approved.

## 3. Phase 4 browser recorder hardening

Pinned nanobot sources:

- `webui/src/hooks/useVoiceRecorder.ts`
- `nanobot/audio/transcription.py`

Bounded donor opportunities for draft Orion PR #16:

- explicit idle / recording / transcribing states;
- prevent overlapping transcription/capture or correlate requests so stale
  transcription cannot submit as newer speech;
- test a small accidental-recording floor, without copying nanobot's 650 ms
  value automatically;
- distinguish secure-context/browser, permission, missing-device, duration,
  empty/unusable speech, and provider failures where evidence permits;
- consider `audio/mp4` when browser compatibility evidence supports it;
- add WAV conversion only if the qualified Hermes STT path requires it;
- keep client, Orion bridge, and Hermes ingress duration/size bounds aligned.

Non-adoption:

- no nanobot STT registry;
- no nanobot provider credentials;
- no independent transcription service;
- no redesign that delays the existing live Phase 4 acceptance gate.

Hermes remains Orion's speech authority.

## 4. Phase 6 reminder durability and corrupt-store recovery

Pinned nanobot sources:

- `docs/automations.md`
- `nanobot/cron/service.py`

Useful donor evidence:

- temp-file write + file flush + atomic replacement;
- directory flush where supported;
- corrupt store is not silently treated as a valid empty store;
- corrupt data is preserved in a recoverable timestamped artifact;
- fail closed when startup/mutation would otherwise overwrite scheduled work;
- retain a last-known-good in-memory snapshot after successful startup when
  later disk corruption appears;
- preserve dirty in-memory state after persistence failure rather than
  reloading an older snapshot that could repeat an already executed side effect;
- bounded run history/audit evidence;
- failed ticks must not silently stop all future reminders;
- local-trigger delivery requires durability/recovery/idempotency semantics.

Orion adoption boundary:

Phase 6 must first decide scheduler ownership. Prefer an installed-version
Hermes mechanism or bounded Hermes plugin. Do not introduce nanobot's cron
service or a second general scheduler solely because donor code exists.

## 5. Deferred Persistent Goal Mode

Pinned nanobot sources:

- `nanobot/agent/tools/long_task.py`
- `nanobot/session/goal_state.py`
- reconnect projection in `nanobot/webui/session_projection.py`

Useful donor evidence:

- explicit activation;
- one active sustained objective per session;
- bounded/self-contained objective;
- active/completed/cancelled/blocked/replaced lifecycle;
- persisted state reappears after reconnect;
- completion is explicit rather than inferred from elapsed time;
- ordinary tools do the work; the goal record carries continuity.

Orion keeps the stronger existing design concepts:

- success criteria;
- work allowance;
- permission boundaries;
- strongest current approach;
- confirmed findings;
- failed methods and reasons;
- parked approval-dependent branches;
- next useful action;
- compact completion/blocker checkpoint.

Persistent Goal Mode remains deferred and separately authorized. It must not
keep Orion running after Stop Orion, bypass approvals, become a second memory
engine/runtime/scheduler, or silently create subagents.

## Explicit bounded-use decision

Use nanobot in three primary bounded ways:

1. typed fact/projection/durability reference material for future Orion HUD refinement;
2. durable scheduling/corrupt-store recovery evidence for Phase 6 reminders;
3. explicit sustained-goal lifecycle evidence for deferred Persistent Goal Mode.

Additional small donor opportunities:

- richer Phase 5 activity/diff/evidence presentation;
- bounded Phase 4 recorder hardening inside the existing Hermes voice path.

## Explicit non-adoption

Do not adopt:

- nanobot as Orion's runtime;
- a second gateway beside Hermes;
- Dream or another memory authority;
- a second MCP/plugin lifecycle;
- nanobot's general scheduler without a demonstrated Hermes gap and architecture approval;
- nanobot's independent STT/TTS provider stack;
- automatic unapproved cloud fallback;
- silent multi-agent/subagent autonomy;
- unrestricted shell/filesystem authority;
- browser-local state as authoritative persisted truth.

Core Intent Preservation: **PRESERVED**.
