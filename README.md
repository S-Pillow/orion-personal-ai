# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion for **native Windows 11**. The accepted foundation uses a pinned Hermes Agent runtime, the named `companion` profile, a local Ollama model, Discord, a loopback Hermes API, and native iai persistent memory.

## Controlling baseline

The controlling product requirements document remains **ORION — Master PRD v2.7**, approved 2026-09-08.

A **v2.8 HUD & Companion Interface** draft has been prepared for owner review, but it is not controlling until explicitly approved. Phase 2 planning may use it as a proposal; implementation decisions that would conflict with v2.7 remain blocked until resolved.

PRD v2.7 formalizes the owner-selected **manual-off** lifecycle model:

- Orion/Hermes do not start automatically at Windows login.
- Start Orion / Stop Orion are explicit operator actions.
- Hermes and iai Scheduled Tasks remain registered for vendor-supported behavior, but their LogonTriggers are disabled.
- Ollama login startup is disabled.
- iai remains its own lifecycle and persistent-memory authority.
- Orion must not add a parallel gateway, memory system, embedding/ranking stack, or lifecycle supervisor.

Historical Docker/s6/JARVIS implementation records remain useful provenance but are not the controlling native-Windows path.

## Current status

### Phase 0 — PASS / CLOSED

Accepted native baseline:

- Hermes tag `v2026.8.27`
- Hermes package `0.20.6`
- Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- profile `companion`
- COMPANION home `%LOCALAPPDATA%\hermes\profiles\companion`
- API `127.0.0.1:8642`
- model `qwen3.5-hermes:9b`
- Ollama provider `http://localhost:11434/v1`
- context `65536`
- Discord native gateway accepted

### Phase 1 — PASS / CLOSED

Phase 1 lifecycle and memory acceptance is complete. Closure was merged to `main` in PR #6 at merge commit:

`7c55493e0401f1003b3f0f2438e684a5fb144227`

Accepted Phase 1 results include:

- iai-pme `3.0.8` in a dedicated native Python 3.11.3 environment
- canonical store `%USERPROFILE%\.iai-mcp`
- native Rust `bge-small-en-v1.5` 384-dimension embedder
- supported Hermes recall/capture hooks adapted for Windows
- real ambient Discord capture into iai
- semantic recall from the canonical iai store
- `wake_depth=standard` for rendered session-start memory
- Hermes built-in persistent `MEMORY.md` / `USER.md` targets disabled for COMPANION
- fresh `/new` ambient recall accepted
- Hermes-managed iai MCP wrapper registered; all 14 tools discovered
- MCP idle recycling accepted at `idle_timeout_seconds=600`
- independent real-HIBERNATION Tests A/B accepted
- daemon-independent recall accepted with pinned provenance `_source: "daemon-down-full"`
- authenticated HIBERNATION wake accepted at **5.887 s** wrapper-start -> daemon-ready
- OR-LIFE-007 owner disposition: **ACCEPT / no further wake patch**
- manual-off task/startup configuration accepted
- v2.7.4 operator controls installed and accepted through restart and pure logoff/logon
- installed Start/Stop lifecycle accepted after both restart and logon
- exact process-ownership boundaries accepted
- corrupted-state, stale-process, interrupted-operation, and concurrent-operation safety gates accepted
- changed-boot recovery accepted after a Windows boot-identity defect was found and corrected

Final Phase 1 evidence:

- `docs/evidence/or-life-005-final-acceptance-2026-09-09.md`
- `docs/evidence/or-life-007-owner-disposition-2026-09-09.md`
- `evidence/or-life-005/recovery-gate-d-2026-09-09.md`

Current Phase 1 status record:

`docs/phase1/status.md`

## Accepted manual-off lifecycle

Default behavior is intentionally quiet:

- Windows boot/login -> Hermes off
- Ollama off
- iai wrapper absent unless vendor on-demand behavior needs it
- iai daemon not login-started
- `Hermes_Gateway_companion` remains registered with LogonTrigger disabled
- `iai-mcp-daemon` remains registered with LogonTrigger disabled
- `Orion Host Idle Bridge` absent
- Ollama Startup shortcut absent
- Start Orion / Stop Orion remain explicit owner actions

iai remains vendor-managed and is intentionally not force-killed by Orion Stop.

## Operator controls and recovery note

The accepted installed operator version is `2.7.4-candidate1`.

During final recovery acceptance, the original `win_process.boot_id()` implementation was proven unsuitable because `NtQuerySystemInformation(90)` returned an identifier that remained unchanged across a real Windows Restart. The accepted correction uses kernel `SystemTimeOfDayInformation` (class 3) `BootTime`. It was proven stable within a boot and different after Restart; supported recovery then archived the prior-boot journal without acting on old PIDs.

Source-controlled correction:

`scripts/operator/patches/or-life-recovery-boottime.patch`

**Do not reinstall an original unpatched v2.7.4 candidate package and assume recovery is accepted.** Any repackaged/rebuilt operator controls must include the accepted BootTime correction and pass the relevant recovery preflight.

## Phase 2 — HUD / Companion Interface

Phase 2 is now the active planning target. Current handoff:

`docs/phase2/status.md`

The owner wants a distinct Orion companion interface inspired by the useful parts of the Jarvis HUD while adding Orion-specific capabilities: an animated Orion Core/face, adaptive center workspace, iai Brain access, memory transparency, agent activity, STOP/approval controls, system telemetry, summonable content, and later voice/mobile capabilities.

Important research finding: the **already-accepted Hermes v0.20.6 pin includes native streaming voice, full-duplex barge-in, local wake-word support, and open-vocabulary wake phrases**. Phase 2 should therefore validate and reuse Hermes' native voice surfaces before carrying forward Jarvis' separate STT/TTS orchestration.

Reference study:

`docs/phase2/jarvis-reference-study-2026-09-09.md`

Research backlog and feature ideas:

`docs/phase2/research-ideas-2026-09-09.md`

## Dependency watch

A documentation-only upstream check was completed on 2026-09-09. No dependency was upgraded.

- Hermes latest stable: `v0.21.1` / tag `v2026.9.7`; Orion remains pinned to accepted `v0.20.6` pending isolated qualification.
- Ollama latest stable: `v0.33.3`; a `v0.34.0-rc3` prerelease also exists. The exact installed Ollama binary version should be captured in the next Phase 2 preflight before any update decision.
- iai latest stable: `v3.2.0`; Orion remains on accepted `3.0.8` pending isolated store/Windows compatibility qualification. v3.2.0 also ships IAI Brain 1.0.0 Windows installer assets, directly relevant to the planned **IAI Brain** HUD action.

Details:

`docs/phase2/dependency-watch-2026-09-09.md`

## Architecture guardrails

- **Hermes Agent** is the sole local agent/gateway runtime.
- **Ollama** is the current local model provider.
- **iai-pme** is the sole persistent memory authority for COMPANION.
- **Obsidian** remains the planned human-facing vault in later phases.
- No Orion lifecycle supervisor.
- No second memory semantics, embedding, ranking, or consolidation system.
- No parallel agent gateway/service.
- No Docker/WSL requirement for Orion.
- The HUD may present and control authorized surfaces, but it must not silently become a second lifecycle authority.
- Narrow upstream-compatible dependency patches are allowed only when necessary and must preserve the reason the selected architecture/dependency exists.

Core Intent Preservation Gate:

> Are we solving the requirement in a way that preserves the reason this architecture, dependency, behavior, or design was chosen in the first place?

A CONFLICT or UNCERTAIN result blocks implementation until resolved.

## Repository strategy

### `S-Pillow/orion-personal-ai`

Canonical Orion integration/control repository for the current architecture, acceptance evidence, reproducibility instructions, lifecycle controls, compatibility notes, and Orion-owned glue.

### `S-Pillow/iai-personal-memory-engine`

Compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine`. Narrow Windows compatibility fixes may be carried only when stock behavior cannot satisfy Orion while preserving iai semantics.

### `S-Pillow/jarvis_ai`

HUD/reference fork. It is now an active **reference implementation and selective code donor** for Phase 2 discovery, not the Orion product architecture. Orion should reuse proven patterns only where they do not duplicate capabilities already provided by the accepted Hermes/iai stack.

## Security and evidence rules

- Never commit Discord tokens, API keys, `.env` files, iai encryption keys, decrypted memory exports, private vault contents, or runtime data.
- Never print secret values into acceptance evidence; presence/length checks are sufficient.
- Distinguish installed-runtime observations from upstream source claims.
- Preserve checkpoints/backups before risky mutations.
- Do not treat historical Docker acceptance as native-Windows acceptance.
- Do not update Hermes, Ollama, or iai merely because a newer release exists; qualify dependency changes separately.
- Keep consequential actions behind explicit operator authority and visible approval boundaries.

## Resume point

Resume with **Phase 2 design/compatibility discovery**. Before implementation, review/approve or revise the v2.8 HUD PRD draft, record the installed Ollama version, and validate which Hermes v0.20.6 native voice/HUD-facing APIs can be reused without introducing a second voice or lifecycle stack.
