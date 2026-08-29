# ADR-0001 — s6 + CAP_KILL for COMPANION gateway lifecycle

Status: **SUPERSEDED / HISTORICAL**

Original decision date: 2026-08-22  
Superseded: 2026-08-29 by **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)** and the accepted native-Windows Phase 0 baseline.

> This ADR preserves valid evidence from the former Docker/s6 implementation. It is no longer a controlling Orion architecture decision. Current Hermes lifecycle acceptance uses the native Windows installation, named `companion` profile, and Windows Scheduled Task `Hermes_Gateway_companion`. Do not apply this ADR to the v2.6 runtime unless the project explicitly returns to the historical container architecture.

## Historical context

Orion previously ran Hermes in a hardened Docker container with `--cap-drop ALL` and a narrowly restored capability set. Hermes dynamically created per-profile s6 services under `/run/service` and ran gateway children as the unprivileged Hermes UID.

During that implementation, `hermes -p companion gateway stop` could successfully register a down request with s6 while leaving the UID-10000 COMPANION gateway child alive. Host-side owner-UID signaling proved operationally able to terminate that child, but that approach required Docker host/socket authority.

Installed-source alignment confirmed that the historical image contained the exact `v2026.8.18` Hermes `service_manager.py` and `container_boot.py` implementations used by the documented s6 lifecycle path.

## Historical evidence

A controlled disposable A/B test held all tested runtime conditions constant except `CAP_KILL`.

### Variant A — without CAP_KILL

- COMPANION start succeeded
- COMPANION gateway child ran under UID 10000
- COMPANION stop command returned success
- child remained alive
- s6 reported a requested-down state

### Variant B — with CAP_KILL

- COMPANION start succeeded
- COMPANION stop command returned success
- child terminated
- service reached a clean down state

Historical canonical acceptance additionally proved:

- PID 1 = `s6-svscan`
- Hermes service manager = `s6`
- PID 1 effective `CAP_KILL` = present
- DEFAULT remained up and retained the same gateway PID through COMPANION start/stop
- COMPANION completed a two-turn Discord conversation with same-session context recall
- COMPANION child was absent after stop
- durable end state DEFAULT `running`, COMPANION `stopped`

## Historical decision

For that Docker/s6 runtime only, Orion selected the Hermes s6 service-manager lifecycle and granted `CAP_KILL` to the container in addition to the previously accepted narrow capability set.

Historical accepted launcher SHA-256:

```text
c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b
```

The historical launcher used:

- `--cap-drop ALL`
- narrowly restored capabilities
- `no-new-privileges`
- bridge networking with no published host ports

## Historical alternatives considered

### Host-side owner-UID signal mediator

Operationally proven but not selected because it required Docker host/socket authority and therefore created a broader control boundary than the in-container s6 path.

### Leave CAP_KILL absent

Rejected because the controlled differential reproduced the failed cross-UID stop behavior without it.

## Current replacement

The accepted v2.6 Phase 0 runtime is native Windows:

- Hermes tag `v2026.8.27`
- package `0.20.6`
- commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- profile `companion`
- persistence task `Hermes_Gateway_companion`
- task run level Limited / least privilege
- authenticated loopback API `127.0.0.1:8642`
- local model `qwen3.5-hermes:9b`
- real Windows restart acceptance passed

The old Docker/s6 findings remain useful only for provenance, regression archaeology, or an explicitly authorized restoration of the legacy architecture.
