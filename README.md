# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion for **native Windows 11**. The accepted foundation uses a pinned Hermes Agent runtime, the named `companion` profile, a local Ollama model, Discord, a loopback Hermes API, native iai persistent memory, and an Orion-owned local HUD/presentation layer.

## Controlling baseline

The controlling product requirements document is **ORION — Master PRD v2.8**, approved 2026-09-10.

PRD v2.8 supersedes v2.7. It preserves the accepted native-Windows/manual-off foundation while defining Hermes as the runtime and preferred native voice/wake authority, iai as the persistent-memory authority, and Orion as the living visual control-and-presentation layer.

The accepted **manual-off** lifecycle model remains unchanged:

- Orion/Hermes do not start automatically at Windows login.
- Start Orion / Stop Orion are explicit operator actions.
- Hermes and iai Scheduled Tasks remain registered for vendor-supported behavior, but their LogonTriggers are disabled.
- Ollama login startup is disabled.
- iai remains its own lifecycle and persistent-memory authority.
- Orion must not add a parallel gateway, memory system, embedding/ranking stack, voice runtime, hotword service, or lifecycle supervisor without a separately approved demonstrated gap.

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

Phase 1 lifecycle and memory acceptance is complete. Closure was merged in PR #6 at:

`7c55493e0401f1003b3f0f2438e684a5fb144227`

Accepted Phase 1 results include:

- iai-pme `3.0.8`
- canonical store `%USERPROFILE%\.iai-mcp`
- supported Hermes recall/capture hooks on Windows
- real ambient Discord capture into iai
- semantic recall from the canonical iai store
- `wake_depth=standard`
- Hermes built-in persistent memory/user-profile targets disabled for COMPANION
- Hermes-managed iai MCP wrapper with accepted idle recycling at `idle_timeout_seconds=600`
- daemon-independent recall with `_source: "daemon-down-full"`
- authenticated HIBERNATION wake at **5.887 s** wrapper-start -> daemon-ready
- OR-LIFE-007 **ACCEPT / no further wake patch**
- manual-off Start/Stop controls accepted through restart and pure logoff/logon
- changed-boot recovery accepted with the BootTime identity correction

Final Phase 1 evidence includes:

- `docs/evidence/or-life-005-final-acceptance-2026-09-09.md`
- `docs/evidence/or-life-007-owner-disposition-2026-09-09.md`
- `evidence/or-life-005/recovery-gate-d-2026-09-09.md`
- `docs/phase1/status.md`

### Phase 2 — typed HUD compatibility/control slice accepted

The internal Phase 2A typed-control bridge slice was accepted and merged through PR #9. It established the loopback-only Orion HUD bridge, persistent COMPANION typed-session continuity, progressive streaming, STOP, browser credential isolation, profile-specific credential separation, Hermes-routed iai recall, truthful degraded-state presentation, and persisted-session transcript reload.

The accepted bridge remains a narrow presentation/control adapter. It does not own lifecycle, voice, memory semantics, model routing, or arbitrary Hermes proxy authority.

Current Phase 2 record:

`docs/phase2/status.md`

That status file is retained as the Phase 2 closure/handoff record; the repository resume point is no longer Phase 2 discovery.

### Phase 3 — visual companion foundation merged

The current `main` source now includes the major Orion visual/presentation foundation built after the Phase 2 typed bridge:

- PR #10 / P3-01 — deterministic Orion Core state + gaze foundation
- PR #11 / P3-02 — adaptive Conversation/System workspace foundation
- PR #12 / P3-03 — read-only Memory Lens + native iai Brain handoff
- PR #13 / P3-04 — provenance/origin + descriptive authority foundation
- PR #14 / P3-05A — composition convergence toward the approved Orion interface

The merged HUD keeps Conversation as the default workspace, makes the Orion Core a truthful state-driven presentation surface, retains native iai ownership for detailed memory administration, and preserves the server-side credential and manual-off boundaries.

Latest merged Phase 3 composition commit:

`ef1ae1156c32c4f5afdd0a6d6568577f1498eb6a`

### Phase 4 — native Hermes voice/wake evaluation active

PRD Phase 4 is now the active experimental workstream. Orion continues to use the accepted Hermes native voice/wake architecture; no separate Orion hotword service or duplicate STT/TTS stack has been authorized.

Current wake evaluation record:

`docs/phase4/p4-03-native-hermes-wake-evaluation.md`

Current evidence includes:

- real Windows/JLab/MME wake-path testing;
- openWakeWord selected as the trained fixed-phrase engine class for the custom `Hey Orion` experiment;
- a validated 54,000-file synthetic positive/adversarial corpus plus augmentation and precomputed negative-feature inputs;
- two substantive custom-model training iterations completed;
- a real `best_val_fp` feedback defect identified and corrected;
- v1 retained as a defective-run artifact rather than a legitimate alternative weight schedule;
- v2 established as the first measured feedback-driven run;
- v2 final recall `37.75%`, insufficient by itself to claim wake viability;
- the two-iteration custom-training budget exhausted; **no v3 is currently authorized**;
- v2 preserved immutably with model SHA-256 `990567d4a2320e540e9dbf93d66a126498d14c3275010899a027b23732428dcd`.

Neither v1 nor v2 is an accepted Orion wake model yet. The next gate is real JLab/MME comparison evidence, not additional training.

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

## Governing architecture

- **Hermes owns the agent runtime and preferred native voice/wake path.**
- **iai owns persistent memory.**
- **Orion owns the living visual companion, presentation, and authorized control surface.**
- **Obsidian remains the durable human-authored document vault.**
- **S-Pillow/jarvis_ai is a selective reference/code donor, not the Orion runtime architecture.**

Do not duplicate these authorities for convenience.

## Dependency posture

The last dedicated dependency-watch record was captured on 2026-09-09. It is historical evidence, not automatic authorization to upgrade anything.

Accepted pins remain:

- Hermes `v2026.8.27` / package `0.20.6`
- iai `3.0.8`
- installed Ollama observed during Phase 2A: `0.32.15`

Any newer Hermes, iai, Ollama, model, or presentation dependency is a **candidate** until separately qualified under PRD v2.8. Do not replace an accepted dependency merely because a newer release exists.

Dependency-watch record:

`docs/phase2/dependency-watch-2026-09-09.md`

## Architecture guardrails

- No Orion lifecycle supervisor.
- No second memory semantics, embedding, ranking, or consolidation system.
- No parallel agent gateway/service.
- No duplicate STT/TTS/wake orchestration when Hermes satisfies the requirement.
- No Docker/WSL requirement for the running Orion product. WSL may be used only as isolated development/training tooling when explicitly bounded.
- Browser assets never receive the Hermes API key.
- HUD/adapter listeners remain loopback-only during MVP.
- Authority/provenance/voice indicators describe observed state; they do not grant permission.
- Narrow dependency patches are allowed only when necessary, evidence-backed, source-controlled, reversible, and consistent with the Intent Preservation Check.

Core Intent Preservation Gate:

> Are we solving the requirement in a way that preserves the reason this architecture, dependency, behavior, or design was chosen in the first place?

A CONFLICT or UNCERTAIN result blocks implementation until resolved.

## Repository strategy

### `S-Pillow/orion-personal-ai`

Canonical Orion integration/control repository for the current architecture, HUD, Orion-owned glue, acceptance evidence, reproducibility instructions, lifecycle controls, and dependency qualification records.

### `S-Pillow/iai-personal-memory-engine`

Compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine`. Narrow Windows compatibility fixes may be carried only when stock behavior cannot satisfy Orion while preserving iai semantics.

### `S-Pillow/jarvis_ai`

Reference/code-donor fork. Reuse only proven patterns that still close a current Orion requirement without duplicating Hermes/iai functionality.

## Security and evidence rules

- Never commit Discord tokens, API keys, `.env` files, iai encryption keys, decrypted memory exports, private vault contents, runtime data, generated training corpora, or large model-training feature arrays.
- Never print secret values into acceptance evidence; presence/length checks are sufficient.
- Distinguish observed runtime evidence, source-confirmed behavior, documentation claims, and hypotheses.
- Preserve/hash consequential artifacts before evaluation or mutation.
- Do not treat historical Docker acceptance as native-Windows acceptance.
- Do not update Hermes, Ollama, or iai merely because a newer release exists; qualify dependency changes separately.
- Keep consequential actions behind explicit operator authority and visible approval boundaries.
- Keep GitHub documentation aligned at meaningful accepted checkpoints so the repository resume point does not drift behind actual work.

## Resume point

Resume with **PRD Phase 4 / P4-03 native Hermes wake evaluation**.

Immediate sequence:

1. verify the existing v1 artifact has immutable/hash-verified preservation equivalent to v2; do not retrain v1;
2. compare preserved v1 and v2 through the fixed Windows JLab/MME Hermes/openWakeWord path at sensitivity `0.5` and confirmation frames `3`;
3. use at least 40 genuinely counted intended `Hey Orion` attempts per model with identical setup and no per-model threshold tuning;
4. record hits, misses, duplicate/unintended fires, and material latency/runtime anomalies;
5. advance only a credibly viable model to the larger intended-wake and ambient false-wake gate;
6. if neither model is viable, record rejection and return wake strategy to owner review — do not automatically launch v3;
7. after the wake disposition is clear, continue the remaining PRD Phase 4 native voice requirements: shared typed/voice conversation continuity, spoken streaming, visible voice-privacy modes, bounded follow-up, and barge-in.

Preserve the accepted Hermes/iai/manual-off boundaries throughout.
