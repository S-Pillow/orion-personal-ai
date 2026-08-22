# Hermes Container Supervision — Installed Runtime Evidence

This note records installed-runtime observations for the Orion Hermes image. It deliberately distinguishes observed runtime behavior from upstream or tagged-repository documentation.

## Installed topology

Observed runtime characteristics:

- supervision is rooted under `/run/service`
- s6-linux-init infrastructure is present
- s6-rc scaffolding processes/directories are present in the runtime
- some services resolve into `/run/s6-rc/servicedirs`
- dynamically created per-profile gateway services are materialized directly as ordinary directories under `/run/service`
- `/command/s6-rc` was not observed during the relevant discovery work

A calibrated description is therefore:

> The installed image exposes a `/run/service` supervision tree under s6-linux-init, with s6-rc infrastructure present. Some static/container services are backed by `/run/s6-rc/servicedirs`, while Hermes dynamically materializes per-profile gateway service directories directly under `/run/service`.

This should not be simplified to either “full upstream s6-overlay behavior is installed exactly as documented” or “s6-rc is not present at all.”

## Per-profile gateway materialization

In a disposable `--network none` runtime, creating the COMPANION profile caused `/run/service/gateway-companion` to appear immediately.

The generated service included:

- `run`
- `finish`
- `log/`
- `supervise/`
- `event/`
- `type`
- a zero-length `down` marker

The generated `run` script activated the Hermes virtual environment, set `HERMES_S6_SUPERVISED_CHILD=1`, and executed the COMPANION gateway via `s6-setuidgid hermes hermes -p companion gateway run --replace` when running as root.

Initial service status was:

```text
down (not started yet)
```

## Unresolved lifecycle transition

Earlier canonical-runtime evidence showed a later `gateway-companion/run` containing a `sleep infinity` placeholder. The newly proven profile-creation behavior shows that the service begins with a real gateway command, so some later lifecycle or reconciliation event must account for the placeholder state.

The next bounded experiment should observe the service before start, after exactly one start, and after exactly one stop.

## Evidence calibration

Upstream/tagged-repository references remain useful context, but installed runtime behavior is authoritative where they diverge. Architecture claims that rely on source files not present in the installed image should remain labeled as upstream/version-context evidence until independently confirmed in the installed artifact.
