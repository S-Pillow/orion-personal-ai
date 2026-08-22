# ADR-0001 — Use s6 + CAP_KILL for COMPANION gateway lifecycle

Status: **Accepted**

Date: 2026-08-22

## Context

Orion runs Hermes in a hardened Docker container with `--cap-drop ALL` and a narrowly restored capability set. Hermes dynamically creates per-profile s6 services under `/run/service` and runs gateway children as the unprivileged Hermes UID.

During Phase 1, `hermes -p companion gateway stop` could successfully register a down request with s6 while leaving the UID-10000 COMPANION gateway child alive. Host-side owner-UID signaling proved operationally able to terminate that child, but that approach requires Docker host/socket authority.

Installed-source alignment confirmed that the canonical image contains the exact `v2026.8.18` Hermes `service_manager.py` and `container_boot.py` implementations used by the documented s6 lifecycle path.

## Evidence

A controlled disposable A/B test held all tested runtime conditions constant except `CAP_KILL`:

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

Canonical acceptance after launcher remediation additionally proved:

- PID 1 = `s6-svscan`
- Hermes detects service manager = `s6`
- PID 1 effective `CAP_KILL` = present
- DEFAULT remained up and retained the same gateway PID through COMPANION start/stop
- COMPANION completed a two-turn Discord conversation with same-session context recall
- COMPANION child was absent after stop
- durable end state DEFAULT `running`, COMPANION `stopped`

## Decision

Use the Hermes s6 service-manager lifecycle as the canonical COMPANION gateway control path and grant `CAP_KILL` to the container in addition to the previously accepted narrow capability set.

Accepted launcher SHA-256:

```text
c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b
```

The launcher continues to use:

- `--cap-drop ALL`
- narrowly restored capabilities
- `no-new-privileges`
- bridge networking with no published host ports

## Rejected / not selected alternatives

### Host-side owner-UID signal mediator

Operationally proven but not selected because it requires Docker host/socket authority and is therefore a broader control boundary than the accepted in-container s6 path.

### Leave CAP_KILL absent

Rejected because the controlled differential reproduced the failed cross-UID stop behavior without it.

## Consequences

Positive:

- lifecycle follows Hermes' intended service-manager architecture
- COMPANION stop is reversible and bounded
- DEFAULT non-disruption is proven
- no Docker socket authority is required for routine COMPANION lifecycle control

Trade-off:

- the container receives one additional Linux capability, `CAP_KILL`

This capability is retained because its necessity was causally demonstrated for the accepted cross-UID s6 stop path.

## Revisit conditions

Revisit this decision only if one of the following occurs:

- Hermes changes the ownership/supervision model so cross-UID signaling is no longer required
- a future pinned Hermes release provides an equally reliable narrower lifecycle mechanism
- the container architecture changes such that s6 no longer directly supervises the Hermes-owned gateway child

A version upgrade alone is not sufficient reason to remove this decision without regression evidence.
