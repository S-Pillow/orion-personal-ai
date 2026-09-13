# Phase 4 documentation

This directory contains two kinds of Phase 4 records:

1. **Current PRD v2.8 Phase 4 work** for native Hermes voice + wake.
2. **Historical archive material** from the earlier Jarvis/HUD and container-era implementation direction.

## Current PRD v2.8 Phase 4

Active current-phase record:

- `p4-03-native-hermes-wake-evaluation.md` — IN PROGRESS. Native Hermes wake-engine evaluation and custom `Hey Orion` openWakeWord model work under OR-VOICE-006.

The current Phase 4 gate is defined by ORION Master PRD v2.8: reuse the installed Hermes voice path, keep typed fallback, validate streaming speech and full-duplex barge-in, expose visible privacy modes, bound hands-free continuation, and implement the preferred `Hey Orion` phrase through a supported local Hermes wake engine. No separate STT/TTS/hotword service is introduced absent a demonstrated approved gap.

## Historical Phase 4 archive

> **SUPERSEDED / REFERENCE ONLY — 2026-08-29.** The older `p4-01*`, `p4-02*`, and related Phase 4 records in this directory document Jarvis/HUD and container-era work from the former implementation direction. They remain preserved so historical links, hashes, and evidence stay stable.

Do not treat those historical closures as current PRD v2.8 acceptance unless separately revalidated against the current native-Windows/Hermes architecture.
