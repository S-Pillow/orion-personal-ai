# Phase 2 Dependency Watch — 2026-09-09

Purpose: record current upstream releases without changing Orion's accepted runtime.

**This is a documentation-only check. No Hermes, Ollama, or iai update was performed.**

## Summary

| Dependency | Orion accepted/current record | Latest stable observed | Other current upstream note | Disposition |
| --- | --- | --- | --- | --- |
| Hermes Agent | `0.20.6`, tag `v2026.8.27`, commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` | `0.21.1`, tag `v2026.9.7` | large post-0.21.0 rollup | Stay pinned; qualify separately |
| Ollama | provider accepted; exact installed binary version not recorded in repo | `0.33.3` | `0.34.0-rc3` prerelease observed | Capture installed version first; no update yet |
| iai Personal Memory Engine | `3.0.8` | `3.2.0` | IAI Brain 1.0.0 Windows installer assets included | Evaluate on isolated store/snapshot; no live upgrade yet |

## Hermes Agent

Latest stable release observed from the official `NousResearch/hermes-agent` GitHub releases endpoint:

- release: **Hermes Agent v0.21.1**
- tag: `v2026.9.7`
- published: 2026-09-07
- release commit window described by upstream as a large rollup after v0.21.0

Upstream says this patch rollup includes codebase modularization, file-operation and startup performance work, provider/model updates, desktop session controls and browser annotations, MCP authorization improvements, cron/delivery fixes, and delegation reliability work.

The release notes explicitly say full curated notes for the window are planned for v0.22.0 rather than enumerating every change in v0.21.1.

### Orion impact

Orion's accepted pin is intentionally older:

- package `0.20.6`
- tag `v2026.8.27`
- commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

Phase 1 acceptance, iai hook behavior, manual-off lifecycle, and restart/recovery evidence were all established against that pin. Moving directly to 0.21.1 would invalidate too much accepted evidence to treat it as a routine patch update.

### Important Phase 2 discovery

The **accepted v0.20.6 tag itself** already documents native capabilities that overlap heavily with Jarvis' custom voice server:

- local faster-whisper STT
- streaming TTS
- full-duplex barge-in during model generation and playback
- interruption awareness in subsequent context
- voice stop phrases
- wake-word operation
- openWakeWord, sherpa, and Porcupine providers
- open-vocabulary custom wake phrases
- GUI/client capture modes
- profile-scoped voice configuration

Therefore Orion does **not** need Hermes 0.21.1 merely to begin Phase 2 voice/HUD work.

### Recommendation

Stay on 0.20.6 for initial Phase 2A/2B discovery. Open a separate dependency-qualification ticket later if a 0.21.x feature materially improves Orion. That qualification should compare API/event contracts, iai integrations, Windows lifecycle behavior, and Start/Stop assumptions before changing the pin.

## Ollama

Latest stable release observed from official `ollama/ollama` GitHub releases:

- stable: **v0.33.3**
- published: 2026-09-02; assets refreshed 2026-09-03

The release includes MLX/GGUF/model/runtime updates upstream.

A newer prerelease was also visible:

- **v0.34.0-rc3**
- prerelease: true
- published release series began 2026-09-05, with rc3 assets updated 2026-09-09

### Orion impact

The Orion repository records Ollama as the accepted local provider and records the model/context behavior, but it does **not currently record the exact installed Ollama binary version** from the Phase 1 machine.

That is a documentation gap, not evidence that the machine is outdated.

### Recommendation

The first Phase 2 preflight should record, read-only:

- `ollama --version`
- executable path
- model inventory relevant to Orion
- current `qwen3.5-hermes:9b` model identity/digest if available

Only then compare that installed version against 0.33.3. Do not move to a release candidate for Orion's baseline without a specific feature need and a separate qualification ticket.

## iai Personal Memory Engine

Latest stable release observed from official `CodeAbra/iai-personal-memory-engine` GitHub releases:

- **v3.2.0**
- published: 2026-09-08

Orion's Phase 1 accepted version is `iai-pme 3.0.8`.

### Relevant v3.2.0 changes

Upstream changelog highlights include:

- `iai import [path]` for cold-start import of Claude Code and Codex transcripts, with idempotent/resumable behavior and dry-run support
- directive list/remove commands
- explicit session-start `HEALTHY` versus `UNAVAILABLE` availability markers
- per-turn recall `DEGRADED (<reason>)` markers
- source watermark / stale-memory indicators
- new doctor checks for stop-hook failure markers and watermark-fence consistency
- canonical-source write-once protection for important source surfaces
- improved Obsidian import behavior
- multiple recall/runtime performance changes
- native storage-driver evolution for newly created stores

The release assets also include **IAI Brain 1.0.0** packages, including Windows:

- `IAI.Brain_1.0.0_x64-setup.exe`
- `IAI.Brain_1.0.0_x64_en-US.msi`

This is directly relevant to the planned Orion HUD **IAI Brain** button/workspace. Orion may be able to launch the supported Brain application rather than building a competing memory editor.

### Upgrade risk

The version jump from 3.0.8 to 3.2.0 is substantial and touches capture, directives, storage, recall, availability semantics, and security. Orion's canonical store and HIBERNATION behavior were accepted on 3.0.8.

Do not perform an in-place upgrade against the canonical store merely to obtain Brain or UI features.

### Recommendation

Open a separate iai 3.2 evaluation when desired:

1. snapshot/backup canonical store according to accepted procedures
2. use an isolated copy or disposable store first
3. test Windows install/daemon lifecycle
4. test Hermes hook compatibility
5. test existing ambient capture and `/new` recall
6. test HIBERNATION wake and daemon-down recall semantics
7. test IAI Brain Windows app against the isolated store
8. only then decide whether to migrate the production pin

## Update policy for Phase 2

The existence of a newer upstream version is **not authorization to update**.

Dependency changes should be consequence-scoped and evidence-driven:

- identify the feature or defect that justifies the change
- isolate the candidate
- preserve rollback artifacts
- verify the integration contracts Orion relies on
- re-run only the acceptance gates materially affected by the dependency change
- update the controlling baseline only after explicit acceptance

Current recommendation: **begin Phase 2 on the accepted Hermes/iai foundation, capture the missing Ollama version, and evaluate newer dependencies separately.**
