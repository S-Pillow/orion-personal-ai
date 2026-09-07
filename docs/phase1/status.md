# Phase 1 Status

Status: **IN PROGRESS — MEMORY + OR-LIFE-008 + HIBERNATION TESTS A/B ACCEPTED / NEXT: OR-LIFE-007 + OR-LIFE-005**

Controlling baseline: **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**, approved 2026-08-29.

> Historical Docker/s6 Phase 1 evidence remains in Git history but is not controlling. This file records the native-Windows Phase 1.

## Frozen dependency baseline

- Hermes tag `v2026.8.27`
- Hermes package `0.20.6`
- Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- Hermes named profile `companion`
- iai-pme `3.0.8`
- iai virtualenv `%LOCALAPPDATA%\hermes\profiles\companion\iai\venv`
- canonical iai store `%USERPROFILE%\.iai-mcp`

Do not run `hermes update` during the Phase 0/1 pin freeze without an explicit dependency-change decision.

## Accepted Phase 1 work

### Native iai installation / crypto / embedder — PASS

- isolated Python 3.11 environment
- `pip check` clean
- iai CLI/MCP executables present
- crypto initialization passed
- Rust embedder passed
- model `bge-small-en-v1.5`
- dimensions `384`
- AVX2 available

### Windows daemon compatibility — PASS WITH NARROW UPSTREAM-COMPATIBLE FIXES

Stock iai 3.0.8 first failed on Windows because daemon startup referenced `signal.SIGHUP` without guarding platform support. The stock failure was preserved as baseline evidence before narrow compatibility work proceeded.

No Orion-owned lifecycle supervisor was added. iai remains the daemon/store/lifecycle authority.

### Hermes ↔ iai ambient memory integration — PASS / ACCEPTED

Native-Windows Python adapters are installed through the supported Hermes hook path:

- `agent-hooks\iai-mcp-hermes-recall.py`
- `agent-hooks\iai-mcp-hermes-capture.py`

A real Discord turn using marker `ORION_CAPTURE_FRESH_GATEWAY_20260829` proved live `on_session_end` capture into the canonical iai store.

Root causes found and resolved during acceptance:

1. Hermes gateway had started before hooks/config/approvals existed, so a supported `hermes -p companion gateway restart` was required before live acceptance.
2. iai 3.0.8 defaults `wake_depth=minimal`, which does not render prior-session memory text for this hook path. Orion now uses supported `wake_depth=standard`.
3. Hermes' separate file-backed `MEMORY.md` / `USER.md` memory targets are disabled for COMPANION:
   - `memory.memory_enabled=false`
   - `memory.user_profile_enabled=false`

A fresh Discord `/new` session then returned the exact marker without `session_search`, while the same marker had already been independently proven present in iai's standard session-start payload.

**Memory integration: ACCEPTED.**

Intent-preservation status: **PRESERVED**.

### Hermes-managed iai MCP registration — PASS

COMPANION registers the bundled iai stdio wrapper through Hermes using absolute native-Windows paths and the canonical store. Hermes discovery found 14 iai MCP tools.

### OR-LIFE-008 MCP idle recycling — PASS / ACCEPTED

Configured:

`mcp_servers.iai-mcp.idle_timeout_seconds = 600`

Runtime verification proved the gateway-owned iai MCP Node wrapper was recycled after the idle timeout without an Orion supervisor.

**OR-LIFE-008: ACCEPTED.**

Intent-preservation status: **PRESERVED**.

## Independent HIBERNATION lifecycle acceptance

Tests A and B used separate confirmed HIBERNATION cycles.

### Test A — authenticated Windows wake path — PASS / ACCEPTED

Pristine parked-state precondition:

```text
Lifecycle = HIBERNATION
Daemon = 0
Wrapper = 0
wake.signal = False
daemon.port = absent
daemon.token = absent
```

Fresh iai MCP wrapper start produced:

```text
MCP initialized: True
MCP initialize elapsed ms: 178
Authenticated daemon ready: True
Wrapper-start to authenticated daemon-ready ms: 5887
```

Post-test evidence:

- lifecycle moved `HIBERNATION -> WAKE`
- Windows Scheduled Task `iai-mcp-daemon` activated
- `.daemon.port` created
- `.daemon.token` created
- authenticated IPC status request succeeded
- `wake.signal` cleaned up
- daemon process pair was the normal Windows venv launcher -> base Python child, not duplicate logical daemons
- `.doctor-auto-last` timestamp predated the wake test by about two hours, so `doctor --auto` did not participate

**OR-LIFE-003b / HIBERNATION Test A: PASS / ACCEPTED.**

Measured wrapper-start -> authenticated daemon-ready latency: **5.887 seconds**.

### Test B — daemon-absent direct recall — PASS / ACCEPTED

Second independent parked-state precondition:

```text
Lifecycle = HIBERNATION
Daemon = 0
Wrapper = 0
wake.signal = False
daemon.port = absent
daemon.token = absent
```

Supported iai CLI recall of `ORION_CAPTURE_FRESH_GATEWAY_20260829` returned:

```text
Recall exit code: 0
JSON parse: True
Recall source: daemon-down-full
Hit count: 5
Marker found: True
```

Post-read state remained:

```text
Lifecycle = HIBERNATION
Daemon = 0
Wrapper = 0
wake.signal = False
daemon.port = absent
daemon.token = absent
Task restarted = False
```

The local test predicate initially expected `_source == "direct-store"` and therefore printed `NEEDS REVIEW`. Pinned iai 3.0.8 source and vendor tests explicitly use `_source == "daemon-down-full"` for the daemon-independent full structural recall path.

Decision: accept `daemon-down-full` as the canonical pinned-vendor provenance for OR-LIFE-003a. Do not patch iai merely to rename the provenance field.

**OR-LIFE-003a / HIBERNATION Test B: PASS / ACCEPTED.**

Intent-preservation status: **PRESERVED**.

Decision record: `docs/phase1/or-life-003a-provenance-decision-2026-09-07.md`.

## Current Phase 1 acceptance state

Accepted:

1. native iai installation
2. crypto initialization
3. native embedder
4. Windows daemon compatibility sufficient for Orion
5. Hermes capture-hook integration
6. canonical-store persistence
7. semantic recall
8. `wake_depth=standard` session-start context
9. fresh-session Discord ambient recall
10. Hermes built-in curated memory disabled for COMPANION
11. Hermes-managed iai MCP registration
12. OR-LIFE-008 idle wrapper recycling at 600 seconds
13. independent HIBERNATION Test A
14. OR-LIFE-003b authenticated wake path, 5.887 s
15. independent HIBERNATION Test B
16. OR-LIFE-003a daemon-independent recall using pinned provenance `daemon-down-full`

Still open:

1. **OR-LIFE-007** — make the Windows accept-vs-patch decision from the now-observed wake behavior
2. **OR-LIFE-005** — restart/logoff/logon lifecycle acceptance with no corruption
3. final Phase 1 closure/reproducibility record after those lifecycle gates pass

## OR-LIFE-007 evidence available for decision

Observed Windows behavior is now substantially better than the original source-only concern:

- confirmed real HIBERNATION state
- daemon fully absent
- fresh wrapper triggered Windows Scheduled Task activation
- authenticated daemon readiness reached in 5.887 seconds
- lifecycle transitioned to WAKE
- wake signal cleaned up
- no `doctor --auto` fallback was required
- no Orion lifecycle supervisor was required

The accept-vs-patch decision should therefore be based on this runtime evidence, not on the earlier assumption that Windows could not demand-wake an absent daemon.

## Next execution step

Proceed to **OR-LIFE-007** and record the accept-vs-patch disposition.

If the observed 5.887-second authenticated wake path is accepted as sufficient, do not add a new Windows wake patch. Preserve the current vendor-compatible Task Scheduler activation path.

Then execute **OR-LIFE-005** restart/logoff/logon lifecycle acceptance and verify:

- Hermes COMPANION returns after logon
- iai Scheduled Task state is healthy
- canonical store remains readable
- no store corruption or duplicate daemon state appears
- memory capture/recall remains functional after the lifecycle event

Only after OR-LIFE-007 and OR-LIFE-005 are accepted should native-Windows Phase 1 be closed and HUD work resume.

## Explicit non-goals

Do not:

- run `hermes update`
- create an Orion lifecycle supervisor
- patch iai only to rename `daemon-down-full`
- replace iai memory semantics or persistence
- treat SLEEP as HIBERNATION evidence
- rerun accepted HIBERNATION tests without contradictory evidence
- begin HUD integration before Phase 1 lifecycle closure
