# Phase 1 HIBERNATION Parked-State Checkpoint

Date: 2026-09-07
Status: **PRECONDITION REACHED / PRESERVED BEFORE WAKE TEST**

Controlling baseline: ORION Master PRD v2.6, native-Windows Phase 1.

## Purpose

Preserve the exact runtime checkpoint reached before any wake-path test mutates the state.

This is evidence for the HIBERNATION lifecycle acceptance work following accepted OR-LIFE-008 (`idle_timeout_seconds=600`). It is not by itself the final OR-LIFE-003b/OR-LIFE-007 wake acceptance.

## Passive monitor result

Observed local timestamp:

`2026-09-07T04:27:55.0814110-04:00`

Exact observed state:

```text
Lifecycle=HIBERNATION
Daemon=0
Wrapper=0
wake.signal=False
```

Expanded monitor output:

```text
04:27:55 | Lifecycle=HIBERNATION | Daemon=0 | Wrapper=0 | wake.signal=False

========================================
TARGET REACHED
========================================
Observed: 2026-09-07T04:27:55.0814110-04:00
Lifecycle: HIBERNATION
Daemon count: 0
MCP wrapper count: 0
wake.signal present: False
```

## Acceptance significance

This proves the system reached the required parked HIBERNATION precondition with:

- persisted lifecycle state `HIBERNATION`
- iai daemon absent
- Hermes/iai MCP wrapper absent
- no pre-existing `wake.signal`

The monitor was passive and COMPANION/Hermes was intentionally left stopped while waiting for this state.

## Next test boundary

The next action must intentionally leave this parked state and measure the Windows wake path from a fresh wrapper interaction. That test should record:

- wrapper-start timestamp
- whether `ensureDaemonAlive()` wakes/activates iai
- authenticated daemon-ready latency
- whether Task Scheduler activation occurs
- whether `doctor --auto` runs as fallback
- resulting lifecycle state
- whether `wake.signal` is cleaned up

Do not treat this checkpoint as final wake acceptance, and do not substitute SLEEP for HIBERNATION.

Intent-preservation status: **PRESERVED**. No Orion lifecycle supervisor or replacement memory/lifecycle system was introduced.
