# Phase 4 documentation

This directory contains two kinds of Phase 4 records:

1. **Current PRD v2.8 Phase 4 work** for native Hermes voice + wake.
2. **Historical archive material** from the earlier Jarvis/HUD and container-era implementation direction.

## Current PRD v2.8 Phase 4

Current-phase records:

- `p4-03-native-hermes-wake-evaluation.md` — custom `Hey Orion` v1/v2 path evaluated and **NOT ACCEPTED** on the Windows/JLab/MME screen. No v3 is automatically authorized; wake remains disabled while strategy returns to owner review.
- `p4-04-push-to-talk-foundation.md` — **IMPLEMENTED / LIVE VALIDATION REQUIRED**. Push-to-talk is the interim activation path so the failed custom wake experiment does not block native Hermes voice integration. The slice reuses Hermes STT/TTS, the existing persisted HUD session, server-side credentials, and typed fallback.

The current Phase 4 gate is defined by ORION Master PRD v2.8: reuse the installed Hermes voice path, keep typed fallback, validate spoken streaming and interruption behavior, expose visible privacy modes, bound hands-free continuation, and preserve the preferred `Hey Orion` requirement as a separate wake-strategy decision. No separate STT/TTS/hotword service is introduced absent a demonstrated approved gap.

The immediate acceptance sequence is:

1. live-validate the P4-04/P4-05 push-to-talk path on native Windows with the JLab microphone;
2. prove spoken input lands in the same persisted Hermes session as typed HUD chat;
3. prove Hermes-owned TTS can speak the normal streamed HUD response without blocking typed fallback;
4. close truthful privacy-state, bounded follow-up, and interruption semantics before declaring Phase 4 complete;
5. keep wake disabled unless a separately accepted wake strategy is selected.

## Historical Phase 4 archive

> **SUPERSEDED / REFERENCE ONLY — 2026-08-29.** The older `p4-01*`, `p4-02*`, and related Phase 4 records in this directory document Jarvis/HUD and container-era work from the former implementation direction. They remain preserved so historical links, hashes, and evidence stay stable.

Do not treat those historical closures as current PRD v2.8 acceptance unless separately revalidated against the current native-Windows/Hermes architecture.
