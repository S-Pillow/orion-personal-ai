# Hermes v0.22.5 isolated gateway smoke finding — 2026-10-30

## Attempt results

The first isolated standalone gateway contract smoke did not bind `127.0.0.1:18642` before its 45-second timeout. The child process remained alive until exact PID-scoped cleanup and the captured console log was empty.

A later hardened attempt did **not start the candidate at all**. It stopped in preflight because the helper required exactly one production listener on `127.0.0.1:8642`, but the observed production listener set was empty.

Neither result establishes a Hermes v0.22.5 runtime regression.

## Qualification-harness defects identified

The first implementation deep-copied the production COMPANION `config.yaml` into the disposable profile and then replaced only the messaging-platform section. That was too broad for a minimal gateway contract smoke:

- unrelated COMPANION configuration could participate in startup and make the test non-isolated;
- the script printed `SCRATCH_PRODUCTION_CREDENTIALS_COPIED=false` without proving that no credential-bearing value existed in `config.yaml`;
- a fresh scratch profile also allowed bundled-skill seeding to run, which made a bind/auth smoke exercise first-run bootstrap work before the gateway listener appeared;
- postcondition checks after candidate cleanup were not guaranteed to run when startup raised.

The later hardened implementation fixed those problems but introduced another invalid precondition: it treated a live production API-server listener on port 8642 as mandatory for an **isolated candidate** smoke. That is not a Hermes requirement. Port 8642 exists only when the `api_server` platform is enabled and healthy; a production baseline may legitimately be absent, and upstream has documented failure states where a gateway process remains alive while the API adapter is not listening.

The earlier claim that the first scratch configuration was fully sanitized is withdrawn. Production state itself was not intentionally modified by the attempt, but the retired v1 scratch tree may have contained copied production configuration until the research-corrected cleanup runs.

## External/upstream research

Research against the exact v0.22.5 source/docs and current upstream reports established:

1. **`gateway.standalone: true` must use normal `gateway run`, not `--force`.** The v0.22.5 multi-profile guide says a named standalone profile runs its own gateway without `--force`. The exact CLI describes `--force` as an escape hatch that bypasses supervisor/host protections and warns that a second dispatcher can escape the service and corrupt shared gateway state. The retired v1 smoke used `--force`; the corrected smoke does not.
2. **A running gateway PID is not equivalent to API readiness.** Upstream issue #91547 documents Windows/macOS cases where the gateway process remains alive after the `api_server` adapter fails to bind; port 8642 is then absent while the gateway still appears to be running. That issue explicitly states that a running gateway PID alone is not an API-readiness check.
3. **The API server is opt-in/configured independently.** Hermes documents `API_SERVER_ENABLED`, `API_SERVER_KEY`, `API_SERVER_HOST`, and `API_SERVER_PORT` as the API-server controls. Therefore an isolated candidate test must snapshot production listener state and prove it unchanged, not require a listener to exist.
4. **Process environment is sufficient for the disposable API key.** The qualification key does not need to be written to scratch `.env`; the corrected smoke keeps it only in the child process environment.
5. **Custom scratch roots are supported by v0.22.5 root resolution.** Exact `hermes_constants._hermes_root_of()` treats a custom `<root>/profiles/<name>` HERMES_HOME as belonging to `<root>`, so a `%TEMP%/.../profiles/companion` layout is a supported shape for this isolated profile test. The corrected smoke nevertheless probes `profile_name_for_home()` and `profile_is_standalone()` before launch and fails closed if the runtime resolves the scratch profile differently.
6. **Community reports show the same operational distinction.** Recent r/hermesagent Windows reports describe gateway `not_ready`/offline conditions while other Hermes activity remains alive, reinforcing that listener/health evidence must be checked directly rather than inferred from process existence.

No matching Stack Overflow report was found that was more specific or authoritative than the Hermes upstream issue/docs and r/hermesagent reports.

## Research-corrected implementation

`v0225_isolated_gateway_contract_smoke_v3.py` is the current research-corrected executable for the next attempt. It:

1. generates a minimal scratch `config.yaml` from nothing;
2. never copies production config content or production credentials into scratch;
3. forces `gateway.standalone: true` in the disposable named profile;
4. starts with normal `gateway run` and no `--force`;
5. enables only the localhost API server on port 18642;
6. creates `.no-bundled-skills` so this gate does not perform bundled-skill first-run seeding;
7. keeps the disposable API key in process environment only and never persists it to disk;
8. removes prior v1 scratch directories before production-listener assumptions;
9. probes that the scratch HERMES_HOME resolves as profile `companion` with standalone=true before launch;
10. snapshots production port 8642 as zero-or-one listener and requires the exact same baseline after cleanup;
11. launches with debug verbosity so a real no-bind produces useful startup evidence;
12. always re-verifies production watched state, candidate source hashes, and isolated-listener cleanup after runtime failure.

## Disposition

- Stock v0.22.5 production topology remains **NO-GO** because the current host is eligible for multiplex auto-migration and that path intersects the open Orion/Chat hard-gate risk.
- Isolated standalone qualification remains **GO** using the research-corrected v3 smoke.
- The first no-bind result is not yet classified as a Hermes v0.22.5 runtime failure because the retired harness was not minimal.
- The later `expected exactly one listener on 8642; observed []` result is a **qualification-harness precondition failure**, not a candidate launch failure; the candidate process was never started on that attempt.
- Production 8642 being absent is now a separate diagnostic fact to investigate, not a prerequisite that blocks the isolated candidate smoke.
