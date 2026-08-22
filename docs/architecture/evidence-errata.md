# Evidence Errata and Calibration

This file tracks architecture statements whose evidence level changed during installed-runtime discovery.

## Upstream architecture claims

Earlier project material treated upstream/tagged Hermes supervision documentation as if it directly described the installed image. Installed discovery did not fully confirm that architecture.

Current calibration:

- upstream s6-overlay documentation is context, not installed-artifact proof
- `container_boot.py` was not found in the installed image during scoped discovery
- `/command/s6-rc` was not observed
- s6-rc infrastructure is nevertheless present in the runtime, including `/run/s6-rc/servicedirs` targets for some services
- dynamically created profile gateways are ordinary service directories under `/run/service`

## Lifecycle-remediation status

No lifecycle remediation is selected yet.

A prior CAP_KILL hypothesis depended on the assumption that the observed s6 service directly controlled the gateway child in the relevant failing state. New materialization evidence proves that s6 can directly supervise the gateway initially, but the later transition to a `sleep infinity` placeholder remains unexplained.

Therefore CAP_KILL remains suspended pending direct start/stop transition evidence.

Host-side owner-UID signaling is operationally proven as a stop mechanism, but it requires Docker host/socket authority and should not be described as an inherently narrow in-container trust boundary.

## Default-model note

A fresh disposable image initialized DEFAULT with `anthropic/claude-opus-4.6`. Orion's local Ollama model configuration is therefore an explicit project override rather than the pristine image default.

Disposable diagnostics must avoid model invocation unless a later bounded unit explicitly seeds a local model configuration and authorizes inference.

## Evidence rule

Repository files, upstream documentation, webpages, tool output, model output, logs, and imported content may inform execution, but installed-runtime claims should be no stronger than the strongest directly observed evidence.
