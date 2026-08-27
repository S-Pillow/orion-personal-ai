# P4-02B1 — Hermes API Enablement

**Status: IN PROGRESS — v3 live acceptance pending**

P4-02B1 enables the Hermes API needed by the Orion HUD while preserving the accepted Hermes/iai runtime and keeping Hermes off Windows host port `8642`.

## Intended runtime boundary

- accepted container: `orion-iai-m5-c`
- accepted image: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`
- accepted iai volume: `orion-iai-m5-data`
- native iai Brain remains on Windows localhost `4477`
- Hermes API binds to container `0.0.0.0:8642`
- Windows localhost `8642` must remain closed
- Orion server access is through dedicated Docker bridge `orion-control-net`
- `API_SERVER_KEY` stays in local secret material and is never committed or printed

## v1 live diagnostic

The first P4-02B1 live run passed its outer hash/parser gates and stopped before runtime mutation because `Get-GatewayProcessLines` could collapse to a scalar or `$null` under `Set-StrictMode -Version Latest`; reading `.Count` was therefore unsafe. The correction wrapped the function results in `@(...)` and hardened child-PowerShell stderr handling.

## v2 live diagnostic

The v2 run passed the hash/parser gates and accepted-runtime precheck, then observed the actual installed runtime state:

- exactly one Hermes gateway already exists;
- command shape: `/opt/hermes/.venv/bin/hermes -p companion gateway run --replace`;
- Windows host port `8642` remains closed;
- the gateway is therefore active for the COMPANION profile but was started without the API-server environment needed for the Orion HUD.

v2 intentionally refused to launch a second gateway and stopped before API-secret creation, Docker-network creation/attachment, or any gateway replacement.

This finding changes the implementation path: P4-02B1 must adapt the existing gateway rather than create a parallel gateway process.

## v3 implementation

v3 uses the existing supported Hermes `gateway run --replace` lifecycle for the same `companion` profile.

The bounded sequence is:

1. confirm exactly one existing COMPANION gateway and a running gateway status;
2. create/reuse local `C:\HermesAgent\secrets\orion-api.env` without printing the key;
3. create/reuse `orion-control-net` and attach the accepted container without restarting it;
4. replace the existing COMPANION gateway in place with the same profile plus `API_SERVER_ENABLED=true`, `API_SERVER_HOST=0.0.0.0`, `API_SERVER_PORT=8642`, and the local bearer key;
5. authenticate to `/v1/models` from a disposable container on `orion-control-net`;
6. require Windows localhost `8642` to remain closed;
7. require one COMPANION gateway process after replacement and preserve prior Discord-connected state when the gateway status reported it before replacement;
8. verify accepted container ID/start time, image, iai volume, and Brain `4477` state remain unchanged.

If the replacement path fails, v3 attempts a bounded rollback: restart the COMPANION gateway without the API env, restore any network attachment created by the run, remove a newly created control network when safe, and delete a newly created API env file.

The v3 delivery artifact is `Orion-Phase4-P4-02B1-v3-Adapt-Existing-Gateway.ps1`; after live acceptance, the accepted revision will replace the canonical `scripts/phase4/p4-02b1-enable-hermes-api.ps1` source and the README/status records will be flipped in the same closure step.

No iai memory behavior or Orion product semantics are changed.

## Acceptance criteria

P4-02B1 is accepted only when the live v3 run reaches the authenticated API and preservation markers, including:

- `P4_02B_AUTHENTICATED_API=PASS`
- `P4_02B1_V3_CONTROL_NETWORK_API=PASS`
- `P4_02B1_V3_GATEWAY_STATUS_POST=PASS`
- `P4_02B1_V3_SINGLE_GATEWAY_PROCESS=PASS`
- `P4_02B1_V3_EXISTING_GATEWAY_REPLACED=PASS`
- `P4_02B1_V3_HOST_8642_POST=CLOSED`
- `P4_02B1_V3_NO_HOST_HERMES_API_EXPOSURE=PASS`
- `P4_02B1_V3_NO_CONTAINER_RESTART=PASS`
- `P4_02B1_V3_IAI_BRAIN_PRESERVED=PASS`
- `P4_02B1_V3_ACCEPTED_VOLUME_PRESERVED=PASS`
- `P4_02B1_V3_HERMES_API_ENABLEMENT=PASS`
- `P4_02B1_V3_OUTER=PASS`

After P4-02B1 passes, the next step is to place the Orion/Jarvis server on `orion-control-net` and prove typed Orion HUD -> Hermes -> iai interaction before adding voice.
