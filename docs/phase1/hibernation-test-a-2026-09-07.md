# OR-LIFE-003b HIBERNATION Test A — Accepted

Date: 2026-09-07
Status: **PASS / ACCEPTED**

Controlling baseline: ORION Master PRD v2.6, native-Windows Phase 1.

## Preconditions

The parked-state checkpoint was reached passively before the wake test:

- lifecycle: `HIBERNATION`
- daemon count: `0`
- iai MCP wrapper count: `0`
- `wake.signal`: absent
- `.daemon.port`: absent
- `.daemon.token`: absent

Observed parked-state time:

`2026-09-07T04:27:55.0814110-04:00`

## Wake test

A fresh iai MCP wrapper was launched directly from the accepted COMPANION iai environment.

Wrapper start:

`2026-09-07T04:49:40.348708-04:00`

Observed:

- fresh wrapper PID: `32520`
- MCP initialize: PASS
- MCP initialize elapsed: `178 ms`
- authenticated daemon readiness: PASS
- wrapper-start to authenticated daemon-ready: `5887 ms`
- wrapper remained alive through readiness probe

The readiness probe used iai's own Windows IPC helpers. It resolved the daemon port, connected over loopback, sent the vendor authentication token, submitted a real `status` request, and received a JSON response. This is stronger evidence than process existence alone.

## Windows wake activation evidence

Before wake:

- Scheduled Task `iai-mcp-daemon` last run: `2026-09-07 03:55:55` local

After wake:

- Scheduled Task `iai-mcp-daemon` last run: `2026-09-07 04:49:44` local
- task restart observed: `True`
- lifecycle after: `WAKE`
- `.daemon.port`: present
- `.daemon.token`: present
- `wake.signal`: absent after completion

This demonstrates the fresh wrapper triggered the Windows iai activation path and the daemon reached authenticated-ready state.

## Daemon process identity

The post-test process scan showed two Python process rows, but they form one normal Windows venv launcher chain rather than two independent daemon instances:

- PID `34100`: `%LOCALAPPDATA%\hermes\profiles\companion\iai\venv\Scripts\python.exe -m iai_mcp.daemon`
- child PID `21488`: `%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m iai_mcp.daemon`

The parent/child relationship confirms one logical iai daemon instance.

## doctor --auto fallback check

The `.doctor-auto-last` file currently has:

`LastWriteTimeUtc = 2026-09-07 06:49:48Z`

The wake harness began at:

`2026-09-07T04:49:40.348708-04:00 = 2026-09-07T08:49:40.348708Z`

Therefore the doctor damper timestamp predates the wake test by approximately two hours. No `doctor --auto` fallback ran during Test A.

## Acceptance verdict

**OR-LIFE-003b HIBERNATION Test A: PASS / ACCEPTED.**

Measured Windows wake latency:

`wrapper start -> authenticated daemon ready = 5.887 seconds`

Accepted transition:

`HIBERNATION + daemon absent -> fresh wrapper -> Windows iai Scheduled Task activation -> authenticated daemon ready -> lifecycle WAKE`

Intent-preservation status: **PRESERVED**.

The result uses iai's existing wrapper, Scheduled Task, daemon IPC authentication, and lifecycle state. No Orion lifecycle supervisor or parallel wake mechanism was introduced.

## Next boundary

Do not rerun Test A from the current WAKE state. Test B must begin from a separate independently observed HIBERNATION + daemon-absent cycle.
