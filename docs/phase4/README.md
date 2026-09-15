# Phase 4 documentation

This directory contains two kinds of Phase 4 records:

1. **Current PRD v2.8 Phase 4 work** for native Hermes voice + wake.
2. **Historical archive material** from the earlier Jarvis/HUD and container-era implementation direction.

## Current PRD v2.8 Phase 4

Current-phase records:

- `p4-03-native-hermes-wake-evaluation.md` — custom `Hey Orion` v1/v2 path evaluated and **NOT ACCEPTED** on the Windows/JLab/MME screen. No v3 is automatically authorized; wake remains disabled.
- `p4-04-push-to-talk-foundation.md` — Orion-side PTT foundation implemented, but **live validation is blocked by a confirmed Hermes gateway audio-API gap** at the accepted pin. The Orion wrapper fails closed on `features.audio_api != true`, preserves typed fallback, and does not attempt dashboard-only routes.

The current Phase 4 gate is defined by ORION Master PRD v2.8: reuse the installed Hermes voice path, keep typed fallback, validate spoken streaming and interruption behavior, expose visible privacy modes, bound hands-free continuation, and preserve the preferred `Hey Orion` requirement as a separate wake-strategy decision. No parallel STT/TTS/hotword service is introduced absent a demonstrated approved gap.

Immediate sequence:

1. implement and qualify a narrow source-controlled Hermes gateway compatibility patch exposing authenticated `POST /api/audio/transcribe` and `POST /api/audio/speak` through the existing 8642 gateway and advertising `audio_api: true` only when present;
2. live-validate PTT on native Windows/JLab;
3. prove spoken input lands in the same persisted Hermes session as typed HUD chat;
4. prove Hermes-owned TTS speaks the normal streamed HUD response without blocking typed fallback;
5. close truthful privacy-state, bounded follow-up, and interruption semantics before declaring Phase 4 complete;
6. keep wake disabled unless a separately accepted wake strategy is selected.

## Historical Phase 4 archive

> **SUPERSEDED / REFERENCE ONLY — 2026-08-29.** The older `p4-01*`, `p4-02*`, and related Phase 4 records in this directory document Jarvis/HUD and container-era work from the former implementation direction. They remain preserved so historical links, hashes, and evidence stay stable.

Do not treat those historical closures as current PRD v2.8 acceptance unless separately revalidated against the current native-Windows/Hermes architecture.
