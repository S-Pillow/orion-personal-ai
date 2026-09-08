# Phase 1 Status

Status: **IN PROGRESS — MEMORY / HIBERNATION ACCEPTED; MANUAL-OFF CONFIG ACCEPTED; OR-LIFE-005 v2.7.4 CANDIDATE VALIDATED THROUGH GATE 2F**

Controlling baseline: **ORION — Master PRD v2.7**, approved 2026-09-08.

> Historical Docker/s6 evidence and earlier v2.6 execution notes remain useful provenance, but they are not controlling. Current work follows the native-Windows v2.7 manual-off architecture.

## Frozen dependency baseline

- Hermes tag `v2026.8.27`
- Hermes package `0.20.6`
- Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- Hermes named profile `companion`
- Hermes home `%LOCALAPPDATA%\hermes`
- COMPANION home `%LOCALAPPDATA%\hermes\profiles\companion`
- iai-pme `3.0.8`
- iai virtualenv `%LOCALAPPDATA%\hermes\profiles\companion\iai\venv`
- canonical iai store `%USERPROFILE%\.iai-mcp`
- model `qwen3.5-hermes:9b`
- Ollama `http://localhost:11434/v1`
- Hermes API `127.0.0.1:8642`

Do not run `hermes update` during Phase 1 closure without an explicit dependency-change decision.

## Governing lifecycle decision

Owner-selected default mode is **manual-off**:

- Windows boot/login must not automatically start Orion/Hermes.
- `Hermes_Gateway_companion` stays registered/enabled, but its LogonTrigger is disabled.
- `iai-mcp-daemon` stays registered/enabled for vendor on-demand wake, but its LogonTrigger is disabled.
- `Orion Host Idle Bridge` is absent.
- Ollama Startup shortcut is removed.
- Start Orion / Stop Orion are explicit operator actions.
- iai remains vendor-managed; Orion must not become a second lifecycle supervisor.

The reboot-off half of OR-LIFE-005 already passed under this policy.

## Accepted Phase 1 memory / iai work

### Native iai installation / crypto / embedder — PASS

- isolated Python 3.11.3 environment
- iai-pme 3.0.8
- crypto initialization passed
- native Rust `bge-small-en-v1.5`, 384 dimensions, AVX2 available
- canonical store `%USERPROFILE%\.iai-mcp`

### Windows daemon compatibility — PASS WITH NARROW UPSTREAM-COMPATIBLE FIXES

The accepted Windows path preserves iai as the daemon/store/lifecycle authority. No Orion-owned daemon supervisor was added.

### Hermes ↔ iai ambient capture/recall — PASS / ACCEPTED

- native Windows recall/capture adapters installed through Hermes hook path
- `wake_depth=standard`
- Hermes built-in persistent `MEMORY.md` / `USER.md` targets disabled for COMPANION
- real Discord capture accepted
- canonical-store semantic recall accepted
- fresh `/new` ambient recall accepted

Canonical marker:

`ORION_CAPTURE_FRESH_GATEWAY_20260829`

Intent-preservation status: **PRESERVED**.

### Hermes-managed iai MCP + OR-LIFE-008 — PASS / ACCEPTED

- bundled iai wrapper registered through Hermes
- all 14 tools discovered
- `idle_timeout_seconds=600`
- gateway-owned wrapper observed to recycle after idle timeout

No Orion supervisor introduced.

## HIBERNATION lifecycle acceptance — PASS

Accepted independent real-HIBERNATION Tests A and B:

- OR-LIFE-003a daemon-independent recall accepted with pinned vendor provenance `_source: "daemon-down-full"`
- OR-LIFE-003b HIBERNATION wake accepted
- measured wrapper-start -> authenticated daemon-ready latency: **5.887 s**
- iai Scheduled Task on-demand wake worked
- no `doctor --auto` fallback required
- no duplicate logical daemon state observed

OR-LIFE-007 owner disposition remains pending final Phase 1 closure. Current recommendation: **ACCEPT / no additional iai patch**.

Do not rerun accepted HIBERNATION cycles without contradictory evidence.

## OR-LIFE-005 manual-off progress

Accepted before the current launcher-candidate work:

- manual-off task configuration accepted
- Ollama login autostart removed
- pre-reboot Start/Stop ownership behavior accepted
- real Windows reboot-off state passed: Hermes off, Ollama off, wrapper absent, daemon absent, tasks preserved with LogonTriggers disabled

A subsequent old-launcher cold-start attempt caused severe transient system slowdown and left Hermes healthy while Ollama was down and no launcher session existed. No hard OOM event was found. Supported direct Hermes stop restored a clean-off state. The exact root cause remains unproven.

Earlier launcher revisions v2.7.1, v2.7.2, and v2.7.3 were rejected and must not be installed.

## v2.7.4 candidate status

Candidate: `Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip`

Static disposition: **ACCEPT FOR NATIVE WINDOWS VALIDATION / NOT YET DEPLOYMENT-ACCEPTED**.

### Gate 1 — PASS

- ZIP SHA-256 verified
- Windows PowerShell 5.1 parse PASS
- read-only installed-runtime discovery PASS
- actual Hermes Python resolved: `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe`
- actual pinned source root resolved: `%LOCALAPPDATA%\hermes\hermes-agent`
- Python 3.11.3 confirmed
- 27 offline safety tests PASS
- native Windows primitives PASS
- exact boot identifier available
- initial preflight dirtiness traced only to an untracked pre-#17157 backup file
- that backup was hash-verified and relocated outside the Hermes checkout
- Hermes checkout then clean at exact approved pin
- candidate preflight PASS

### Gate 2A — PASS

- real worker ready/go/result handshake PASS
- pinned vendor `gateway_windows` status binding PASS
- Hermes correctly reported absent
- local missing-task start/install veto PASS
- no runtime started

### Gate 2B — PASS

Controlled candidate cold Start from clean-off state:

- `ORION READY`
- Start exit 0
- Hermes healthy
- Ollama healthy
- candidate session present
- active operation absent
- LogonTriggers remained disabled
- Hermes source remained clean

### Gate 2C — PASS / TELEMETRY CORRECTION

Session ownership record validated:

- schema 4
- same boot true
- exact live Orion-owned Ollama identity present

The initial Gate 2B observer CSV was malformed because localized comma-formatted numbers were written unquoted. Therefore the apparent `264 MB free RAM` result is rejected as resource evidence.

Direct Gate 2C snapshot showed about 5.47 GB free RAM, pagefile usage 60 MB, and ample RTX 3070 VRAM.

### Gate 2D — PASS

First real model inference + Discord + ambient iai recall:

- Discord `/new` succeeded
- model loaded as `qwen3.5-hermes:9b`, context 65536
- Hermes recalled `ORION_CAPTURE_FRESH_GATEWAY_20260829`
- exact-string predicate was false only because Hermes returned explanatory text rather than marker-only output; recall itself succeeded
- corrected telemetry stayed healthy during first inference:
  - minimum free RAM ~4.55 GB
  - maximum pagefile usage 88 MB
  - maximum GPU used ~2.65 GiB
  - minimum GPU free ~5.36 GiB
- severe prior slowdown did not reproduce

The old incident remains unexplained; do not claim a proven root cause.

### Gate 2E — PASS

Candidate Stop on its own running session:

- `Owned Ollama: stopped`
- `ORION STOPPED; iai remains vendor-managed.`
- Hermes API off
- Ollama API off
- zero Ollama processes
- session absent
- active operation absent
- wrapper absent after 5 s
- tasks preserved; LogonTriggers disabled
- Hermes checkout clean

### Gate 2F — PASS

Independent-runtime ownership boundary:

- test launched an independent Ollama process
- existing vendor Scheduled Task launched Hermes independently
- candidate Start over healthy runtimes returned `ORION READY`
- candidate session recorded `ollamaOwnershipRecorded: false`
- candidate Stop stopped Hermes under explicit operator authority
- candidate did **not** stop the independent Ollama process
- exact independent PID/image/start-time identity remained unchanged
- test cleanup terminated only that exact test-owned Ollama process
- final state returned to clean-off

This directly validates the ownership boundary that earlier rejected launcher revisions did not adequately prove.

## Current machine stopping point

End-of-session state after Gate 2F is clean-off:

- Hermes API off
- Ollama API off
- Ollama process count 0
- candidate launcher session absent
- active operation absent
- Hermes source clean at approved pin

iai remains vendor-managed and may transition on its own lifecycle; Orion Stop intentionally does not force-kill it.

Checkpoint: `docs/phase1/or-life-005-v274-end-session-clean-off-2026-09-08.md`.

## Remaining Phase 1 work

v2.7.4 is **not installed, merged to main, or deployment-accepted**.

Next work:

1. complete selected remaining Gate 2 native fault/race/recovery coverage, preferably with isolated harnesses rather than destabilizing the accepted Hermes installation
2. Gate 3 installation/publication/workflow validation, including old-launcher transition and shortcut publication behavior
3. install only after Gate 3 acceptance
4. controlled post-install recovery Start/Stop
5. separate real logoff/logon manual-off durability test
6. Phase 1 Foundation Recovery Gate
7. owner OR-LIFE-007 disposition (recommend ACCEPT / no patch)
8. final Phase 1 closure

Only after those items pass should Phase 2 HUD work begin.

## Explicit non-goals / guardrails

Do not:

- run `hermes update`
- install rejected v2.7.1/v2.7.2/v2.7.3 launchers
- install v2.7.4 before remaining validation gates pass
- create an Orion lifecycle supervisor
- replace iai lifecycle or memory semantics
- patch iai only to rename `daemon-down-full`
- rerun accepted HIBERNATION tests without contradictory evidence
- use the old desktop Start/Stop shortcuts during v2.7.4 validation
- infer the old slowdown root cause without evidence
- begin HUD integration before Phase 1 closure

Core Intent Preservation: **PRESERVED**.
