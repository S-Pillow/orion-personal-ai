# Phase 1 Status

Status: **ACTIVE**

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
- AU-09A — pass / closed

## Active unit

### AU-08C — Discord gateway lifecycle

Transport and authentication evidence already established:

- configuration verified
- DNS verified
- TCP to Discord 443 verified
- TLS verified
- exactly one authenticated `GET /api/v10/users/@me` returned HTTP 200 with a valid bot object

The authenticated request is already accepted evidence and should not be repeated solely for lifecycle verification.

Current remaining objective: establish an accepted reversible COMPANION gateway lifecycle without disturbing DEFAULT.

## Gateway lifecycle discovery

### PH1-GW-L2B — objective pass / closed

Installed-runtime evidence established that creating a COMPANION profile dynamically materializes `/run/service/gateway-companion` in the same disposable runtime.

Observed sequence:

1. `gateway-companion` absent before profile creation.
2. Exactly one `hermes profile create companion` succeeded.
3. `/opt/data/profiles/companion` appeared.
4. `/run/service/gateway-companion` appeared immediately (`OBSERVED_AFTER_SECONDS=0`).
5. Generated service contained a `down` marker.
6. `s6-svstat` reported `down (not started yet)`.
7. Generated `run` script directly invoked the COMPANION Hermes gateway under s6 supervision.

A later process-display verifier failed because shell-regex quoting was mangled across the Windows -> Docker -> `sh -c` boundary. That verifier defect occurred after the decisive materialization evidence had already been collected and does not invalidate the L2B objective.

## Next bounded candidate

Disposable lifecycle transition observation:

- Snapshot A: before gateway start
- exactly one COMPANION gateway start
- Snapshot B: after start
- exactly one COMPANION gateway stop
- Snapshot C: after stop

The next experiment should determine what changes in `run`, `down`, supervisor state, and gateway child state across start and stop.

No lifecycle remediation mechanism is selected yet.
