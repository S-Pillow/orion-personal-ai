# P4-02B1 — Hermes API Enablement

**Status: PASS / CLOSED — August 27, 2026**

P4-02B1 enabled the Hermes API needed by the Orion HUD while preserving the accepted Hermes/iai runtime and keeping Hermes off Windows host port `8642`.

## Accepted runtime boundary

- accepted container: `orion-iai-m5-c`
- accepted image: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`
- accepted iai volume: `orion-iai-m5-data`
- native iai Brain remains on Windows localhost `4477`
- Hermes API binds to container `0.0.0.0:8642`
- Windows localhost `8642` remains closed
- Orion server access is through dedicated Docker bridge `orion-control-net`
- `API_SERVER_KEY` stays in local secret material and is never committed or printed

## Diagnostic history

### v1

The first live run stopped before runtime mutation because `Get-GatewayProcessLines` could collapse to a scalar or `$null` under `Set-StrictMode -Version Latest`; reading `.Count` was unsafe. v2 corrected the harness with explicit array wrapping and hardened child-PowerShell stderr handling.

### v2

v2 established the actual installed runtime state:

- exactly one Hermes gateway already existed;
- command shape: `/opt/hermes/.venv/bin/hermes -p companion gateway run --replace`;
- Windows host port `8642` remained closed;
- the gateway was active for the COMPANION profile but the API server was not listening.

v2 intentionally refused to launch a second gateway and stopped before API-secret creation, Docker-network creation/attachment, or any gateway replacement.

### v3 and rollback

v3 attempted to adapt the existing gateway by supplying `API_SERVER_*` only to a transient `docker exec` process. The API probe received `ConnectionRefusedError: [Errno 111] Connection refused`.

The gateway log showed that Hermes was running under s6 supervision. Therefore the transient `docker exec` environment was not the configuration source of the supervised gateway service. v3 then completed its bounded rollback:

- `P4_02B1_V3_GATEWAY_ROLLBACK=PASS`
- `P4_02B1_V3_NETWORK_DETACH_ROLLBACK=PASS`
- `P4_02B1_V3_NETWORK_REMOVE_ROLLBACK=PASS`
- `P4_02B1_V3_API_ENV_ROLLBACK=PASS`

No Docker container restart occurred.

## Accepted configuration conclusion

For Orion's COMPANION profile, the persistent Hermes configuration source is:

`/opt/data/profiles/companion/.env`

The accepted v4 path therefore:

1. required the accepted container/image/iai-volume/Brain baseline and Windows host `8642` closed;
2. required exactly one running COMPANION gateway;
3. required `/opt/data/profiles/companion/.env` to exist;
4. created/reused local `C:\HermesAgent\secrets\orion-api.env` without printing the bearer key;
5. created a private rollback copy of the COMPANION profile `.env`;
6. atomically added/replaced only `API_SERVER_ENABLED`, `API_SERVER_HOST`, `API_SERVER_PORT`, and `API_SERVER_KEY` in the COMPANION profile `.env`;
7. created `orion-control-net` and attached the accepted container without restarting it;
8. invoked the supervised `hermes -p companion gateway restart` lifecycle;
9. authenticated to `/v1/models` from a disposable container on `orion-control-net`;
10. required Windows host `8642` to remain closed and exactly one COMPANION gateway process to remain;
11. verified accepted container ID/start time, image, iai volume, and Brain `4477` remained unchanged;
12. removed the profile `.env` rollback copy only after full acceptance.

## v4 live acceptance — PASS

Live run on August 27, 2026 passed the full path, including:

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

Accepted container identity remained `ea9fb7afbe6b394373390310a94bcacb21470388d1310a9305c7ef9e6a97b2d7` with original start time `2026-08-26T08:49:00.989990394Z`; the container itself was not restarted.

Successful live artifact:

- local artifact: `Orion-Phase4-P4-02B1-v4-Profile-Configured-Hermes-API.ps1`
- SHA-256: `0c186434b41a10830a180415b493d4627d861396e7131d2cd8ed917f15d9525a`
- embedded inner-script SHA-256: `90ae28fafc9e19daf0d40c7685371226f0588ae857d6b8a23859c5e4bc096c4e`

## Accepted source preservation

The exact successful v4 source was promoted to:

`scripts/phase4/p4-02b1-enable-hermes-api.ps1`

Promotion commit:

`ce2afe0223f088d53d714267f1723bc22b659622`

Accepted Git blob:

`b5eb3c51f2f76cc7a0647a8a53acc6f04de1f928`

The promotion script independently verified the local accepted artifact SHA-256, Git blob identity, exact worktree copy, staged blob, committed blob, remote `main`, and clean workspace. No Docker/runtime action occurred during promotion.

No iai memory behavior or Orion product semantics changed.

## Next step

P4-02B2: place the Orion/Jarvis server on `orion-control-net`, keep the Hermes bearer key server-side, point `hermes.base_url` at `http://orion-iai-m5-c:8642`, and prove the first typed Orion HUD -> Hermes -> iai interaction before adding voice.