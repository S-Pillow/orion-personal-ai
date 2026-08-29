# Hermes Container Supervision — Historical Installed Runtime Evidence

> **SUPERSEDED AS CONTROLLING ARCHITECTURE (2026-08-29).** This document preserves evidence from the earlier Docker/s6 Orion implementation. The controlling Orion baseline is now the native-Windows architecture defined by **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**. Current Hermes acceptance uses the native Windows installation at `%LOCALAPPDATA%\hermes`, named profile `companion`, and Windows Scheduled Task `Hermes_Gateway_companion`. Nothing in this historical note should be treated as current v2.6 acceptance unless separately revalidated.

## Current native replacement

The accepted Phase 0 native baseline is:

- Hermes tag `v2026.8.27`
- package `0.20.6`
- commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- profile `companion`
- persistence `Hermes_Gateway_companion`
- Windows task run level Limited / least privilege
- authenticated loopback API on `127.0.0.1:8642`
- local model `qwen3.5-hermes:9b` through Ollama
- runtime context `65536`
- real Windows restart acceptance passed
- post-restart API inference passed
- post-restart Discord round-trip passed

The legacy Docker COMPANION container was stopped during the native Discord cutover and its restart policy was set to `no`; legacy runtime data was not intentionally deleted.

Everything below this line is retained as **historical evidence only**.

---

This note records installed-runtime observations for the former Orion Hermes image and distinguishes installed evidence from upstream/tagged-repository context.

## Historical accepted installed topology

Observed canonical runtime characteristics under the previous architecture:

- PID 1 is `s6-svscan`
- supervision is rooted under `/run/service`
- s6-linux-init infrastructure is present
- `/run/s6/basedir` is present
- s6-rc infrastructure is present in the runtime
- some static/container services resolve into `/run/s6-rc/servicedirs`
- dynamically created per-profile gateway services are materialized directly as ordinary directories under `/run/service`
- Hermes runtime service-manager detection returns `s6`

A calibrated installed-runtime description was:

> The former Orion Hermes runtime used s6-linux-init/s6 supervision with a `/run/service` supervision tree. s6-rc infrastructure was present for container services, while Hermes dynamically materialized per-profile gateway service directories directly under `/run/service` and managed them through its installed s6 service-manager path.

## Historical installed source alignment

Read-only source alignment established that the installed modules were the exact tagged `v2026.8.18` implementations examined during the earlier Phase 1:

- `/opt/hermes/hermes_cli/service_manager.py`
- `/opt/hermes/hermes_cli/container_boot.py`

The earlier scoped-discovery statement that `container_boot.py` was absent from the installed image was retired; the file was present under `/opt/hermes/hermes_cli/` and had simply not been located by the earlier path-limited inspection.

## Historical per-profile gateway materialization

In a disposable `--network none` runtime, creating the COMPANION profile caused `/run/service/gateway-companion` to appear immediately.

The generated service included the expected s6 service artifacts, a `down` marker, and a real `run` script that activated the Hermes virtual environment and executed the COMPANION gateway under the Hermes UID. Initial service status was:

```text
down (not started yet)
```

This proved that Hermes dynamically created the per-profile supervision slot before the gateway was started in the container architecture.

## Historical cross-UID stop requirement

The former Orion container hardening used `--cap-drop ALL` and selectively restored required capabilities. The earlier Phase 1 isolated one additional lifecycle requirement: `CAP_KILL`.

The relevant ownership relationship was:

```text
root s6-supervise
        |
        v
UID 10000 Hermes gateway child
```

A controlled disposable A/B lifecycle test differed only by `CAP_KILL`:

- without `CAP_KILL`, `hermes -p companion gateway stop` returned success but the Hermes-owned child remained alive and s6 remained in a requested-down state
- with `CAP_KILL`, the same stop cleanly terminated the child and left the service down

This provided causal support for `CAP_KILL` as the required capability for the in-container s6 supervisor to terminate the differently owned gateway child.

## Historical accepted lifecycle mechanism

The former Phase 1 lifecycle design was:

> **Hermes s6 service manager + in-container s6 supervision + `CAP_KILL`.**

The historical launcher retained `--cap-drop ALL`, the prior narrow capability set, `no-new-privileges`, and added `KILL` specifically to satisfy the proven s6 cross-UID signal requirement.

Historical accepted launcher SHA-256:

```text
c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b
```

## Historical acceptance

The former architecture proved:

- DEFAULT supervised up before COMPANION start
- COMPANION supervised down before start
- exactly one COMPANION start succeeded
- COMPANION remained supervised and responsive through a two-turn Discord conversation
- exactly one COMPANION stop succeeded
- COMPANION gateway child was absent after stop
- DEFAULT retained the same gateway PID before, during, and after the COMPANION lifecycle
- PID 1 remained `s6-svscan`
- durable end state was DEFAULT `running`, COMPANION `stopped`

These facts remain historically valid but no longer define the current Orion runtime.

## Historical host-side owner-UID signaling

Host-side `docker exec -u hermes ... kill <pid>` was previously proven operationally capable of terminating the Hermes-owned gateway child. It remains useful historical evidence only and is not part of the current native-Windows lifecycle.

## Evidence calibration

Historical installed-runtime evidence remains preserved for auditability. Current v2.6 acceptance must be based on current native-Windows runtime evidence. Upstream/tagged-repository documentation and source remain supporting context unless independently matched to installed artifacts.
