# P4-04 / P4-05 — Push-to-talk voice foundation

**Status:** IMPLEMENTED / LIVE VALIDATION REQUIRED  
**Date:** 2026-09-15  
**Controlling PRD:** ORION Master PRD v2.8  
**Depends on:** accepted native Hermes `v2026.8.27` / `0.20.6` / `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

## Decision

The failed P4-03 custom `Hey Orion` v1/v2 models do not block the rest of Phase 4. Orion proceeds with **push-to-talk** as the interim activation method while wake remains disabled. No third custom wake-model run is authorized by this slice.

Hermes remains the speech authority. Orion does not add an STT engine, TTS engine, always-on microphone service, hotword service, voice gateway, lifecycle supervisor, or second conversation authority.

## Pinned-Hermes capability basis

The accepted Hermes release already provides the voice primitives this slice needs:

- `POST /api/audio/transcribe` accepts a base64 audio data URL and returns a transcript using Hermes' configured transcription provider and hallucination filtering;
- `POST /api/audio/speak` synthesizes text through Hermes' configured TTS provider and returns audio as a data URL;
- `GET /api/audio/voice-config` resolves the active profile's STT/TTS path;
- native Hermes voice behavior also defines silence handling, streaming TTS, continuous follow-up, stop phrases, and barge-in.

Orion therefore integrates with these supported primitives rather than duplicating them.

## Implementation

This slice adds a reversible Phase 4 wrapper instead of mutating the accepted Phase 2/3 bridge directly:

- `hud/orion_phase4_voice_bridge.py`
  - reuses `orion_hud_bridge` and its loopback-only target, server-side API credential, same-origin cookie guard, session/run allowlist, and manual-off lifecycle boundary;
  - adds only `/api/orion/voice/status`, `/api/orion/voice/transcribe`, and `/api/orion/voice/speak`;
  - never returns Hermes voice credentials to the browser; `GET /api/audio/voice-config` is redacted before presentation;
  - caps browser audio request size at 6 MiB and TTS chunks at 4,000 characters;
  - does not start, stop, install, update, patch, or supervise Hermes, Ollama, iai, or any Windows task/service;
  - injects the Phase 4 voice module only when this wrapper is launched, so reverting to the accepted bridge is simply launching `orion_hud_bridge.py` again.

- `hud/static/phase4-voice.js`
  - adds Push to Talk and Speak Replies controls to the existing Conversation composer;
  - uses browser `MediaRecorder` only for microphone capture; recognition is performed by Hermes;
  - imposes a 20-second recording safety cap;
  - sends the returned transcript through the existing composer, so typed and spoken input use the **same selected persisted Hermes session**;
  - speaks assistant output in sentence-sized chunks through Hermes TTS as text appears;
  - pressing Push to Talk stops current browser playback and invokes the existing HUD STOP control if a run is active;
  - wake is shown as OFF and is never silently enabled.

- `hud/static/phase4-voice.css`
  - contains only presentation styling for the Phase 4 controls/status line.

- `hud/tests/test_phase4_voice.py`
  - verifies credential redaction, same-origin enforcement, narrow STT/TTS allowlisting, server-side Hermes authorization, invalid-audio rejection, and absence of new shell/runtime authority.

## Truthful state model for this slice

- idle: `VOICE · PUSH TO TALK · WAKE OFF`
- microphone recording: `VOICE · CONVERSATION · LISTENING · WAKE OFF`
- after capture: `VOICE · CONVERSATION · TRANSCRIBING · WAKE OFF`
- unsupported/unavailable: `VOICE · OFF · <reason>`

The state describes observed client behavior. It does not grant permission or imply wake listening.

## What this closes if live validation passes

This slice is intended to close the implementation portion of:

- **P4-04:** owner wake-strategy disposition for the current phase — Push to Talk accepted as the interim activation mode; wake remains a separate future decision;
- **P4-05:** voice input enters the same selected Hermes session as typed HUD chat;
- a substantial portion of **P4-06:** Hermes-owned STT plus sentence-progressive Hermes TTS with typed fallback preserved.

## Still required before Phase 4 can close

Live Windows/JLab validation must prove:

1. browser microphone permission and recording work through the Phase 4 wrapper;
2. Hermes returns usable transcription through the configured COMPANION voice provider;
3. the spoken transcript appears as a user turn in the same selected Hermes session;
4. the assistant response remains visible as the normal streamed HUD response while Hermes TTS speaks it;
5. Push to Talk can interrupt browser speech and an active run without leaving the HUD stuck;
6. disabling Speak Replies leaves typed behavior unchanged;
7. Hermes unavailable / microphone denied / STT failure / TTS failure degrade visibly without blocking typed chat.

P4-07 through P4-09 still need explicit acceptance evidence for privacy modes, bounded follow-up, and interruption semantics. This wrapper intentionally does not claim that a click-to-interrupt automatically proves Hermes' native acoustic barge-in behavior or that a stopped partial reply is semantically annotated as interrupted.

## Local validation command

Run the same Python test discovery used by the HUD project, including the new Phase 4 test:

```powershell
python -m unittest discover -s hud\tests -p "test_*.py" -v
```

For live validation, launch the Phase 4 wrapper in place of the base HUD bridge using the same accepted loopback/Hermes arguments used for `orion_hud_bridge.py`.

## Non-regression boundary

- wake remains disabled;
- no custom-model v3;
- no Hermes source patch;
- no Hermes dependency upgrade;
- no browser access to `API_SERVER_KEY` or voice provider credentials;
- no parallel STT/TTS implementation;
- no new always-on microphone process;
- no lifecycle authority added to Orion;
- iai memory authority unchanged;
- typed chat remains available regardless of voice state.
