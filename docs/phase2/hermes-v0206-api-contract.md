# Hermes v0.20.6 API Contract for Orion Phase 2A

Status: **SOURCE-VERIFIED AGAINST TAG `v2026.8.27`**

Date: 2026-09-10

Purpose: define the smallest Hermes-facing contract Orion may use for the Phase 2 HUD without introducing a second agent, voice, memory, or lifecycle runtime.

## Source of truth

This contract was verified against the accepted Orion Hermes baseline:

- tag `v2026.8.27`
- package `0.20.6`
- accepted Orion commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

Primary upstream source:

- `gateway/platforms/api_server.py`
- `website/docs/user-guide/features/api-server.md`
- `website/docs/user-guide/features/voice-mode.md`
- `website/docs/user-guide/features/wake-word.md`

Jarvis was used only to identify useful external-UI interaction patterns. The Hermes tag above is authoritative for the Orion contract.

## Architectural conclusion

Phase 2A SHOULD integrate through Hermes' supported API-server surface rather than import Hermes Python internals or recreate Jarvis' agent/voice server.

Ownership remains:

- Hermes: agent execution, sessions, run lifecycle, approvals, tools, native voice/wake
- iai: persistent memory semantics and lifecycle
- Orion: local visual/control/presentation layer

The Orion HUD bridge MUST NOT start, stop, supervise, reinstall, upgrade, or repair Hermes, Ollama, or iai.

## Network and authentication boundary

Accepted defaults:

- Hermes API: `http://127.0.0.1:8642`
- Hermes API key: `API_SERVER_KEY`
- bearer auth is required even on loopback
- Hermes does not enable browser CORS by default

Orion Phase 2A therefore uses a same-origin loopback bridge. The browser never receives `API_SERVER_KEY`; the bridge reads the key server-side and injects `Authorization: Bearer ...` only on allowlisted upstream calls.

The bridge itself binds to loopback only. Remote/LAN serving is explicitly out of scope for 2A.

## Capability discovery

### `GET /v1/capabilities`

Use this as the primary compatibility probe before enabling controls. Hermes documents it as the machine-readable stable surface for external UIs/orchestrators.

Relevant advertised capabilities include session APIs, run submission/status/events/stop/approval, and endpoint metadata. Orion MUST degrade a UI control when the running Hermes instance does not advertise the capability rather than assuming private implementation details.

## Read-only status/discovery surface

### `GET /health`

Cheap unactioned liveness probe. Expected nominal payload: `{"status":"ok"}`.

### `GET /health/detailed`

Authenticated bounded readiness/status. It intentionally reports statuses and counts without exposing credentials, commands, raw config values, or raw errors.

### `GET /v1/skills`

Authenticated read-only skills inventory.

### `GET /v1/toolsets`

Authenticated read-only toolset inventory, including the concrete tools each toolset expands to.

### `GET /api/jobs`

Authenticated scheduled/background-job inventory. Phase 2A is LIST ONLY. Job creation, update, deletion, pause/resume, and manual run are deferred because they are consequential actions.

### `GET /api/sessions`

Authenticated list of persisted Hermes sessions.

### `GET /api/sessions/{id}`

Authenticated session metadata.

### `GET /api/sessions/{id}/messages`

Authenticated persisted message history.

## Typed conversation surface

### `POST /api/sessions`

Creates an empty persisted Hermes session. Orion 2A uses a dedicated named session rather than maintaining a second transcript database.

Initial title SHOULD identify the surface, e.g. `orion-hud-main`.

### `POST /api/sessions/{id}/chat/stream`

Primary typed-turn transport for Phase 2A.

Request body:

```json
{"input":"user text"}
```

Response is SSE. Verified event family includes:

- `run.started`
- `message.started`
- `assistant.delta`
- `tool.progress`
- `tool.started`
- `tool.completed`
- `tool.failed`
- `approval.request` when approval is required
- `assistant.completed`
- `run.completed`
- failure/error events where applicable

Hermes injects `session_id`, `run_id`, and monotonically increasing `seq` into session-stream event payloads.

Important rendering rule: `assistant.delta` is a live-display stream. The authoritative post-turn transcript is persisted by Hermes and should be reconciled from session history/completion data after the turn. Orion must not create its own competing conversation-history authority.

### Relevant event payloads

`run.started` carries `run_id` and session correlation data. Orion stores the active run id in volatile UI state only.

`assistant.delta` carries at least:

```json
{"message_id":"...","delta":"...","session_id":"...","run_id":"...","seq":1}
```

Tool lifecycle payloads carry at least:

```json
{
  "message_id":"...",
  "tool_name":"...",
  "preview":"...",
  "args":{},
  "session_id":"...",
  "run_id":"...",
  "seq":2
}
```

Internal pseudo-tool activity such as reasoning may arrive as `tool.progress`; the UI should render it as state/progress, not claim it is an external tool execution.

`assistant.completed` carries the final reply content and completion metadata, plus run/session correlation.

## STOP / cancellation

### `POST /v1/runs/{run_id}/stop`

Supported Hermes cancellation surface.

Hermes returns immediately with `{"status":"stopping"}` while the executor remains tracked until it actually exits and reaches `cancelled`.

Orion requirements:

- STOP is enabled only when a syntactically valid active `run_id` is known.
- A request with no active run fails locally without inventing a target.
- Orion never kills Hermes/Ollama/iai processes to implement turn cancellation.
- UI remains in a stopping state until Hermes stream/status reconciles the terminal run state.

## Approval handling

### `POST /v1/runs/{run_id}/approval`

Supported human-decision surface for a run waiting on approval.

Accepted request field:

```json
{"choice":"once"}
```

Allowed normalized choices in the accepted Hermes source:

- `once`
- `session`
- `always`
- `deny`

Hermes also normalizes aliases `approve`, `approved`, and `allow` to `once`, but Orion SHOULD send the canonical values above.

If a run has no pending approval, Hermes returns HTTP 409 with `approval_not_pending`. Orion must display that as reconciliation, not retry blindly.

Security note: `approval.request` output redacts command text through Hermes' approval redaction boundary before it reaches the external UI.

## Runs API

Hermes also provides:

- `POST /v1/runs`
- `GET /v1/runs/{run_id}`
- `GET /v1/runs/{run_id}/events` (SSE)

These are useful for reconnect/resume and future thick-client behavior. Phase 2A's typed proof uses persisted-session chat streaming because it naturally keeps the HUD transcript inside Hermes' existing SessionDB. Run-status polling MAY be used for reconciliation but Orion should avoid creating a parallel run state machine.

## Voice / wake posture

Phase 2A does not implement voice.

The accepted Hermes pin already documents native:

- local STT
- streaming TTS
- full-duplex barge-in
- stop phrases
- interruption awareness
- local wake-word detection
- openWakeWord, sherpa open-vocabulary, and Porcupine wake engines

Phase 2E will integrate those supported surfaces first. Jarvis' custom RealtimeSTT/ElevenLabs voice orchestration is not part of the 2A bridge.

## Explicitly deferred consequential surfaces

The following supported Hermes endpoints are NOT exposed by the Phase 2A bridge:

- job create/update/delete/pause/resume/run
- session delete/fork/model mutation
- `/v1/runs/{run_id}/steer`
- browser-controller registration/control
- model/provider mutation
- plugin/toolset mutation
- any filesystem/terminal proxy outside normal Hermes agent turns

They require separate requirements, authority, and acceptance tests.

## Phase 2A allowlist

Bridge upstream allowlist:

Read:

- `/health`
- `/health/detailed`
- `/v1/capabilities`
- `/v1/skills`
- `/v1/toolsets`
- `/api/jobs`
- `/api/sessions`
- `/api/sessions/{id}`
- `/api/sessions/{id}/messages`
- `/v1/runs/{run_id}`

Write/control:

- `POST /api/sessions`
- `POST /api/sessions/{id}/chat/stream`
- `POST /v1/runs/{run_id}/stop`
- `POST /v1/runs/{run_id}/approval`

No generic arbitrary-path proxy is permitted.

## Core Intent Preservation

**PRESERVED.**

This contract makes Orion a client/presentation layer on top of Hermes' supported external-UI API. It does not replace Hermes' agent/runtime role, iai's memory role, or the accepted manual-off lifecycle architecture.
