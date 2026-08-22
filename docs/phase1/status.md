# Phase 1 Status

Status: **PASS / CLOSED**

## Completed / accepted units

- AU-01A — complete
- AU-01B — pass / closed
- AU-01C — pass / closed
- AU-02A — pass / closed
- AU-02B — pass / closed
- AU-03 — pass / closed
- AU-04 — pass / closed
- AU-05 — pass / closed
- AU-06 — pass / closed
- AU-07 — pass / closed
- AU-08A — pass / closed
- AU-08B — pass / closed
- AU-08C — pass / closed
- AU-09A — pass / closed

## Phase 1 closure summary

Phase 1 closed after canonical end-to-end acceptance of the COMPANION Discord gateway and local conversation path.

Accepted lifecycle result:

- canonical launcher SHA-256: `c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b`
- lifecycle mechanism: in-container s6 supervision with `CAP_KILL`
- PID 1 remained `s6-svscan`
- Hermes service-manager detection returned `s6`
- DEFAULT remained continuously supervised and retained the same gateway child PID through COMPANION start/stop acceptance
- COMPANION started exactly once through Hermes/s6
- COMPANION remained healthy during the Discord acceptance conversation
- COMPANION stopped exactly once through Hermes/s6
- COMPANION child was absent after stop
- durable end state: DEFAULT `running`, COMPANION `stopped`
- no repeat `/api/v10/users/@me` authentication probe was performed
- no OpenAI access occurred
- no vault access or vault write occurred

## Discord acceptance

The final product smoke used a two-turn Discord conversation with a unique marker.

Observed acceptance behavior:

1. COMPANION returned the supplied marker and a coherent short local-first response.
2. On the next turn, COMPANION recalled the same marker from session context.
3. Operator acceptance was PASS.

The second response included extra explanatory text despite a request for marker-only output. This is a formatting/compliance note, not a Phase 1 stability or context-continuity failure.

## Gateway lifecycle root cause and remediation

A disposable A/B test isolated `CAP_KILL` as the causal difference for clean cross-UID gateway termination under s6:

- without `CAP_KILL`, `gateway stop` returned successfully but the UID-10000 child remained alive while s6 reported a down request
- with `CAP_KILL`, the otherwise-identical stop terminated the child and left the service cleanly down

The accepted launcher therefore retains `--cap-drop ALL`, restores the previously accepted narrow capability set, and additionally grants `KILL` so the root s6 supervisor can signal the Hermes-owned gateway child.

## Supporting Phase 1 findings

- creating a COMPANION profile dynamically materializes `/run/service/gateway-companion`
- the generated service initially contains the real Hermes gateway run command and a `down` marker
- installed `hermes_cli.service_manager` and `hermes_cli.container_boot` matched the exact upstream `v2026.8.18` Git blobs during source-alignment discovery
- canonical runtime uses bridge networking with no published host ports
- DEFAULT and COMPANION Discord credentials are both present but are different values
- COMPANION retains one numeric Discord allowlisted user and allow-all remains disabled

## Non-blocking follow-ups

These do not reopen Phase 1:

- DEFAULT separately emitted Discord `401 Unauthorized / Improper token` errors during relaunch windows; DEFAULT and COMPANION credentials were proven different, so this is a DEFAULT-profile credential cleanup item
- COMPANION final s6 status after accepted stop reported `down (exitcode 1)` while the child was absent, desired state was stopped, DEFAULT was unaffected, and PID 1 remained `s6-svscan`
- Hermes upstream `v2026.8.19` is an evaluation candidate only; Orion remains pinned to the accepted `v2026.8.18`-based image until a separate upgrade evaluation is authorized

## Next phase

Next planned work: **Phase 2 — iai feasibility and memory foundation**.

Initial Phase 2 evaluation should remain isolated and local-first, use a supported Python 3.11/3.12 environment rather than the Hermes Python 3.13 environment, verify fail-open behavior when memory is unavailable, and ensure no optional cloud consolidation path is enabled without explicit authorization.
