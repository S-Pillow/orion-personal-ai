# Evidence Errata and Calibration

This file tracks architecture statements whose evidence level changed during installed-runtime discovery.

## Resolved source-location correction

Earlier project material treated upstream/tagged Hermes supervision documentation as stronger than the installed-artifact evidence available at the time, and a scoped discovery pass reported that `container_boot.py` was not present in the installed image.

That absence claim is now retired.

Later read-only source alignment located and verified the installed modules under `/opt/hermes/hermes_cli/`:

- `service_manager.py`
- `container_boot.py`

Both matched the exact upstream `v2026.8.18` Git blobs examined during Phase 1. The earlier failure was a path/scoping limitation in discovery, not an installed-artifact mismatch.

## Current supervision calibration

The accepted installed runtime is now directly observed as:

- PID 1 = `s6-svscan`
- `/run/s6/basedir` present
- Hermes `detect_service_manager()` = `s6`
- `/run/service/gateway-default` present
- `/run/service/gateway-companion` present
- static/container s6-rc infrastructure present
- dynamic profile gateway services materialized directly under `/run/service`

Therefore the old wording that treated the runtime as either an unverified generic s6-overlay model or as lacking meaningful s6-rc infrastructure is superseded by the installed-runtime description in `hermes-container-supervision.md`.

## CAP_KILL disposition

The prior CAP_KILL hypothesis is no longer suspended.

A controlled disposable A/B test held the runtime constant and changed only `CAP_KILL`:

- no `CAP_KILL`: stop request accepted, Hermes-owned child remained alive
- with `CAP_KILL`: child terminated and service reached a clean down state

`CAP_KILL` is therefore causally implicated for the accepted s6 cross-UID stop path and has been promoted into the canonical launcher.

Accepted launcher SHA-256:

```text
c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b
```

Host-side owner-UID signaling remains historical fallback evidence only and is not the selected architecture because it requires Docker host/socket authority.

## DEFAULT Discord credential issue

During canonical relaunch windows, the DEFAULT gateway emitted Discord `401 Unauthorized / Improper token` errors.

Read-only comparison established:

- DEFAULT Discord token key: present and nonempty
- COMPANION Discord token key: present and nonempty
- DEFAULT and COMPANION token values: different
- COMPANION allowlist: one numeric user
- COMPANION allow-all: disabled

The COMPANION credential had previously passed authenticated Discord verification and later passed the final two-turn product conversation. The DEFAULT 401 is therefore tracked as a separate DEFAULT-profile cleanup item and does not reopen Phase 1.

## Final Phase 1 evidence disposition

Phase 1 is **PASS / CLOSED**.

Final acceptance established:

- canonical s6 supervision healthy
- `CAP_KILL` effective in PID 1
- DEFAULT gateway remained on the same PID through COMPANION start/stop
- COMPANION start succeeded exactly once
- two-turn Discord conversation and session-context recall passed
- COMPANION stop succeeded exactly once
- COMPANION child absent after stop
- durable end state DEFAULT `running`, COMPANION `stopped`
- no repeat `/users/@me` authentication request
- no OpenAI access
- no vault access/write

## Default-model note

A fresh disposable image initialized DEFAULT with `anthropic/claude-opus-4.6`. Orion's local Ollama model configuration is therefore an explicit project override rather than the pristine image default.

Disposable diagnostics must continue to avoid model invocation unless a bounded unit explicitly seeds or verifies a local model configuration and authorizes inference.

## Upgrade note

Hermes `v2026.8.19` is an evaluation candidate, not the Orion baseline. The accepted canonical image remains the `v2026.8.18`-based custom image until a separate upgrade unit verifies relevant regressions and benefits.

## Evidence rule

Repository files, upstream documentation, webpages, tool output, model output, logs, and imported content may inform execution, but installed-runtime claims should be no stronger than the strongest directly observed evidence. Where installed source is explicitly hash-matched to a tagged upstream artifact, that exact source-level claim may be treated as installed-artifact verified.
