# Hermes v0.22.5 Qualification Status

Status: **PRE-INSTALL QUALIFICATION — ACTIVE**

Last updated: 2026-10-30

PR: #81 — `feature/hermes-v0225-controlled-migration`

## Production boundary

The accepted production Hermes runtime remains unchanged:

- Hermes Agent package: `0.20.6`
- accepted tag: `v2026.8.27`
- accepted source commit: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- production profile: `companion`
- production API: `127.0.0.1:8642`

No production Hermes install, upgrade, cutover, profile reset, iai change, model/provider change, production restart, or destructive database rewrite has been authorized or performed by the v0.22.5 qualification work.

## Exact candidate

The controlled migration target remains upstream Hermes `v0.22.5` at exact release commit:

`bf0203a794a07aac3ff764972ab9087baa4e4f4e`

The disposable candidate carries only the three Orion compatibility requirements retained for v0.22.5:

1. P4-04A — authenticated bounded audio relay on the existing API-server gateway;
2. P6-03 — exact pre-repair `jobs.json` byte preservation;
3. P6-04A — durable execution `error_class` persistence.

The old Orion P5 approval backport and old P6-04 ledger implementation remain retired for this candidate because v0.22.5 provides the relevant native behavior.

## Qualification completed

### Source candidate — PASS

Exact-release source qualification passed. The candidate compiled, the changed-path scope matched the intended compatibility delta, P4-04A/P6-03/P6-04A source assertions passed, v0.22.5 dependency ownership of `edge-tts==7.3.1` was confirmed, and installed Hermes remained unchanged.

Evidence:

- `docs/hermes/hermes-v0225-source-qualification-2026-10-30.md`
- `docs/hermes/hermes-v0225-dependency-override-qualification.md`

### Isolated standalone gateway contract — PASS WITH BIND ENUMERATION LIMITATION

The exact candidate launched in a unique standalone scratch profile on `127.0.0.1:18642`, remained HTTP-stable, enforced Bearer authentication, exposed the required capability contract, and passed local P4-04A audio route authentication/validation without model, STT, TTS, or memory provider calls.

Windows `netstat` returned no listener rows during the bounded observation window while HTTP remained stable. This is retained as a Windows socket-enumeration evidence limitation, not a candidate failure and not proof of broader network exposure.

Evidence:

- `docs/hermes/hermes-v0225-isolated-gateway-smoke-v6-result-2026-10-30.md`

### Startup timing diagnostic — PASS

After one session-gate attempt remained alive but did not become HTTP-ready within the legacy 90-second boundary, a dedicated no-session diagnostic was run rather than extending the gate.

The diagnostic reached HTTP readiness in **8.285 seconds**, passed post-ready stability, preserved production static configuration and production gateway PID identity, and left the candidate source unchanged.

The earlier 90-second miss remains an intermittent/unresolved startup-variance observation, not a reproduced v0.22.5 blocker. The 90-second acceptance boundary remains unchanged so a recurrence stays visible.

Evidence:

- `docs/hermes/hermes-v0225-startup-timing-diagnostic-result-2026-10-30.md`

### Isolated session/profile resource contract — PASS

Session/profile smoke v3 reached HTTP readiness in **7.745 seconds** and passed:

- session resource Bearer-auth enforcement;
- session create;
- session get;
- session patch;
- session list;
- session delete;
- persisted scratch-session verification through read-only SQLite;
- scratch profile isolation;
- production static-config invariance;
- production gateway PID identity invariance;
- cleanup and candidate-source invariance.

No chat turn, model provider call, memory call, STT call, or TTS call was made.

This closes the isolated session-resource/profile-persistence sub-gate. It does **not** by itself qualify a real model-backed chat turn or the full Memory/Voice production hard gates.

Evidence:

- `docs/hermes/hermes-v0225-session-profile-smoke-v3-result-2026-10-30.md`

## Current gate

### P6-03 / P6-04A isolated runtime compatibility contract — PENDING OPERATOR RESULT

Current harness:

- `scripts/hermes_upgrade/v0225_isolated_cron_compat_contract_smoke.py`

The gate is designed to run without a gateway process or provider traffic and to use only a disposable `HERMES_HOME`.

It must prove:

- P6-03 preserves the exact pre-repair `jobs.json` bytes before a harmless automatic repair rewrite;
- the recovery artifact is byte-for-byte identical to the original input;
- P6-04A adds the nullable `error_class` schema field;
- a failed disposable execution durably persists the expected deterministic class (`rate_limited` for the fixture);
- a successful disposable execution retains `error_class = NULL`;
- production static config and gateway PID identity remain unchanged;
- no production cron job executes and the production cron store is untouched.

Do not mark this gate PASS until the operator output is captured and reconciled.

## Remaining qualification before cutover

The following work remains after the current P6 runtime gate:

- approval/runtime behavior beyond session CRUD, without assuming source assertions equal runtime acceptance;
- Memory/profile-home boundary and persistence checks using isolated state only unless broader access is explicitly authorized;
- actual model-backed Chat behavior when live provider use is explicitly authorized, including session continuity, interruption/stop, and relevant long-session risk;
- actual Voice/STT/TTS/PTT qualification when live STT/TTS calls are explicitly authorized; v6 proved only API authentication and local validation;
- any remaining reported-issue relevance checks that intersect Orion, Memory, Voice, Chat, or Security;
- pre-cutover backup/rollback evidence;
- controlled production cutover only after explicit authorization;
- all five production hard gates after cutover: Orion lifecycle/runtime, Memory, Voice, Chat/session, and Security/authorization.

## Known qualification observations

Two failed qualification attempts were harness/observation findings rather than accepted candidate failures:

1. session/profile v1 timed out in a composite preflight identity-import subprocess before candidate launch;
2. session/profile v2 launched the candidate but missed the 90-second HTTP readiness boundary; its production mutation watcher also incorrectly treated volatile runtime metadata as a mutation oracle.

The corrected v3 harness removes those observer defects while retaining the 90-second startup acceptance boundary. The later startup diagnostic (8.285 s) and v3 session run (7.745 s) both started normally.

These observations remain documented because recurrence matters for lifecycle qualification.

## Authorization boundary

PR #81 remains **draft, pre-install, and fail-closed**.

This status does not authorize:

- `hermes update` against production;
- installing or cutting production over to v0.22.5;
- changing the accepted `companion` profile;
- changing iai, model/provider configuration, or credentials;
- copying production config/credentials into scratch state;
- persisting disposable API keys;
- using `--force` for candidate launch;
- launching a second Hermes dashboard/web process;
- merging PR #81;
- live model/STT/TTS calls without separate authorization;
- removing rollback evidence.

The next resume point is the operator result from `v0225_isolated_cron_compat_contract_smoke.py`.