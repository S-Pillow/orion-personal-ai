# P4-02B1 — Hermes API Enablement

**Status: IN PROGRESS — live acceptance pending**

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

## First live attempt — diagnostic failure

The first P4-02B1 live run on August 27, 2026 passed both pre-execution safeguards:

- `P4_02B1_INNER_HASH=PASS`
- `P4_02B1_INNER_PARSE=PASS`

It then failed under `Set-StrictMode -Version Latest` because `Get-GatewayProcessLines` can emit zero or one PowerShell pipeline object. The caller assigned that function result directly and then read `.Count`; with zero/one output, PowerShell may produce `$null` or a scalar rather than an array, so `.Count` is not safe under StrictMode.

The first unsafe `.Count` occurs during the existing-gateway precheck, before API secret creation, Docker-network creation/attachment, or Hermes gateway launch. Therefore this failed attempt did not mutate the accepted runtime.

The outer launcher also used `ErrorActionPreference=Stop` while invoking a child `powershell.exe`, allowing child stderr to surface as `NativeCommandError` before the wrapper could replay the inner diagnostic output.

## v2 correction

Canonical script: `scripts/phase4/p4-02b1-enable-hermes-api.ps1`

v2 changes only the harness behavior:

- wraps both `Get-GatewayProcessLines` call sites in `@(...)` so `.Count` is deterministic for zero, one, or multiple results;
- temporarily sets the outer wrapper to `ErrorActionPreference=Continue` only around the child PowerShell invocation, then restores the original preference, so a failed child run can be reported with its full output and exit code;
- retains the hash gate, parser gate, secret redaction, no-host-publish policy, accepted-container identity checks, iai volume checks, Brain check, and authenticated disposable API probe.

No iai memory behavior or Orion product semantics changed.

## Acceptance criteria

P4-02B1 is accepted only when the live run reaches the authenticated API and preservation markers, including:

- `P4_02B_AUTHENTICATED_API=PASS`
- `P4_02B1_CONTROL_NETWORK_API=PASS`
- `P4_02B1_HOST_8642_POST=CLOSED`
- `P4_02B1_NO_HOST_HERMES_API_EXPOSURE=PASS`
- `P4_02B1_GATEWAY_PROCESS=PASS`
- `P4_02B1_NO_CONTAINER_RESTART=PASS`
- `P4_02B1_IAI_BRAIN_PRESERVED=PASS`
- `P4_02B1_ACCEPTED_VOLUME_PRESERVED=PASS`
- `P4_02B1_HERMES_API_ENABLEMENT=PASS`
- `P4_02B1_OUTER=PASS`

After P4-02B1 passes, the next step is to place the Orion/Jarvis server on `orion-control-net` and prove typed Orion HUD -> Hermes -> iai interaction before adding voice.
