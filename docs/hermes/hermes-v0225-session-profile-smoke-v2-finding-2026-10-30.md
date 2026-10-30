# Hermes v0.22.5 session/profile smoke v2 finding — 2026-10-30

Status: **DIAGNOSTIC BREAKPOINT — runtime gate unresolved**

## Observed attempt

The v2 session/profile smoke launched the exact qualified candidate at upstream release commit
`bf0203a794a07aac3ff764972ab9087baa4e4f4e` in the unique standalone scratch profile
`orion_v0225_qual` on `127.0.0.1:18642`.

Preflight passed:

- scratch bind configuration `127.0.0.1:18642`;
- structural scratch-profile identity;
- `gateway.standalone: true`;
- Windows task identity `Hermes_Gateway_orion_v0225_qual`;
- no matching Scheduled Task collision;
- production `/health` baseline `HTTP_200|status=ok`;
- no production config or credentials copied into scratch;
- no chat/model/memory/STT/TTS operation requested by the harness.

The candidate process then remained alive but did not expose HTTP `/health` within the harness's
90-second startup deadline. Safe diagnostics at timeout showed:

- parent process still running;
- one Python child still running;
- parent had one thread and very low observed CPU;
- scratch log contained the expected standalone-profile warnings;
- the next visible startup milestone was `Nous auth keepalive started`, logged roughly 62 seconds
after the first standalone warning;
- no API-server readiness line was observed before cleanup.

Because readiness never passed, the harness did **not** execute session create/get/patch/list/delete
and did not verify scratch `state.db` persistence. Therefore the session/profile contract is neither
pass nor fail yet.

## Production watched-state postcondition

The same attempt also reported:

`POSTCONDITION_ERROR=production watched artifacts changed during session/profile smoke`

The existing helper defines "watched production state" as immutable hashes for static config files
plus `(exists, size, mtime_ns)` signatures for live runtime artifacts including `state.db`,
`gateway_state.json`, and `gateway.pid` under the default and COMPANION roots.

That runtime signature is too strict as a mutation oracle while production Hermes is running:
`gateway_state.json` is a live status/heartbeat artifact and may change size or mtime independently of
the disposable candidate. SQLite/runtime metadata may also change because of legitimate production
activity. The harness did not identify which runtime path changed, so this postcondition cannot be
used to attribute a production mutation to the candidate attempt.

Static production configuration and exact process identity must remain hard gates. Volatile runtime
metadata should be reported path-by-path as observation unless a semantic invariant is violated.

## Relevance to open upstream risk

Open upstream issue `#144883` describes synchronous profile `.env` / `config.yaml` reads on the
gateway event loop stalling long enough to miss liveness probes. This attempt does **not** prove that
issue occurred: the process was still alive at the 90-second harness deadline and no watchdog exit 75
was observed. However, the long cold-start gap is close enough to the reported defect class that the
next bounded unit must be a startup-timing diagnostic rather than another session smoke retry.

## Disposition

- Hermes v0.22.5 candidate: **not rejected** by this attempt.
- Session/profile runtime gate: **unresolved**.
- Production mutation claim from volatile runtime mtime/size change: **withdrawn as unsupported**.
- Next unit: one cold-start diagnostic launch with no warm-up import and no session/model/provider
  operations. Measure HTTP-readiness latency, process liveness/resources, safe log growth, production
  health, static production configuration, and volatile-runtime path changes separately.
- Do not rerun the session/profile CRUD gate until the cold-start behavior is classified.
