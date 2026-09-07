# Phase 1 HIBERNATION Test B Parked-State Checkpoint

Date: 2026-09-07
Status: **READY FOR TEST B / SECOND INDEPENDENT HIBERNATION CYCLE**

Controlling baseline: ORION Master PRD v2.6, native-Windows Phase 1.

## Purpose

Preserve the exact second-cycle parked HIBERNATION state before consuming it with Test B.

This checkpoint is independent from accepted Test A. Test A already proved the Windows wake path from HIBERNATION + daemon absent to authenticated daemon readiness via the vendor iai MCP wrapper and Task Scheduler activation.

## Observed precondition

Exact observed state:

```text
Lifecycle: HIBERNATION
Daemon count: 0
Wrapper count: 0
wake.signal present: False
daemon.port present: False
daemon.token present: False
TEST B PARKED STATE: READY
```

## Acceptance significance

This proves a separate HIBERNATION cycle reached the required parked state with:

- persisted lifecycle state `HIBERNATION`
- no running iai daemon
- no running iai MCP wrapper
- no pending `wake.signal`
- no Windows `.daemon.port`
- no Windows `.daemon.token`

The state is therefore suitable for a separate lifecycle test without reusing or contaminating Test A's wake evidence.

## Test B boundary

Test B should use this parked state to verify the direct-store fallback requirement without first starting the MCP wrapper, because launching a fresh wrapper can wake the daemon and invalidate the daemon-absent precondition.

Required evidence target:

- execute the supported iai recall path while daemon is absent / lifecycle is HIBERNATION
- verify the query returns the correct known marker
- verify response provenance reports `_source: direct-store`
- confirm the read itself does not require a running daemon
- record post-read lifecycle/process state before any subsequent wake action

This checkpoint does not itself satisfy OR-LIFE-003a; it preserves the precondition for that test.

Intent-preservation status: **PRESERVED**. No Orion lifecycle supervisor, alternate store, or replacement retrieval path was introduced.
