# Hermes Container Supervision — Installed Runtime Evidence

This note records installed-runtime observations for the Orion Hermes image and distinguishes installed evidence from upstream/tagged-repository context.

## Accepted installed topology

Observed canonical runtime characteristics:

- PID 1 is `s6-svscan`
- supervision is rooted under `/run/service`
- s6-linux-init infrastructure is present
- `/run/s6/basedir` is present
- s6-rc infrastructure is present in the runtime
- some static/container services resolve into `/run/s6-rc/servicedirs`
- dynamically created per-profile gateway services are materialized directly as ordinary directories under `/run/service`
- Hermes runtime service-manager detection returns `s6`

A calibrated installed-runtime description is:

> The accepted Orion Hermes runtime uses s6-linux-init/s6 supervision with a `/run/service` supervision tree. s6-rc infrastructure is present for container services, while Hermes dynamically materializes per-profile gateway service directories directly under `/run/service` and manages them through its installed s6 service-manager path.

## Installed source alignment

Read-only source alignment established that the installed modules are the exact tagged `v2026.8.18` implementations examined during Phase 1:

- `/opt/hermes/hermes_cli/service_manager.py`
- `/opt/hermes/hermes_cli/container_boot.py`

The earlier scoped-discovery statement that `container_boot.py` was absent from the installed image is retired; the file was present under `/opt/hermes/hermes_cli/` and had simply not been located by the earlier path-limited inspection.

## Per-profile gateway materialization

In a disposable `--network none` runtime, creating the COMPANION profile caused `/run/service/gateway-companion` to appear immediately.

The generated service included the expected s6 service artifacts, a `down` marker, and a real `run` script that activates the Hermes virtual environment and executes the COMPANION gateway under the Hermes UID. Initial service status was:

```text
down (not started yet)
```

This proves that Hermes dynamically creates the per-profile supervision slot before the gateway is started.

## Cross-UID stop requirement

The accepted Orion container hardening uses `--cap-drop ALL` and selectively restores required capabilities. Phase 1 isolated one additional lifecycle requirement: `CAP_KILL`.

The relevant ownership relationship is:

```text
root s6-supervise
        |
        v
UID 10000 Hermes gateway child
```

A controlled disposable A/B lifecycle test differed only by `CAP_KILL`:

- without `CAP_KILL`, `hermes -p companion gateway stop` returned success but the Hermes-owned child remained alive and s6 remained in a requested-down state
- with `CAP_KILL`, the same stop cleanly terminated the child and left the service down

This provides causal support for `CAP_KILL` as the required capability for the in-container s6 supervisor to terminate the differently owned gateway child.

## Accepted lifecycle mechanism

The accepted Phase 1 lifecycle design is now:

> **Hermes s6 service manager + in-container s6 supervision + `CAP_KILL`.**

The canonical launcher retains `--cap-drop ALL`, the prior narrow capability set, `no-new-privileges`, and adds `KILL` specifically to satisfy the proven s6 cross-UID signal requirement.

The accepted launcher SHA-256 is:

```text
c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b
```

## Canonical acceptance

Final Phase 1 acceptance proved:

- DEFAULT supervised up before COMPANION start
- COMPANION supervised down before start
- exactly one COMPANION start succeeded
- COMPANION remained supervised and responsive through a two-turn Discord conversation
- exactly one COMPANION stop succeeded
- COMPANION gateway child was absent after stop
- DEFAULT retained the same gateway PID before, during, and after the COMPANION lifecycle
- PID 1 remained `s6-svscan`
- durable end state was DEFAULT `running`, COMPANION `stopped`

## Host-side owner-UID signaling

Host-side `docker exec -u hermes ... kill <pid>` was previously proven operationally capable of terminating the Hermes-owned gateway child. It remains useful historical evidence, but it is **not** the selected lifecycle mechanism because it requires Docker host/socket authority.

The accepted in-container s6 + `CAP_KILL` path is narrower and follows Hermes' intended service-manager architecture.

## Evidence calibration

Installed runtime behavior remains authoritative for Orion acceptance. Upstream/tagged-repository documentation and source are supporting context unless independently matched to installed artifacts. During Phase 1, the relevant installed lifecycle modules were independently matched to the exact `v2026.8.18` source, so those particular source-level lifecycle claims are now installed-artifact verified.
