# Jarvis Reference Study — 2026-09-09

Reference repository:

`S-Pillow/jarvis_ai`

Upstream/source:

`eadmin2/jarvis_ai`

Purpose: understand the implementation deeply enough to decide what Orion should reuse, adapt, replace, or avoid during Phase 2.

## Executive conclusion

Jarvis is a strong **reference implementation** for a Hermes-facing HUD. Its most valuable contributions are the interaction model, explicit visible-display tool, session/run event handling, STOP/approval UX, credential-isolating proxy, and practical lessons around browser audio and media panels.

It should **not** become Orion's architecture wholesale.

The biggest reason is that Jarvis was built around Hermes v0.16-era needs and implements its own STT/TTS/voice orchestration. Orion's already-accepted Hermes v0.20.6 pin now includes native streaming voice, barge-in, local wake-word support, and profile-scoped voice configuration. Carrying Jarvis' full voice pipeline forward would duplicate a capability Hermes already owns and create a second source of truth.

Recommended posture:

**Jarvis = reference implementation + selective code donor. Orion = separate modular product.**

## Repository anatomy

Current fork layout:

- `README.md` — project overview, architecture, security model, usage
- `server/server.py` — FastAPI voice/HUD core, Hermes client, STT/TTS, WebSockets, proxying, usage, machines
- `server/hud/index.html` — entire HUD as one large vanilla HTML/CSS/JS file
- `server/config/server.example.yaml` — Hermes, STT, TTS, machine, security, server configuration
- `server/scripts/` — start/stop/health/smoke, TLS certs, boot audio, WebSocket test
- `client/client.py` — optional Windows/Linux push-to-talk and wake-word client
- `worker/stt_server.py` — optional remote GPU Whisper worker
- `worker/worker_stats.py` — lightweight remote CPU/GPU telemetry server
- `hermes-plugin/hud_display/` — Hermes tools for visible HUD media
- `launchd/` — macOS auto-start templates
- `docs/ARCHITECTURE.md`, `SETUP.md`, `TROUBLESHOOTING.md`

The fork's current main tree matches the inherited upstream tree at commit `88998de8369e9d36f6d434b5e01feb93fcf1c33f` as reviewed on 2026-09-09.

## Voice turn flow in Jarvis

Jarvis' browser voice path is well thought out:

1. browser captures 16 kHz mono PCM and streams raw int16 frames over `/ws`
2. server performs partial transcription during speech
3. final transcription tries optional GPU STT first and local Whisper fallback second
4. text is submitted to a persistent named Hermes session using the Sessions API
5. Hermes SSE events drive run ID, assistant deltas, tool activity, approvals, completion, and usage
6. assistant text is sentence-buffered, markdown/think content stripped, secret-shaped strings redacted
7. sentences stream to ElevenLabs while generation is still in progress
8. raw TTS PCM streams back to the browser
9. barge-in cancels current playback/run and records the last sentence the user actually heard
10. the next user turn receives an interruption note so the agent is not unaware that speech was cut off

This is a good interaction model even where Orion does not reuse the implementation.

## Hermes session handling

Jarvis persists conversation-name -> Hermes-session-ID mappings in `logs/hermes_sessions.json`. Voice and typed chat use the same conversation and therefore resume the same Hermes session.

The server consumes Hermes stream events including:

- run start / run ID
- assistant text deltas
- tool start + preview
- approval requests
- assistant completion / interruption
- run completion / token usage

STOP is wired to the active Hermes run where possible and also drops/cancels the local stream so the user gets immediate interruption behavior.

For Orion, the important pattern is **one shared agent session across modalities**, not Jarvis' specific persistence file.

## Browser/HUD protocol

Browser -> server messages include:

- start recording
- stop/send recording
- stop active run
- approval decision
- binary PCM audio chunks

Server -> browser messages include:

- connection/status
- partial transcript
- final transcript
- active run ID
- agent state (`thinking`, `tool_use`, `speaking`, `stopped`)
- approval request
- error/done timing
- binary TTS PCM
- summon/dismiss panel events

This event vocabulary is a useful starting point for Orion's UI state machine.

## HUD layout and interaction model

Jarvis uses a three-column command-center layout:

### Left rail

- Voice Link
- Agent Activity
- Turn Metrics
- Views
- Session

### Center

- animated arc-reactor canvas
- current state label
- approval cards
- chat/transcript feed
- typed message input
- holographic media stage
- large dashboard/kanban viewer

### Right rail

- Models Loadout
- Machines
- Skills
- Diagnostics
- Automations

The reactor supports state-specific speed/color/glow for standby, listening, thinking, tool use, speaking, and error.

This information hierarchy is strong. Orion should preserve the **idea** that interaction/session state lives on one side, runtime/system state on the other, and the assistant/workspace owns the center.

## Holographic media system

Jarvis' `hud_display` plugin is one of the best pieces of the project.

The plugin gives Hermes explicit first-class tools:

- `hud_display`
- `hud_dismiss`

The schema tells the model that ordinary browser tools are invisible to the user and that visible on-screen content must go through the HUD tool. This solved a practical model-routing problem that persona/SOUL prose alone did not solve reliably.

The tool POSTs a small structured payload to the local HUD server and the server broadcasts it to connected screens. The HUD then renders image/video/iframe content with animated placement.

**Orion should adopt this concept, but generalize it.**

Recommended future Orion display contract should support structured surfaces such as:

- media
- document
- chart
- map
- memory
- task
- comparison
- diagnostics
- generic workspace
- focus/pin/dismiss

The display tool should not itself grant authority to execute unrelated actions.

## Security model worth keeping

Jarvis keeps the Hermes API credential off the browser. The HUD talks to its local server, which proxies a restricted set of Hermes endpoints and injects the bearer credential server-side.

Other useful patterns:

- loopback Hermes API
- HUD token/cookie gate
- browser Origin checks
- dashboard proxy rather than exposing a raw Hermes key
- secret-shaped string redaction before cloud TTS
- LAN-only operating assumption

Orion should preserve the credential-isolation principle even if the exact proxy implementation changes.

## Machine and usage telemetry

Jarvis exposes:

- host CPU/memory
- remote worker health
- GPU/VRAM/temp through remote stats agent
- turns/tokens
- estimated LLM cost
- ElevenLabs character/quota usage
- Hermes health/sessions/agents
- loaded skills
- scheduled jobs

These are useful HUD concepts, but Orion should prioritize actionable status over permanent visual density.

## Practical implementation lessons encoded in Jarvis

The code and troubleshooting docs capture several useful operational lessons:

- force UTF-8 when consuming Hermes SSE where the response lacks a charset
- browser microphone access requires a secure context
- raw PCM/TTS chunks can split int16 samples at arbitrary byte boundaries
- near-silent Whisper input should be treated as empty transcription rather than a fatal turn
- Windows NVIDIA Python wheels may need explicit CUDA DLL directory handling
- background model warmup needs race protection
- streaming responses must always close
- child audio/STT processes can outlive naive parent-name process kills
- agent-facing UI behavior works better as a real explicit tool than as persona prose

These should inform Orion's implementation tests even when Orion does not reuse the same code.

## Problems / limitations found during review

### 1. Voice stack duplication risk

Jarvis owns STT, TTS, voice sessions, wake behavior, and barge-in because of the Hermes generation it targeted.

Orion's accepted Hermes v0.20.6 already provides native voice/wake/barge-in functionality. Reusing Jarvis' entire pipeline would create duplicate configuration, duplicated interruption semantics, more credentials, extra latency, and more lifecycle state.

Disposition: **do not port this wholesale. Validate Hermes-native voice first.**

### 2. Monolithic HUD

`server/hud/index.html` is roughly 45 KB and combines layout, styling, animation, auth, mic capture, WebSocket protocol, chat, telemetry polling, viewer, media panels, and boot effects in one file.

That is attractive for a no-build-step project but is not a good long-term base for Orion's planned memory/workspace/device features.

Disposition: **copy interaction ideas, build Orion modularly.**

### 3. macOS lifecycle assumptions

Jarvis ships launchd templates and macOS-specific service/port/TCC guidance. Orion has a separately accepted native-Windows manual-off lifecycle and must not inherit Jarvis auto-start behavior.

Disposition: **ignore launchd lifecycle implementation.**

### 4. Broadcast display semantics

`/api/summon` broadcasts to every connected HUD screen. That is convenient for one-room Jarvis but becomes wrong once Orion supports multiple devices/rooms.

Disposition: **add display identity/targeting before multi-device rollout.**

### 5. Remote worker stats defect

`worker/worker_stats.py` reads `os.environ` but, in the reviewed file, does not import `os`. A request to `/stats` can therefore raise `NameError` on that path.

This is a reference-code defect, not an Orion runtime defect. It is recorded here so the file is not copied uncritically.

### 6. Old version text/assumptions

HUD/footer/setup material references Hermes v0.16-era behavior. Current Hermes capabilities are materially broader.

Disposition: **treat every Jarvis API assumption as a discovery input, not an accepted Orion contract.**

## What Orion should reuse

| Jarvis idea | Orion disposition |
| --- | --- |
| Shared typed + voice agent session | Adopt concept |
| Live tool/activity stream | Adopt |
| STOP/cancel | Adopt |
| Approval cards | Adopt |
| Explicit HUD display tool | Adopt and generalize |
| Credential-isolating allowlisted proxy | Adopt principle |
| Holographic/adaptive panels | Adapt |
| System/machine telemetry | Adapt |
| Usage metrics | Adapt selectively |
| Browser secure-context handling | Adopt |
| Secret redaction before cloud TTS | Adopt if cloud TTS is used |
| Jarvis custom STT/TTS server | Avoid unless Hermes gap is proven |
| One-file HUD | Avoid |
| launchd auto-start | Avoid |
| broadcast to every HUD | Replace with targeting |
| Jarvis memory model | Replace with iai-native memory presentation |

## Orion-specific improvements beyond Jarvis

Orion can become more than a themed chat screen by making its center an adaptive workspace.

The central Orion Core can remain large in idle/listening states, then contract when the agent presents memory, research, documents, media, tasks, or diagnostics. The assistant therefore retains a visible presence without sacrificing the majority of screen real estate.

The iai memory layer should be first-class and transparent. Orion can surface:

- memory availability/health
- current context provenance
- stale/degraded state where supported
- recent or relevant memory cards
- explicit launch/open action for IAI Brain

Orion should not build a competing memory editor.

## Recommended next action

Begin Phase 2A with a read-only API/event compatibility map against the **accepted Hermes v0.20.6 pin**, especially typed sessions, run events, STOP, approvals, health, and native audio/wake endpoints. Only after that contract is documented should implementation choose which Jarvis code paths are worth porting.

Core Intent Preservation: **PRESERVED**.
