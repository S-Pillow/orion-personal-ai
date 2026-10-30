# Hermes v0.22.5 isolated gateway smoke finding — 2026-10-30

## Attempt result

The first isolated standalone gateway contract smoke did not bind `127.0.0.1:18642` before its 45-second timeout. The child process remained alive until exact PID-scoped cleanup. The captured console log was empty.

This attempt does **not** establish a Hermes runtime regression.

## Qualification-harness defects identified

The first implementation deep-copied the production COMPANION `config.yaml` into the disposable profile and then replaced only the messaging-platform section. That was too broad for a minimal gateway contract smoke:

- unrelated COMPANION configuration could participate in startup and make the test non-isolated;
- the script printed `SCRATCH_PRODUCTION_CREDENTIALS_COPIED=false` without proving that no credential-bearing value existed in `config.yaml`;
- a fresh scratch profile also allowed bundled-skill seeding to run, which made a bind/auth smoke exercise first-run bootstrap work before the gateway listener appeared;
- postcondition checks after candidate cleanup were not guaranteed to run when startup raised.

The earlier claim that the scratch configuration was fully sanitized is therefore withdrawn. Production state itself was not modified by the attempt, but the disposable scratch tree may have contained copied production configuration until cleanup.

## Hardened replacement

The original executable implementation was retired. `v0225_isolated_gateway_contract_smoke.py` is now only a compatibility entry point to `v0225_isolated_gateway_contract_smoke_v2.py`.

The hardened implementation:

1. generates a minimal scratch `config.yaml` from nothing;
2. never copies production config content or production credentials into scratch;
3. forces `gateway.standalone: true`;
4. enables only the localhost API server on port 18642;
5. creates `.no-bundled-skills` so this gate does not perform bundled-skill first-run seeding;
6. generates a one-run disposable API key and removes the scratch `.env` after cleanup;
7. removes prior v1 scratch directories created by the retired implementation after confirming the isolated port is free;
8. preserves bounded process/log diagnostics if the candidate still fails to bind;
9. always re-verifies production watched state, production port-8642 ownership, candidate source hashes, and isolated-listener cleanup even after a runtime failure.

## Disposition

- Stock v0.22.5 production topology remains **NO-GO** because the current host is eligible for multiplex auto-migration and that path intersects the open Orion/Chat hard-gate risk.
- Isolated standalone qualification remains **GO** using only the hardened smoke implementation.
- The no-bind result from the retired implementation is **not** yet classified as a Hermes v0.22.5 runtime failure.
