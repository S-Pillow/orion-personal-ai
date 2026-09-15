# P4-04 / P4-05 — Push-to-talk voice foundation

**Status:** ORION IMPLEMENTED / HERMES GATEWAY AUDIO GAP CONFIRMED / LIVE VALIDATION BLOCKED  
**Date:** 2026-09-15  
**Controlling PRD:** ORION Master PRD v2.8  
**Depends on:** accepted native Hermes `v2026.8.27` / `0.20.6` / `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

## Decision

The failed P4-03 custom `Hey Orion` v1/v2 models do not block the rest of Phase 4. Orion proceeds with **push-to-talk** as the interim activation method while wake remains disabled. No third custom wake-model run is authorized by this slice.

Hermes remains the speech authority. Orion does not add an STT engine, TTS engine, always-on microphone service, hotword service, second agent gateway, lifecycle supervisor, or second conversation authority.

## Pinned-Hermes capability finding

Source review against the **accepted Hermes commit**, not upstream `main`, found an important interface boundary:

- Hermes already contains the native STT/TTS implementations needed by Orion;
- the Hermes dashboard server exposes `POST /api/audio/transcribe` and `POST /api/audio/speak` and uses the existing Hermes transcription/TTS implementations;
- Orion's accepted bridge, however, talks to the authenticated Hermes **gateway API server on `127.0.0.1:8642`**;
- `gateway/platforms/api_server.py` at accepted commit `5fc308a...` does **not** register `/api/audio/*` routes;
- its `GET /v1/capabilities` response explicitly advertises `audio_api: false` and `realtime_voice: false`;
- current upstream source still keeps the dashboard audio routes separate, so a routine dependency upgrade is not an evidence-backed solution to this gap.

Therefore the original direct-relay assumption was rejected before live Windows testing. We will not run a second always-on Hermes dashboard server merely to obtain the audio routes, and we will not bypass Hermes with browser/provider speech APIs.

## Orion-side implementation

This slice adds a reversible Phase 4 wrapper instead of mutating the accepted Phase 2/3 bridge directly:

- `hud/orion_phase4_voice_bridge.py`
  - reuses `orion_hud_bridge` and its loopback-only target, server-side API credential, same-origin cookie guard, session/run allowlist, and manual-off lifecycle boundary;
  - adds only `/api/orion/voice/status`, `/api/orion/voice/transcribe`, and `/api/orion/voice/speak`;
  - checks authenticated `GET /v1/capabilities` and enables voice only when Hermes explicitly advertises `features.audio_api == true`;
  - with the accepted unpatched Hermes gateway, voice **fails closed** as `hermes_gateway_audio_api_unavailable` while typed fallback remains available;
  - never exposes Hermes or provider credentials to the browser;
  - caps browser audio request size at 6 MiB and TTS text at 4,000 characters;
  - does not start, stop, install, update, patch, or supervise Hermes, Ollama, iai, or any Windows task/service;
  - injects the Phase 4 voice module only when this wrapper is launched, so rollback is launching `orion_hud_bridge.py` again.

- `hud/static/phase4-voice.js`
  - adds Push to Talk and Speak Replies controls to the existing Conversation composer;
  - uses browser `MediaRecorder` only for microphone capture; recognition remains Hermes-owned;
  - imposes a 20-second recording safety cap;
  - sends a returned transcript through the existing composer, so typed and spoken input use the **same selected persisted Hermes session**;
  - queues visible assistant output for Hermes TTS as sentences become available;
  - Push to Talk stops current browser playback and invokes the existing HUD STOP control if a run is active;
  - Speak Replies OFF stops speech playback without cancelling the agent run;
  - wake is shown as OFF and is never silently enabled.

- `hud/tests/test_phase4_voice.py`
  - covers the gateway capability gate, same-origin enforcement, narrow STT/TTS allowlisting, server-side Hermes authorization, invalid-audio rejection, credential redaction, typed-fallback truthfulness, and absence of new shell/runtime authority.

## Required Hermes-side closure

Before live PTT validation, the accepted Hermes gateway needs a **narrow, reversible, source-controlled compatibility patch** that:

1. registers authenticated `POST /api/audio/transcribe` and `POST /api/audio/speak` on the existing gateway listener;
2. reuses Hermes' existing `transcribe_recording()` and `text_to_speech_tool()` implementations instead of creating new speech semantics;
3. respects the gateway's existing profile scope, API-key authentication, request limits, and multiplex routing;
4. changes only `features.audio_api` to `true` when those routes are actually present; `realtime_voice` remains `false` because this slice is bounded PTT, not a new realtime websocket implementation;
5. returns only transcript/audio result data, never resolved provider credentials;
6. is hash-pinned to the accepted Hermes source and independently testable/reversible.

This compatibility patch is the next implementation ticket. It is preferable to requiring a second always-running dashboard server because it preserves the accepted single authenticated gateway boundary.

## Truthful state model

- accepted Hermes today: `VOICE · OFF · HERMES_GATEWAY_AUDIO_API_UNAVAILABLE`
- after a qualified gateway patch, idle: `VOICE · PUSH TO TALK · WAKE OFF`
- recording: `VOICE · CONVERSATION · LISTENING · WAKE OFF`
- transcription: `VOICE · CONVERSATION · TRANSCRIBING · WAKE OFF`
- failure: `VOICE · OFF · <reason>` with typed chat still available

## What this can close after gateway + live validation

- **P4-04:** Push to Talk accepted as the interim activation mode; wake remains a separate future decision.
- **P4-05:** spoken input enters the same selected persisted Hermes session as typed HUD chat.
- a substantial portion of **P4-06:** Hermes-owned STT plus progressive Hermes TTS with typed fallback preserved.

## Live acceptance still required

After the gateway patch is qualified on native Windows/JLab:

1. browser microphone permission and recording work through the Phase 4 wrapper;
2. Hermes returns usable transcription through the configured COMPANION speech path;
3. the transcript appears as a user turn in the same selected Hermes session;
4. the normal streamed HUD reply stays visible while Hermes TTS speaks it;
5. Push to Talk interrupts playback and an active run cleanly;
6. Speak Replies OFF leaves typed behavior unchanged;
7. Hermes unavailable / microphone denied / STT failure / TTS failure degrade visibly without blocking typed chat.

P4-07 through P4-09 still need explicit acceptance evidence for privacy modes, bounded follow-up, and interruption semantics. A click-to-interrupt path does not by itself prove native acoustic barge-in or truthful interrupted-response semantics.

## Non-regression boundary

- wake remains disabled;
- no custom-model v3;
- no routine Hermes upgrade as a substitute for the demonstrated interface gap;
- no second always-running Hermes dashboard server;
- no browser access to `API_SERVER_KEY` or speech-provider credentials;
- no parallel STT/TTS implementation;
- no new always-on microphone process;
- no lifecycle authority added to Orion;
- iai memory authority unchanged;
- typed chat remains available regardless of voice state.
