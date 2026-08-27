# P4-02B1 — Hermes API Enablement

**Status: LIVE PASS — exact accepted v4 source promotion pending**

P4-02B1 enables the Hermes API needed by the Orion HUD while preserving the accepted Hermes/iai runtime and keeping Hermes off Windows host port `8642`.

## Intended runtime boundary

- accepted container: `orion-iai-m5-c`
- accepted image: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`
- accepted iai volume: `orion-iai-m5-data`
- native iai Brain remains on Windows localhost `4477`
- Hermes API binds to container `0.0.0.0:8642`
- Windows localhost `8642` remains closed
- Orion server access is through dedicated Docker bridge `orion-control-net`
- `API_SERVER_KEY` stays in local secret material and is never committed or printed

## v1 live diagnostic

The first P4-02B1 live run passed its outer hash/parser gates and stopped before runtime mutation because `Get-GatewayProcessLines` could collapse to a scalar or `$null` under `Set-StrictMode -Version Latest`; reading `.Count` was therefore unsafe. The correction wrapped the function results in `@(...)` and hardened child-PowerShell stderr handling.

## v2 live diagnostic

The v2 run passed the hash/parser gates and accepted-runtime precheck, then observed the actual installed runtime state:

- exactly one Hermes gateway already exists;
- command shape: `/opt/hermes/.venv/bin/hermes -p companion gateway run --replace`;
- Windows host port `8642` remained closed;
- the gateway was active for the COMPANION profile but the API server was not listening.

v2 intentionally refused to launch a second gateway and stopped before API-secret creation, Docker-network creation/attachment, or any gateway replacement.

## v3 live diagnostic and rollback

v3 attempted to adapt the existing COMPANION gateway by launching the same profile command with `API_SERVER_*` supplied only to the transient `docker exec` process.

The run established:

- outer hash/parser gates: PASS;
- accepted container identity/start-time/volume/Brain precheck: PASS;
- exactly one existing COMPANION gateway: PASS;
- Windows host `8642`: CLOSED;
- dedicated local API secret creation: PASS;
- `orion-control-net` creation: PASS;
- accepted-container network attachment: PASS;
- gateway replacement launch: PASS.

The API probe then received `ConnectionRefusedError: [Errno 111] Connection refused` from container port `8642`.

The gateway log provided the decisive installed-runtime clue: Hermes reported that the gateway was running under **s6 supervision** and recommended that supervised mode for the container image. Therefore the `gateway run --replace` CLI invocation delegated gateway ownership back to the s6 service. The transient environment passed to `docker exec` was not the configuration source of the supervised gateway process, so `API_SERVER_ENABLED=true` never reached the service that actually owned the gateway.

v3 then completed its bounded rollback:

- `P4_02B1_V3_GATEWAY_ROLLBACK=PASS`
- `P4_02B1_V3_NETWORK_DETACH_ROLLBACK=PASS`
- `P4_02B1_V3_NETWORK_REMOVE_ROLLBACK=PASS`
- `P4_02B1_V3_API_ENV_ROLLBACK=PASS`

No Docker container restart occurred. The accepted runtime was returned to its prior gateway/network/secret baseline.

## Upstream-supported configuration conclusion

Hermes v2026.8.18 documentation confirms the correct boundary:

- the API server is enabled through `API_SERVER_ENABLED=true` plus `API_SERVER_KEY`, with `API_SERVER_HOST=0.0.0.0` required for non-loopback container access;
- Hermes reads user-managed secrets from the active Hermes/profile `.env`;
- each profile has its own `.env` and its own `HERMES_HOME`;
- inside the official Docker/s6 layout, profile gateways are supervised services and `hermes -p <profile> gateway restart` dispatches through the supervisor.

For Orion's COMPANION profile, the persistent Hermes configuration source is therefore:

`/opt/data/profiles/companion/.env`

This is an integration/configuration-boundary correction, not an iai or Hermes API defect.

## v4 implementation

v4 follows the Hermes profile/s6 model instead of trying to inject environment variables into a transient gateway CLI process.

The bounded sequence is:

1. require the accepted container/image/iai-volume/Brain baseline and Windows host `8642` closed;
2. require exactly one running COMPANION gateway;
3. require `/opt/data/profiles/companion/.env` to exist;
4. create/reuse local `C:\HermesAgent\secrets\orion-api.env` without printing the bearer key;
5. create a private rollback copy of the COMPANION profile `.env`;
6. atomically add/replace only `API_SERVER_ENABLED`, `API_SERVER_HOST`, `API_SERVER_PORT`, and `API_SERVER_KEY` in the COMPANION profile `.env`;
7. create/reuse `orion-control-net` and attach the accepted container without restarting the container;
8. invoke the supported supervised lifecycle command `hermes -p companion gateway restart`;
9. authenticate to `/v1/models` from a disposable container on `orion-control-net`;
10. require Windows host `8642` to remain closed and exactly one COMPANION gateway process to remain;
11. verify accepted container ID/start time, image, iai volume, and Brain `4477` remain unchanged;
12. remove the profile `.env` rollback copy only after full acceptance.

On failure after profile mutation, v4 restores the original profile `.env`, restarts the supervised COMPANION gateway, removes only networking created by that run, and restores/removes the host-side Orion API secret according to its pre-run state.

## v4 live acceptance — PASS

Live run on August 27, 2026 passed the full acceptance path.

Observed PASS evidence:

- `P4_02B1_V4_INNER_HASH=PASS`
- `P4_02B1_V4_INNER_PARSE=PASS`
- `P4_02B1_V4_ACCEPTED_RUNTIME_PRECHECK=PASS`
- `P4_02B1_V4_EXISTING_COMPANION_GATEWAY=PASS`
- `P4_02B1_V4_GATEWAY_STATUS_PRE=PASS`
- `P4_02B1_V4_COMPANION_PROFILE_ENV=PASS`
- `P4_02B1_V4_API_SECRET_READY=PASS`
- `P4_02B1_V4_HOST_SECRET_FILE_READY=PASS`
- `P4_02B1_V4_CONTAINER_HELPERS_READY=PASS`
- `P4_02B1_V4_ROLLBACK_HELPER_RETAINED=PASS`
- `P4_02B1_V4_PROFILE_ENV_APPLY=PASS`
- `P4_02B1_V4_PROFILE_CONFIG_SOURCE=PASS`
- `P4_02B1_V4_CONTROL_NETWORK_CREATED=PASS`
- `P4_02B1_V4_ACCEPTED_CONTAINER_NETWORK_ATTACH=PASS`
- `P4_02B1_V4_SUPERVISED_GATEWAY_RESTART=PASS`
- `P4_02B1_V4_GATEWAY_STATUS_POST_RESTART=PASS`
- `P4_02B_AUTH_MODELS_STATUS=200`
- `P4_02B_AUTHENTICATED_API=PASS`
- `P4_02B1_V4_CONTROL_NETWORK_API=PASS`
- `P4_02B1_V4_HOST_8642_POST=CLOSED`
- `P4_02B1_V4_NO_HOST_HERMES_API_EXPOSURE=PASS`
- `P4_02B1_V4_SINGLE_GATEWAY_PROCESS=PASS`
- `P4_02B1_V4_NO_CONTAINER_RESTART=PASS`
- `P4_02B1_V4_IAI_BRAIN_PRESERVED=PASS`
- `P4_02B1_V4_ACCEPTED_VOLUME_PRESERVED=PASS`
- `P4_02B1_V4_PROFILE_ENV_FINALIZE=PASS`
- `P4_02B1_V4_HERMES_API_ENABLEMENT=PASS`
- `P4_02B1_V4_OUTER=PASS`

Accepted container identity remained `ea9fb7afbe6b394373390310a94bcacb21470388d1310a9305c7ef9e6a97b2d7` with original start time `2026-08-26T08:49:00.989990394Z`; therefore the container itself was not restarted.

The successful live artifact is `Orion-Phase4-P4-02B1-v4-Profile-Configured-Hermes-API.ps1` with SHA-256 `0c186434b41a10830a180415b493d4627d861396e7131d2cd8ed917f15d9525a` and embedded inner-script SHA-256 `90ae28fafc9e19daf0d40c7685371226f0588ae857d6b8a23859c5e4bc096c4e`.

## Source-preservation status

The live runtime behavior is accepted. Per Orion's source-preservation rule, P4-02B1 is not marked fully CLOSED until the exact successful v4 artifact above is promoted to `scripts/phase4/p4-02b1-enable-hermes-api.ps1` and its remote blob is verified.

No iai memory behavior or Orion product semantics were changed.

## Next step

Promote the exact accepted v4 artifact to the canonical Phase 4 script, then begin P4-02B2: place the Orion/Jarvis server on `orion-control-net` and prove the first typed Orion HUD -> Hermes -> iai interaction before adding voice.
