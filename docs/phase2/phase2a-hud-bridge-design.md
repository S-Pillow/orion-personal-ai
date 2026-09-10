# Phase 2A HUD Bridge Design

Status: **IMPLEMENTATION DESIGN**

Date: 2026-09-10

## Goal

Build the smallest local Orion HUD bridge that proves persistent typed Hermes interaction, live agent/tool activity, STOP, approvals, and read-only status without creating a second agent, voice, memory, or lifecycle runtime.

## Chosen implementation

A Python standard-library loopback bridge is preferred for 2A.

Reasons:

- no new package dependency
- no Node/FastAPI runtime required for the proof
- easy Windows execution using an existing Python 3 interpreter
- supports static-file serving, ordinary JSON proxy calls, and byte-streaming Hermes SSE
- keeps `API_SERVER_KEY` server-side
- foreground/manual process only; no service, Scheduled Task, or auto-start

This is intentionally a Phase 2A proof surface, not the final Phase 2B frontend architecture.

## Process boundary

The bridge:

- binds only to `127.0.0.1`
- defaults to port `8765`
- reads only `API_SERVER_KEY` from the COMPANION profile `.env` unless explicitly provided through `ORION_HERMES_API_KEY`
- talks only to loopback Hermes `127.0.0.1:8642`
- never invokes Start Orion, Stop Orion, `hermes gateway`, Ollama, iai, task scheduler, service manager, installer, updater, shell, or process-kill commands
- exits when its foreground process exits

The HUD therefore cannot become a lifecycle supervisor by accident.

## Browser boundary

The browser never receives the Hermes bearer key.

The bridge serves the UI and its own `/api/orion/*` endpoints from one origin. It maintains a random per-process browser session cookie and rejects state-changing requests from a different `Origin`.

No generic proxy endpoint exists. Every upstream Hermes path is constructed by bridge code from validated ids and an explicit operation allowlist.

## Phase 2A local API

Read-only:

- `GET /api/orion/status`
- `GET /api/orion/capabilities`
- `GET /api/orion/skills`
- `GET /api/orion/toolsets`
- `GET /api/orion/jobs`
- `GET /api/orion/sessions`
- `GET /api/orion/sessions/{id}`
- `GET /api/orion/sessions/{id}/messages`
- `GET /api/orion/runs/{id}`

Typed/control:

- `POST /api/orion/sessions` -> Hermes `POST /api/sessions`
- `POST /api/orion/sessions/{id}/chat/stream` -> Hermes session SSE stream
- `POST /api/orion/runs/{id}/stop` -> Hermes supported STOP endpoint
- `POST /api/orion/runs/{id}/approval` -> canonical choice `once|session|always|deny`

## Local status behavior

`GET /api/orion/status` is safe while Hermes is off. It returns bridge state plus a bounded Hermes liveness result; it does not start Hermes.

The initial HUD can therefore be opened while Orion is manually off and display `HERMES OFFLINE` instead of changing machine state.

## Session behavior

The browser stores only the current Hermes `session_id` in localStorage for UI convenience. Hermes SessionDB remains the transcript authority.

If a stored session no longer exists, the UI allows creation of a new `orion-hud-main` session. Phase 2A does not silently delete or mutate other sessions.

## Streaming behavior

The bridge forwards the Hermes `text/event-stream` response without interpreting or rewriting event payloads. This preserves the accepted upstream contract and avoids inventing a competing event model.

The browser parses SSE frames and uses:

- `run.started` -> active run + THINKING state
- `assistant.delta` -> live assistant text
- `tool.progress` -> THINKING/progress
- `tool.started` -> ACTING state + activity card
- `tool.completed`/`tool.failed` -> activity completion
- `approval.request` -> approval card + WAITING state
- `assistant.completed` -> final response
- `run.completed`/failure -> reconcile active run and READY state

## STOP behavior

The browser enables STOP only with a current run id. The bridge independently validates the run id shape and refuses missing/invalid ids.

STOP never maps to process termination.

## Approval behavior

The Phase 2A UI exposes canonical Hermes choices only:

- Allow once
- Allow for session
- Always allow
- Deny

The UI sends the exact canonical value via `{"choice":"..."}`. An upstream 409 `approval_not_pending` is displayed as a reconciliation condition rather than retried.

## Deliberately minimal UI

Phase 2A does not attempt the final Orion visual design. It will provide a clean dark proof interface with:

- connection/runtime status
- persistent typed transcript
- live agent activity
- STOP control
- approval cards
- basic skills/jobs visibility

The animated Orion Core, adaptive workspace, iai Brain, gaze, particles, and voice enter in later approved Phase 2 gates.

## Acceptance boundary

2A code can be merged only after:

- static review confirms no lifecycle/process mutation path
- bridge unit tests pass without live Hermes
- local read-only preflight records installed Ollama version and accepted task policy
- live proof uses accepted Start Orion lifecycle rather than the bridge starting dependencies
- typed persistent turn passes
- tool event visibility passes
- STOP no-target behavior passes
- approval path is tested when an approval event can be safely produced, or explicitly carried as a bounded follow-up if no safe deterministic trigger exists
- stopping the bridge leaves Hermes/Ollama/iai state unchanged

Core Intent Preservation: **PRESERVED**.
