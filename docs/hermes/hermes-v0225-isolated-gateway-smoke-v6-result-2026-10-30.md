# Hermes v0.22.5 isolated gateway smoke v6 result — 2026-10-30

Status: **PASS WITH WINDOWS BIND-ENUMERATION LIMITATION**

Target candidate:

- upstream release: `v0.22.5`
- upstream release commit: `bf0203a794a07aac3ff764972ab9087baa4e4f4e`
- Orion migration tooling commit used by the operator: `12bd5c07f670abef915556a8c60c301800e55286`
- isolated API bind target: `127.0.0.1:18642`
- production API baseline: `127.0.0.1:8642`

## Operator result

The observer-hardened v6 contract passed the isolated standalone gateway gate without mutating production Hermes, COMPANION state, or the candidate source checkout.

Observed pass evidence:

```text
ISOLATED_BIND_CONFIGURATION=PASS|127.0.0.1:18642
CANDIDATE_HEAD=bf0203a794a07aac3ff764972ab9087baa4e4f4e
PRODUCTION_8642_HEALTH_BASELINE=HTTP_200|status=ok
SCRATCH_CONFIG_SOURCE=minimal_generated
SCRATCH_PROFILE_LAYOUT=profiles/orion_v0225_qual
SCRATCH_GATEWAY_STANDALONE=true
SCRATCH_BUNDLED_SKILL_SEEDING=disabled
SCRATCH_EXTERNAL_PLATFORM_COUNT=0
SCRATCH_PRODUCTION_CONFIG_CONTENT_COPIED=false
SCRATCH_PRODUCTION_CREDENTIALS_COPIED=false
SCRATCH_API_KEY_PERSISTED=false
READINESS_ORACLE=http_health_no_proxy
BIND_OBSERVER=netstat_bounded_supporting_evidence
LAUNCH_MODE=standalone_normal_no_force
ISOLATED_BIND_TARGET=127.0.0.1:18642
SCRATCH_PROFILE_RESOLUTION=PASS
SCRATCH_PROFILE_NAME=orion_v0225_qual
SCRATCH_PROFILE_STANDALONE=true
SCRATCH_WINDOWS_TASK_NAME=Hermes_Gateway_orion_v0225_qual
SCRATCH_WINDOWS_TASK_COLLISION=ABSENT
POST_READY_HTTP_STABILITY=PASS|samples=8
POST_READY_PROCESS_ALIVE=PASS
ISOLATED_BIND_NETSTAT=INCONCLUSIVE_NO_ROWS|attempts=12
ISOLATED_BIND_LOCALHOST_ONLY=CONFIG_CONFIRMED_RUNTIME_ENUMERATION_INCONCLUSIVE
ISOLATED_GATEWAY_HEALTH=PASS
API_BEARER_AUTH=PASS
CAPABILITY_CONTRACT=PASS
P404A_AUDIO_ROUTE_AUTH=PASS
P404A_AUDIO_ROUTE_LOCAL_VALIDATION=PASS
MODEL_PROVIDER_CALLS=0
STT_PROVIDER_CALLS=0
TTS_PROVIDER_CALLS=0
MEMORY_CALLS=0
SCRATCH_LOG_SECRET_REDACTION=NOT_NEEDED
PRODUCTION_8642_HEALTH_AFTER=HTTP_200|status=ok
ISOLATED_GATEWAY_CLEANUP=PASS
PRODUCTION_8642_HEALTH_BASELINE_UNCHANGED=PASS
PRODUCTION_WATCHED_STATE_UNCHANGED=PASS
CANDIDATE_SOURCE_UNCHANGED=PASS
BIND_EVIDENCE_LIMITATION=WINDOWS_SOCKET_ENUMERATION_EMPTY_WHILE_HTTP_STABLE
ISOLATED_STANDALONE_GATEWAY_CONTRACT=PASS_WITH_BIND_ENUMERATION_LIMITATION
PRODUCTION_HERMES_MUTATED=false
COMPANION_STATE_MUTATED=false
PRODUCTION_RUNTIME_RESTARTED=false
ISOLATED_GATEWAY_GATE=PASS
```

## What this closes

This result closes the isolated **standalone API/gateway contract** sub-gate for the exact qualified candidate:

- minimal generated scratch profile resolves to the unique `orion_v0225_qual` identity;
- scratch Windows Scheduled Task identity does not collide with production `Hermes_Gateway_companion`;
- standalone launch succeeds without `--force`;
- proxy-disabled `GET /health` is stable after readiness rather than a one-shot response immediately before process death;
- the candidate process remains alive across the post-ready stability window;
- API Bearer authentication rejects absent/wrong credentials and accepts the disposable key;
- the required API capability contract is present;
- the P4-04A `/api/audio/speak` and `/api/audio/transcribe` routes enforce authentication and perform local request validation;
- no model, STT, TTS, or memory provider call is required by this gate;
- the disposable API key is not persisted by the harness;
- cleanup succeeds;
- production 8642 health and watched production state remain unchanged;
- candidate source remains unchanged.

## Bind-enumeration limitation

Native Windows `netstat -ano -p TCP` returned no matching listener row for port 18642 across 12 bounded observations while all of the following were simultaneously true:

- the scratch configuration explicitly selected `127.0.0.1:18642`;
- repeated proxy-disabled HTTP health requests to `127.0.0.1:18642` returned `HTTP 200` with `status=ok`;
- the candidate process remained alive;
- authenticated API requests to the same endpoint succeeded;
- unauthenticated/wrong-token requests were rejected as expected.

Therefore the empty Windows socket-table snapshot is retained as an **evidence limitation**, not promoted to a Hermes runtime failure. v6 still fails closed if socket enumeration returns contradictory non-empty evidence, including a non-loopback bind, multiple listeners, or a listener PID outside the owned candidate process tree.

This limitation does **not** authorize a broader network-exposure claim. Production cutover still requires the ordinary Orion production bind/security requalification against the deployed runtime.

## Remaining disposable runtime work

The v6 pass does not qualify Hermes v0.22.5 for production. Remaining isolated-runtime work includes, at minimum:

1. session/resource persistence and COMPANION-profile-home isolation;
2. session/chat behavior that can be exercised safely in isolation;
3. runtime approval behavior beyond capability advertisement;
4. P6-03 exact pre-repair preservation at runtime/fixture level where needed;
5. P6-04A durable `error_class` behavior at runtime/fixture level where needed;
6. memory integration/profile-home boundaries where an isolated non-production memory path is available;
7. voice behavior requiring real provider/audio execution only when explicitly authorized and quota/network-safe.

The next selected gate is **scratch session/profile isolation without model-provider calls**. It should create, read, update, list, and delete only disposable session records through the authenticated v0.22.5 API; prove persistence under the scratch profile; verify session endpoints reject missing/wrong credentials; and re-prove production watched state remains unchanged.

## Authorization boundary

This evidence does not authorize production installation, cutover, profile reset, iai changes, model/provider changes, destructive database work, production restarts, or removal of rollback evidence. PR #81 remains pre-install qualification only.
