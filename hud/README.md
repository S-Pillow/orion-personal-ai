# Orion HUD — Phase 2A Typed-Control Proof

This directory contains the first Orion HUD implementation proof.

It is deliberately smaller than the planned Phase 2B/2C product UI. Its job is to prove the security and interaction boundary before the cinematic Orion Core, adaptive workspaces, iai Brain, and voice are layered on top.

## What this build does

- serves a local HUD at `http://127.0.0.1:8765`
- observes Hermes liveness without starting it
- keeps `API_SERVER_KEY` out of browser JavaScript
- lists Hermes sessions, skills, jobs, and advertised capabilities
- creates a named persisted Hermes session
- loads persisted Hermes message history
- streams a typed turn from `/api/sessions/{id}/chat/stream`
- renders live assistant deltas and tool lifecycle events
- captures the active Hermes `run_id` for STOP
- sends STOP through Hermes `/v1/runs/{run_id}/stop`
- renders approval requests and sends canonical `once|session|always|deny` choices

## What it cannot do

The bridge contains no process-management or shell-execution facility. It cannot:

- start or stop Hermes
- start or stop Ollama
- start or stop iai
- create/modify Scheduled Tasks
- install or update dependencies
- kill processes
- mutate jobs
- delete/fork/model-switch Hermes sessions
- steer arbitrary runs
- expose an arbitrary upstream proxy path

It is a foreground client process only.

## Requirements

- Windows 11 accepted Orion environment
- Hermes accepted pin running through the normal **Start Orion** lifecycle when live chat is desired
- Python 3.11+; no third-party Python packages are required by the bridge
- COMPANION profile `API_SERVER_KEY` available from `%LOCALAPPDATA%\hermes\profiles\companion\.env`, or explicitly supplied in process environment as `ORION_HERMES_API_KEY`

The bridge does not modify the Hermes `.env` file.

## Run unit tests

From the repository root:

```powershell
python -m unittest discover -s hud\tests -p "test_*.py" -v
```

The tests use an in-process fake Hermes server and consume no model calls, no VT/API quota, and no external network access.

## Start the bridge manually

From the repository root:

```powershell
python .\hud\orion_hud_bridge.py
```

Then open:

```text
http://127.0.0.1:8765
```

The bridge prints only its local URL, Hermes loopback target, whether a credential was found, and lifecycle-authority status. It never prints the credential value.

Press `Ctrl+C` to stop the HUD bridge. Stopping the bridge issues **no** Hermes/Ollama/iai stop action.

## Manual-off behavior

You may open the HUD bridge while Hermes is off. The UI should show `HERMES OFFLINE`. It must not start the accepted runtime.

For a live typed proof, start Orion only through the already-accepted Start Orion control. The HUD bridge then connects as a client.

## Configuration

Defaults:

```text
HUD bind:    127.0.0.1:8765
Hermes API:  http://127.0.0.1:8642
```

Optional bridge arguments:

```text
--port <port>
--hermes-url http://<loopback-host>:<port>
--hermes-env <path-to-companion-.env>
```

`--host` exists for explicit validation but Phase 2A rejects any value other than `127.0.0.1`.

The Hermes URL is also restricted to a bare HTTP loopback origin. LAN/public targets are intentionally rejected in 2A.

## Browser security boundary

- same-origin static UI and bridge API
- random per-process HttpOnly + SameSite=Strict UI cookie
- state-changing requests require matching `Origin`
- restrictive Content Security Policy
- no browser CORS requirement on Hermes
- no Hermes bearer key in HTML/JS responses
- explicit route construction instead of arbitrary-path proxying

This is not a claim that later LAN/mobile serving can reuse the same trust model. Remote clients require a separate authenticated design gate.

## Source contract

See:

- `docs/phase2/hermes-v0206-api-contract.md`
- `docs/phase2/phase2a-hud-bridge-design.md`

## Next acceptance step

Run the Phase 2A read-only Windows preflight first. It records the installed Ollama version, confirms accepted manual-off task policy, and syntax/tests this bridge without starting the runtime.

Only after that passes should the controlled live typed proof begin.
