# P4-02B1A Durable Startup and Recovery

Status: implementation candidate; production acceptance pending.

## Problem

The accepted external-idle compatibility deployment proved the iai-side adapter, but it left three lifecycle owners split across ad-hoc launch mechanisms:

- Docker container `orion-iai-m5-c` used restart policy `no`.
- iai daemon was launched by a one-time `docker exec -d ... python -m iai_mcp.daemon`.
- the Windows `GetLastInputInfo` producer was launched by a one-time PowerShell child process.

A Docker Desktop/daemon restart therefore recovered the s6-managed Hermes gateway but did not recover the container automatically, the iai daemon, or the Windows host-idle producer.

## Durable ownership model

This change assigns each long-running component to its native supervisor:

1. Docker owns the Orion core container with `restart: unless-stopped`.
2. s6-overlay owns the iai daemon as an s6-rc `longrun` in the image.
3. Windows Task Scheduler owns the host-idle producer with an interactive-logon trigger and restart-on-failure settings.

The host-idle producer must use an interactive Windows token because `GetLastInputInfo` reports activity for the calling session.

## s6 service

Image overlay:

- base: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-extidle-b6d356e`
- service: `/etc/s6-overlay/s6-rc.d/orion-iai-daemon`
- type: `longrun`
- dependency: `base`
- bundle: `/etc/s6-overlay/user-bundles.d/user/contents.d/orion-iai-daemon`

The run script drops to the existing `hermes` account and starts:

```text
/opt/iai/venv/bin/python -m iai_mcp.daemon
```

with the accepted COMPANION store, socket, offline embedding, and external-idle environment.

## Windows task

Task name:

```text
Orion Host Idle Bridge
```

Properties:

- trigger: logon of the installing interactive user
- logon type: Interactive
- run level: Limited
- multiple instances: IgnoreNew
- restart on failure: 10 attempts, one-minute interval
- no execution time limit
- allowed on battery
- installed bridge path: `C:\HermesAgent\bin\Orion-Host-Idle-Bridge.ps1`

The bridge now writes both `host-idle.json` and its PID/instance record itself, so process identity does not depend on a deployment harness.

## Source provenance

Repository commit/path is the source-of-truth provenance boundary. Do not compare a Windows working-copy SHA/blob to the Git blob because Git line-ending conversion may legitimately change working-tree bytes.

## Production acceptance

A production deployment is accepted only after all of the following are true:

- core uses the supervised image and `unless-stopped`;
- exact persistent volume, bind mount, capabilities, security option, networks, and no-host-port topology are preserved;
- Task Scheduler owns a live bridge and two fresh samples from the same producer are observed;
- s6 reports `orion-iai-daemon` up;
- daemon socket/state are healthy;
- Hermes COMPANION API and fresh wrapper recover;
- iai reads `external_idle_file`;
- a deliberate container restart recovers the iai daemon and COMPANION automatically without `docker exec` daemon launch;
- no lifecycle thresholds, memory state, or lifecycle state are edited.

A full Docker Desktop restart can be used as the final host-level recovery proof after the bounded container-level acceptance.
