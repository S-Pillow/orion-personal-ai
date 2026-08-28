# P4-02B1A — Autonomous Lifecycle Container Idle Discovery

**Status: ROOT CAUSE CONFIRMED / COMPATIBILITY DESIGN REQUIRED**

Date: 2026-08-28 UTC

## Scope

This note records the read-only investigation that followed the P4-02B1A manual Brain-control PASS when the production autonomous observer failed to see the expected native iai `WAKE -> DROWSY` transition.

No lifecycle thresholds were changed, no iai state files were edited, no wrapper was stopped, and no accepted runtime container was restarted during this discovery.

## Installed runtime facts

Accepted core container:

- `orion-iai-m5-c`
- accepted container ID remained `ea9fb7afbe6b394373390310a94bcacb21470388d1310a9305c7ef9e6a97b2d7`
- accepted container `StartedAt` remained `2026-08-26T08:49:00.989990394Z`

`docker top` proved the live iai daemon is running inside the accepted s6 container:

```text
iai lilli (iai_mcp.daemon) store=/opt/data/profiles/companion/.iai-mcp
```

The real COMPANION iai store/socket are:

```text
/opt/data/profiles/companion/.iai-mcp
/opt/data/profiles/companion/.iai-mcp/.daemon.sock
```

A correctly addressed CLI status request returned:

```text
ok: True
state: WAKE
version: 3.0.8
fsm_state: WAKE
scheduler_paused: False
```

The earlier unqualified `iai-mcp daemon status -> daemon not running` result was a probe-addressing false negative: `docker exec` inherited a root home while the daemon/socket belong to the COMPANION profile.

## Observer-addressing correction

The earlier v6A/v6B autonomous probes used a `Path.home()` fallback and therefore inspected `/root/.iai-mcp` for store-specific state. `/root/.iai-mcp` does not exist in the accepted runtime.

Consequences:

- store-specific v6A/v6B lifecycle/heartbeat/request observations are not valid production acceptance evidence;
- the manual v5 Brain-control smoke remains valid because it exercised the live BrainView/control path rather than the faulty read-only store fallback;
- the old v6Br1 observer must not be reused.

The old v6A OS-idle-source reading remains diagnostically useful because `IdleDetector` is platform/session based rather than store based: the container reported no OS idle source/value.

## Live wrapper evidence

The COMPANION wrapper heartbeat directory contains a live 3.0.8 heartbeat for the persistent MCP wrapper. Example observed payload:

```json
{"pid":6850,"uuid":"529b66f2-256a-4587-b121-ee9d157f1e97","started_at":"2026-08-27T09:04:06.903Z","last_refresh":"2026-08-28T00:11:40.712Z","wrapper_version":"3.0.8","schema_version":1}
```

The matching process is the shipped iai MCP wrapper:

```text
/usr/local/bin/node /opt/iai/venv/lib/python3.12/site-packages/iai_mcp/_wrapper/index.js
```

This heartbeat is expected upstream behavior, not an Orion defect by itself.

## Pinned iai 3.0.8 source findings

Pinned Orion fork commit:

`55a8c32ece1f2af32002b3e0e542bead7290bdf1`

Relevant source behavior:

1. `mcp-wrapper/src/lifecycle.ts`
   - wrapper heartbeat refresh interval is 30 seconds;
   - a live wrapper intentionally keeps its heartbeat fresh.

2. `src/iai_mcp/heartbeat_scanner.py`
   - heartbeat freshness threshold is 90 seconds;
   - one fresh heartbeat makes the scanner active.

3. `src/iai_mcp/daemon/__init__.py`
   - an active wrapper normally selects `wake_refresh`;
   - the nightly `IAI_MCP_WINDOW_DEEP_IDLE_MIN` path is explicitly designed to see past an open/fresh wrapper when real OS-level human-idle evidence exists;
   - default window-deep-idle threshold is 30 minutes;
   - if OS idle is unknown, that arm is unavailable.

4. `src/iai_mcp/idle_detector.py`
   - Linux OS idle comes from systemd-logind seat-attached interactive sessions;
   - headless/no-seat sessions are deliberately excluded;
   - when no matching Linux seat exists, the detector returns no OS idle source and lifecycle falls back to heartbeat-idle only.

5. The current fork `main` still has this same Linux idle-source model; no built-in container/Windows-host idle-provider seam was found.

## Root cause

Orion's production topology combines two individually valid behaviors that leave no usable autonomous-idle signal:

```text
persistent Hermes/iai MCP wrapper
        |
        +-- refreshes iai heartbeat every 30 s (expected)

Docker Linux container on Windows host
        |
        +-- no seat-attached systemd-logind session for the Windows user
        +-- iai OS idle source = unknown

iai lifecycle
        |
        +-- scanner_active = true
        +-- no OS deep-idle arm available
        +-- wake_refresh wins
        +-- lifecycle remains WAKE
```

The production lifecycle log is consistent with this diagnosis: the only observed state transitions on 2026-08-27 were the accepted manual Brain controls (`force_sleep_request`, `force_sleep_drowsy_to_sleep`, `force_wake_request`); no native autonomous idle transition was recorded.

## Intent-preserving compatibility direction

Do **not** solve this by:

- killing/stopping the persistent MCP wrapper;
- weakening iai's production idle thresholds;
- hand-editing lifecycle state;
- inventing an Orion sleep/consolidation state machine;
- exposing the Docker socket to Brain/dashboard code;
- mounting a host system D-Bus/logind socket from the Windows host.

The smallest intent-preserving design is an **external OS-idle evidence adapter** at iai's existing `IdleDetector` boundary:

- opt-in only through an explicit environment variable such as `IAI_MCP_EXTERNAL_IDLE_PATH`;
- read a small host-produced JSON observation containing `idle_sec`, `observed_at`, `source`, and schema version;
- accept only non-negative finite idle values with a timezone-aware fresh timestamp;
- stale, malformed, missing, or future-invalid evidence must fail closed as active/unknown, never as idle;
- when the option is absent, macOS/Linux/Windows behavior remains byte-for-byte semantically unchanged;
- feed the resulting seconds into iai's existing native `sleep_eligible`, window-deep-idle, DROWSY/SLEEP/HIBERNATION policy without changing any lifecycle threshold or transition rule.

On the Orion side, Windows can produce this evidence with `GetLastInputInfo` and atomically write it under the already mounted `C:\HermesAgent\data` -> `/opt/data` boundary. No new privileged mount, Docker socket, network listener, or memory database is required.

Proposed shared path:

```text
host:      C:\HermesAgent\data\orion-runtime\host-idle.json
container: /opt/data/orion-runtime/host-idle.json
```

Proposed daemon setting:

```text
IAI_MCP_EXTERNAL_IDLE_PATH=/opt/data/orion-runtime/host-idle.json
```

## Verification gates before production deployment

1. Patch lives in the maintained iai compatibility fork, not as an alternate Orion lifecycle implementation.
2. Unit tests prove valid/fresh, active, stale, missing, malformed, negative/non-finite, and future-timestamp behavior plus unchanged default Linux/logind behavior.
3. Windows bridge is host-only, read-only with respect to iai state, atomic-write, and contains no secrets/network operations.
4. Disposable/container test proves a fresh external idle observation is consumed through `IdleDetector` while a wrapper heartbeat remains fresh.
5. Production deployment preserves the native 300 s DROWSY threshold, 1800 s sleep-idle threshold, nightly window behavior, and native SLEEP-cycle/HIBERNATION semantics.
6. Final acceptance uses authoritative iai lifecycle/event evidence and then proves foreground activity returns the lifecycle to WAKE.

## Disposition

P4-02B1A remains **IN PROGRESS**.

Manual Brain controls are accepted. Autonomous lifecycle acceptance is blocked on this demonstrated container/host idle-signal integration mismatch, not on a dead daemon or a defective wrapper heartbeat.
