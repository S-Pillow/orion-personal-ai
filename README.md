# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion for **native Windows 11**. The active architecture is centered on a pinned Hermes Agent runtime, named `companion` profile, local Ollama model, Discord, loopback Hermes API, and native iai persistent memory.

## Controlling baseline

The controlling product requirements document is **ORION — Master PRD v2.7**, approved 2026-09-08.

PRD v2.7 supersedes v2.6 and formalizes the owner-selected **manual-off** lifecycle model:

- Orion/Hermes do not start automatically at Windows login.
- Start Orion / Stop Orion are explicit operator actions.
- Hermes and iai Scheduled Tasks remain registered for vendor-supported behavior, but their LogonTriggers are disabled.
- Ollama login startup is disabled.
- iai remains its own lifecycle and persistent-memory authority.
- Orion must not add a parallel gateway, memory system, embedding/ranking stack, or lifecycle supervisor.

Historical Docker/s6/JARVIS implementation records remain useful provenance but are not the controlling MVP path.

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

Do **not** run `hermes update` during Phase 1 closure.

### Phase 1 — IN PROGRESS

Accepted memory/lifecycle work includes:

- iai-pme `3.0.8` in dedicated native Python 3.11.3 environment
- canonical store `%USERPROFILE%\.iai-mcp`
- native Rust `bge-small-en-v1.5` 384-dimension embedder
- supported Hermes recall/capture hooks adapted for Windows
- real ambient Discord capture into iai
- semantic recall from canonical iai store
- `wake_depth=standard` for rendered session-start memory
- Hermes built-in persistent `MEMORY.md` / `USER.md` targets disabled for COMPANION
- fresh `/new` ambient recall accepted
- Hermes-managed iai MCP wrapper registered; all 14 tools discovered
- MCP idle recycling accepted at `idle_timeout_seconds=600`
- independent real-HIBERNATION Tests A/B accepted
- daemon-independent recall accepted with pinned provenance `_source: "daemon-down-full"`
- authenticated HIBERNATION wake accepted at **5.887 s** wrapper-start -> daemon-ready
- manual-off task/startup configuration accepted
- real reboot-off state accepted

OR-LIFE-007 owner disposition remains pending final Phase 1 closure; current recommendation is **ACCEPT the 5.887 s vendor wake path with no additional iai patch**.

## Manual-off lifecycle

Current intended default behavior:

- Windows boot/login -> Hermes off
- Ollama off
- iai wrapper absent
- iai daemon not login-started
- `Hermes_Gateway_companion` remains registered/enabled with LogonTrigger disabled
- `iai-mcp-daemon` remains registered/enabled with LogonTrigger disabled so iai can still use its vendor on-demand wake mechanism
- `Orion Host Idle Bridge` absent
- Ollama Startup shortcut removed

This preserves vendor lifecycle semantics while allowing the owner to run Orion only when wanted.

## OR-LIFE-005 / Start-Stop hardening

An older launcher cold-start attempt after reboot caused severe transient Windows slowdown and left an inconsistent state: Hermes healthy, Ollama down, and no launcher session record. No hard OOM event was found, and the exact root cause remains unproven.

Launcher revisions v2.7.1, v2.7.2, and v2.7.3 were rejected after review and must not be installed.

### v2.7.4 candidate

Current validation candidate:

`Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip`

Validation branch:

`feature/orion-start-v272-lifecycle-safety`

Static disposition:

**ACCEPT FOR NATIVE WINDOWS VALIDATION / NOT YET DEPLOYMENT-ACCEPTED**

Native validation completed through **Gate 2F**:

- Gate 1A: Windows PowerShell 5.1 parse PASS
- Gate 1B: read-only installed-runtime discovery PASS
- Gate 1C: exact Hermes/Ollama runtime provenance resolved
- Gate 1D: Python 3.11.3, 27 offline tests PASS, native Windows process/lock primitives PASS, exact-pin clean preflight PASS
- Gate 2A: real worker handshake + pinned vendor status binding PASS; missing-task start/install veto PASS
- Gate 2B: controlled cold candidate Start PASS
- Gate 2C: same-boot exact Ollama ownership record PASS; resource observer issue identified and corrected
- Gate 2D: first real model inference + Discord `/new` + ambient iai recall PASS
- Gate 2E: candidate Stop PASS; Orion-owned Ollama stopped cleanly
- Gate 2F: independent-runtime ownership PASS; independent Ollama was neither claimed nor stopped by Orion

Corrected first-inference telemetry showed approximately:

- minimum free RAM: **4.55 GB**
- maximum pagefile usage: **88 MB**
- maximum GPU memory used: **2.65 GiB**
- minimum GPU memory free: **5.36 GiB**

The prior severe slowdown did **not** reproduce under the controlled v2.7.4 start + first-inference path. This is useful evidence, but it does not prove the earlier incident's root cause.

### Current safe stopping point

After Gate 2F, the machine returned to clean-off state:

- Hermes API off
- Ollama API off
- Ollama process count 0
- candidate launcher session absent
- candidate active operation absent
- Hermes checkout clean at the approved pin

iai remains vendor-managed and is intentionally not force-stopped by Orion Stop.

Detailed stopping-point record:

`docs/phase1/or-life-005-v274-end-session-clean-off-2026-09-08.md`

Current Phase 1 status:

`docs/phase1/status.md`

## Remaining Phase 1 work

The v2.7.4 candidate is **not installed, merged to main, or deployment-accepted**. Main contains documentation of validation status only; candidate implementation remains on the validation branch/package.

Resume with:

1. selected remaining Gate 2 native fault/race/recovery coverage, preferably using isolated harnesses rather than destabilizing the accepted Hermes installation
2. Gate 3 installation/publication/workflow validation
3. one-time old-launcher transition and candidate installation only after Gate 3 acceptance
4. controlled post-install recovery Start/Stop
5. separate real logoff/logon manual-off durability test
6. Phase 1 Foundation Recovery Gate
7. OR-LIFE-007 owner disposition
8. final Phase 1 closure

Only after Phase 1 closes should Phase 2 HUD work begin.

## Architecture guardrails

- **Hermes Agent** is the sole local agent/gateway runtime.
- **Ollama** is the current local model provider.
- **iai-pme 3.0.8** is the sole persistent memory authority for COMPANION.
- **Obsidian** remains the planned human-facing vault in later phases.
- No Orion lifecycle supervisor.
- No second memory semantics, embedding, ranking, or consolidation system.
- No parallel gateway/service.
- No Docker/WSL requirement for Orion.
- Narrow upstream-compatible dependency patches are allowed only when necessary and must preserve the reason the chosen architecture/dependency exists.

Core Intent Preservation Gate:

> Are we solving the requirement in a way that preserves the reason this architecture, dependency, behavior, or design was chosen in the first place?

A CONFLICT or UNCERTAIN result blocks implementation until resolved.

## Repository strategy

### `S-Pillow/orion-personal-ai`

Canonical Orion integration/control repository for current architecture, acceptance evidence, reproducibility instructions, lifecycle controls, compatibility notes, and Orion-owned glue.

### `S-Pillow/iai-personal-memory-engine`

Compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine`. Narrow Windows compatibility fixes may be carried only when stock behavior cannot satisfy Orion while preserving iai semantics.

### `S-Pillow/jarvis_ai`

Historical and possible future HUD source. It is not the active phase; HUD work resumes only after native Phase 1 closure.

## Security and evidence rules

- Never commit Discord tokens, API keys, `.env` files, iai encryption keys, decrypted memory exports, private vault contents, or runtime data.
- Never print secret values into acceptance evidence; presence/length checks are sufficient.
- Distinguish installed-runtime observations from upstream source claims.
- Preserve checkpoints/backups before risky mutations.
- Do not treat historical Docker acceptance as native-Windows acceptance.
- Do not install rejected launcher revisions.
- Do not install v2.7.4 until its remaining validation gates pass.

## Resume point

Resume from the **remaining v2.7.4 Gate 2 fault/recovery coverage**, with the machine already in clean-off state. Do not rerun accepted HIBERNATION cycles or Gates 1 / 2A–2F without contradictory evidence.
