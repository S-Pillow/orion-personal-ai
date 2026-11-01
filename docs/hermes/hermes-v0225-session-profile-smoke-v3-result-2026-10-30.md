# Hermes v0.22.5 Isolated Session/Profile Smoke v3 Result

Status: **PASS**

Date: 2026-10-30

Target candidate:

- upstream release commit: `bf0203a794a07aac3ff764972ab9087baa4e4f4e`
- migration tooling head at execution: `d518bdf307cfd914b94175aed4bc5e9fa46032b7`
- scratch profile: `orion_v0225_qual`
- isolated API bind target: `127.0.0.1:18642`

## Result

The observer-hardened v3 session/profile gate passed end to end.

Observed runtime evidence:

```text
SESSION_PROFILE_HARNESS_VERSION=v3
STARTUP_ACCEPTANCE_BOUNDARY_S=90
SESSION_GATE_HTTP_READY=PASS|elapsed_s=7.745
SESSION_GATE_STARTUP_CLASSIFICATION=READY_WITHIN_90S
POST_READY_HTTP_STABILITY=PASS|samples=8
POST_READY_PROCESS_ALIVE=PASS
SESSION_RESOURCE_AUTH=PASS
SESSION_CREATE=PASS
SESSION_GET=PASS
SESSION_PATCH=PASS
SESSION_LIST=PASS
SESSION_DELETE=PASS
SCRATCH_PERSISTENCE_OBSERVER=sqlite_read_only
SCRATCH_SESSION_PERSISTENCE=PASS
SCRATCH_SESSION_PROFILE_ISOLATION=PASS
PRODUCTION_STATIC_CONFIG_UNCHANGED=PASS
PRODUCTION_GATEWAY_PID_IDENTITY_UNCHANGED=PASS
PRODUCTION_8642_HEALTH_BASELINE_UNCHANGED=PASS
CANDIDATE_SOURCE_UNCHANGED=PASS
ISOLATED_SESSION_PROFILE_CONTRACT=PASS
PRODUCTION_HERMES_MUTATED=false
COMPANION_STATE_MUTATED=false
PRODUCTION_RUNTIME_RESTARTED=false
```

The disposable session database was created only under the scratch profile:

`C:\Users\spill\AppData\Local\Temp\orion-hermes-v0225-session-profile-niznyhb_\profiles\orion_v0225_qual\state.db`

## What this proves

This gate proves, for the exact qualified v0.22.5 candidate on the operator's Windows runtime:

- the standalone scratch gateway starts within the retained 90-second acceptance boundary;
- post-ready health remains stable and the candidate process remains alive;
- session resource endpoints enforce bearer authentication;
- authenticated session create/get/patch/list/delete behavior works against the isolated API server;
- session metadata survives in the scratch profile's SQLite database;
- the scratch session store is profile-scoped rather than written into the production COMPANION profile;
- production static configuration and gateway PID identity remain unchanged;
- the production 8642 health baseline remains unchanged;
- the exact candidate source remains unchanged;
- cleanup succeeds without restarting production.

This closes the isolated session-resource/profile-persistence portion of the Chat/session reliability and Security/authorization hard gates. It does **not** qualify a model-backed chat turn, provider behavior, memory-provider behavior, or voice/STT/TTS execution.

## Prior startup variance

The immediately preceding v2 attempt did not become HTTP-ready inside 90 seconds, while a dedicated follow-up startup timing diagnostic reached readiness in 8.285 seconds and this v3 run reached readiness in 7.745 seconds.

Current classification: **intermittent startup variance observed once; not reproduced as a persistent blocker**.

Do not erase the prior finding. A future repeated >90-second startup should be treated as material lifecycle evidence and investigated rather than hidden by extending the acceptance timeout.

## Safety boundary

No production Hermes install, upgrade, cutover, restart, profile reset, iai change, provider/model change, production credential copy, model call, memory call, STT call, or TTS call was authorized or performed by this gate.

## Next gate

Proceed with deterministic runtime qualification of the two surviving cron compatibility requirements in an isolated scratch home:

1. P6-03 exact pre-repair `jobs.json` byte preservation;
2. P6-04A durable execution `error_class` persistence.

This next gate must remain local-only and provider-free. It must not run production cron jobs or touch the production cron store.
