# Phase 1 Status

Status: **PASS / CLOSED — NATIVE MEMORY + MANUAL-OFF LIFECYCLE ACCEPTED**

Controlling baseline: **ORION — Master PRD v2.7**, approved 2026-09-08.

Phase 1 closure was merged to `main` in PR #6 on 2026-09-09.

Merge commit:

`7c55493e0401f1003b3f0f2438e684a5fb144227`

> Historical Docker/s6 evidence and earlier v2.6 execution notes remain useful provenance, but they are not controlling. Phase 1 closed on the native-Windows v2.7 manual-off architecture.

## Frozen accepted dependency baseline

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
- Ollama base `http://localhost:11434/v1`
- Hermes API `127.0.0.1:8642`

These are acceptance pins, not claims that no newer upstream versions exist. Dependency upgrades require a separate qualification decision.

## Governing lifecycle decision — ACCEPTED

Owner-selected default mode is **manual-off**:

- Windows boot/login does not automatically start Orion/Hermes.
- `Hermes_Gateway_companion` stays registered but its LogonTrigger is disabled.
- `iai-mcp-daemon` stays registered for vendor on-demand behavior but its LogonTrigger is disabled.
- `Orion Host Idle Bridge` is absent.
- Ollama login Startup entry is absent.
- Start Orion / Stop Orion are explicit operator actions.
- iai remains vendor-managed; Orion does not become a second lifecycle supervisor.

This behavior survived both a real Windows Restart and a separate pure sign-out/sign-in cycle.

## Memory / iai acceptance — PASS

Accepted memory work:

- native iai installation, crypto initialization, and Rust embedder
- canonical store `%USERPROFILE%\.iai-mcp`
- Windows compatibility sufficient for Orion without replacing iai lifecycle semantics
- Hermes ↔ iai ambient capture/recall
- `wake_depth=standard`
- Hermes built-in persistent `MEMORY.md` / `USER.md` targets disabled for COMPANION
- fresh `/new` ambient recall
- Hermes-managed iai MCP wrapper; all 14 tools discovered
- OR-LIFE-008 MCP wrapper idle recycling at 600 seconds
- independent HIBERNATION Tests A/B
- OR-LIFE-003a daemon-independent recall with pinned provenance `_source: "daemon-down-full"`
- OR-LIFE-003b authenticated HIBERNATION wake at **5.887 s** wrapper-start -> daemon-ready

Canonical memory marker used during acceptance:

`ORION_CAPTURE_FRESH_GATEWAY_20260829`

Core Intent Preservation: **PRESERVED**.

## OR-LIFE-007 — CLOSED

Owner disposition:

**ACCEPT — no further wake patch.**

The observed 5.887-second vendor wake path is accepted for Phase 1. Future performance tuning remains possible but is not a Phase 1 blocker.

Evidence:

`docs/evidence/or-life-007-owner-disposition-2026-09-09.md`

## OR-LIFE-005 operator lifecycle — PASS

Accepted installed version:

`2.7.4-candidate1`

The complete validation sequence included:

- Gate 1 package/static/native preflight
- Gate 2A worker/vendor-status binding
- Gate 2B controlled cold Start
- Gate 2C ownership identity + telemetry correction
- Gate 2D first real model inference + Discord + ambient memory recall
- Gate 2E candidate Stop
- Gate 2F independent-runtime ownership boundary
- Gate 2G corrupted control-state fail-closed behavior
- Gate 2H stale process-identity safety
- Gate 2I interrupted-operation safety
- Gate 2J concurrent operation serialization
- Gate 3 installation/publication workflow validation
- legacy control archive/removal
- real post-restart manual-off validation
- real v2.7.4 installation
- installed Start/Stop validation
- real restart persistence + Start/Stop acceptance
- pure logoff/logon persistence + Start/Stop acceptance

Final OR-LIFE-005 evidence:

`docs/evidence/or-life-005-final-acceptance-2026-09-09.md`

## Changed-boot recovery — PASS WITH ACCEPTED CORRECTION

Final recovery validation exposed a defect in the original boot identity implementation: `NtQuerySystemInformation(90)` returned an identifier that did not change across a real Windows Restart on the acceptance machine, so recovery correctly failed closed but could not distinguish the prior boot.

Accepted correction:

- use kernel `SystemTimeOfDayInformation` (class 3) `BootTime`
- preserve the no wall-clock-minus-uptime design
- verify stable identity within one boot
- verify identity changes after a real Windows Restart
- use supported recovery to archive the previous-boot journal
- do not inspect or terminate prior-boot PID identities

The corrected identity changed from:

`134334129385000000`

to:

`134334145095000000`

after a real Windows Restart. Supported recovery then printed:

`Previous-boot records archived. No processes stopped.`

and returned to clean-off state.

Evidence:

`evidence/or-life-005/recovery-gate-d-2026-09-09.md`

Source-controlled correction:

`scripts/operator/patches/or-life-recovery-boottime.patch`

Operational note: do not treat an original unpatched v2.7.4 package as equivalent to the accepted installed state. Any future rebuild/repackage must include this correction.

## Final accepted machine policy

At Phase 1 closure:

- Hermes manual-off by default
- Ollama manual/off when Orion is stopped
- no Orion launcher session at rest
- no active lifecycle operation at rest
- Hermes and iai LogonTriggers disabled
- iai remains its own memory/lifecycle authority
- no Orion supervisor
- no parallel gateway
- no competing memory stack
- Hermes pin unchanged during acceptance

## Phase 1 closure result

**Phase 1 is closed. HUD/UI work may begin.**

The next phase must preserve the accepted lifecycle and memory boundaries. In particular, a HUD server or browser client may observe and interact with Hermes through authorized surfaces, but it must not silently become a second gateway, daemon supervisor, or memory authority.

## Next handoff

Phase 2 status:

`docs/phase2/status.md`

Jarvis reference study:

`docs/phase2/jarvis-reference-study-2026-09-09.md`

Dependency watch:

`docs/phase2/dependency-watch-2026-09-09.md`

Research ideas:

`docs/phase2/research-ideas-2026-09-09.md`
