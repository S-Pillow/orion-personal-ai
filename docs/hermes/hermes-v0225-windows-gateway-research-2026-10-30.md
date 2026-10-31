# Hermes v0.22.5 Windows gateway qualification research — 2026-10-30

## Why this research was done

Repeated disposable gateway qualification attempts produced misleading failures before a real v0.22.5 runtime verdict was established. The goal of this review was to compare the harness assumptions with exact Hermes source, Hermes documentation, upstream issues, and community reports before another retry.

## Findings

### 1. `gateway.pid` is not a bare integer on the accepted installed baseline

Exact installed baseline commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` builds a JSON PID record with at least `pid`, `kind`, `argv`, `start_time`, and `hermes_home`. Its reader accepts that JSON format and only falls back to a plain integer for legacy files.

Therefore the earlier PowerShell diagnostic that reported the COMPANION `gateway.pid` as `NON_NUMERIC` was parsing a valid Hermes identity file with the wrong schema. That result is not evidence of a corrupt PID file.

### 2. Hermes itself does not use one signal as the complete liveness answer

The accepted installed source's `resolve_gateway_liveness()` uses a ladder:

1. PID file + runtime lock;
2. HTTP health probe when available;
3. runtime-status PID validated against the process table.

Probe errors degrade to the next rung. The qualification harness should follow the same principle instead of treating one Windows socket-table snapshot as authoritative.

### 3. API readiness should be HTTP-based

Hermes documents `GET /health` as the API-server liveness endpoint and `GET /health/detailed` as authenticated readiness. `API_SERVER_ENABLED`, `API_SERVER_HOST`, `API_SERVER_PORT`, and `API_SERVER_KEY` are first-class API-server configuration inputs.

For disposable qualification, startup readiness is therefore `GET /health == 200`, followed by authenticated `/v1/capabilities` and route-contract checks. Native socket enumeration is supplemental bind-address/process evidence, not the startup oracle.

### 4. `gateway.standalone: true` should run without `--force`

Exact v0.22.5 multi-profile documentation says a named profile with `gateway.standalone: true` runs its own gateway without `--force`. The exact CLI documents `gateway run --force` as an escape hatch that bypasses normal supervisor protection and can create a second dispatcher.

The standalone qualification path must use ordinary `gateway run`.

### 5. A scratch profile named `companion` collides with the real Windows service identity

Exact v0.22.5 derives service/Scheduled-Task identity from the requested profile home. A custom root shaped like `<scratch>/profiles/<name>` resolves to the profile name as its service suffix. Therefore a disposable `<scratch>/profiles/companion` resolves to the same `companion` suffix as the real `Hermes_Gateway_companion` Scheduled Task.

That makes `companion` the wrong scratch name for a minimal runtime launch on this Windows host: ordinary `gateway run` can legitimately see an installed supervisor for that service identity, while `--force` would merely bypass the collision and hide the problem.

The minimal gateway smoke now uses the unique named profile `orion_v0225_qual`, probes the exact v0.22.5-computed Windows task name before launch, and fails closed if a task with that name already exists. Actual COMPANION config/memory compatibility remains a separate later gate.

### 6. Hermes has known Windows/gateway states where process liveness and API readiness diverge

Upstream issue #91547 documented `gateway restart` races where the gateway process remains alive after the API server loses its bind race, leaving API clients offline. Windows confirmation showed `api_server` fatal while another gateway owned the listener. The issue was closed by a later fix, but its important operational lesson remains: a running gateway PID alone is not API readiness.

Other Windows reports (#123971, #124893, #143331) document stale/missing/mismatched PID and lock metadata around launcher/update paths. These reinforce that file/process identity and HTTP service readiness must be checked independently.

### 7. The latest operator diagnostic did not prove the production listeners were absent

The diagnostic first sampled `Get-NetTCPConnection` and later performed HTTP requests. It observed zero listeners at the earlier sample but then received HTTP 200 from Hermes 8642 and Orion HUD 8765. Those observations were not simultaneous, so the output is consistent with a timing race/recovery between sections or with a Windows enumeration limitation. It is not valid evidence that HTTP succeeded with no listener at the same instant.

The correct qualification approach is bounded HTTP polling for readiness and native `netstat -ano` only after readiness to record actual bind evidence.

## Harness corrections

The research-corrected runtime smoke:

- generates a minimal unique scratch named profile from nothing (`orion_v0225_qual`);
- copies no production config or credentials;
- sets `gateway.standalone: true`;
- proves the computed Windows Scheduled-Task identity does not collide with an installed task;
- launches ordinary `gateway run` without `--force`;
- disables bundled-skill seeding for this narrow contract test;
- keeps the disposable API key only in the child process environment;
- disables HTTP proxy use explicitly for loopback probes;
- polls public `GET /health` for startup readiness;
- verifies authenticated capabilities and P4-04A local validation routes;
- uses native Windows `netstat -ano` only to prove the isolated listener is loopback-bound and owned by the candidate process tree;
- compares production watched state and production 8642 HTTP availability before/after rather than requiring a production listener as a precondition;
- re-verifies exact candidate source status/hashes after cleanup.

Canonical researched implementation: `scripts/hermes_upgrade/v0225_isolated_gateway_contract_smoke_v5.py`.

## Current disposition

- No failed attempt so far establishes that exact v0.22.5 cannot start the isolated API gateway.
- Several failures were qualification-harness assumptions that did not match Hermes' documented/runtime contracts.
- Stock production cutover remains NO-GO because this host is eligible for multiplex auto-migration and that path intersects the open Orion/Chat risk already identified.
- Isolated standalone qualification remains GO using the researched v5 harness.
