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

### P6-03 / P6-04A isolated runtime compatibility contract — UNRESOLVED AFTER HARNESS TIMEOUT

The first runtime harness attempt used one monolithic child process with a 90-second timeout. The child timed out before the parent could recover phase-level evidence. Because stdout/stderr were captured inside `subprocess.run()` and the timeout path did not surface partial child output, the run does not establish whether the stall occurred during:

- `cron.jobs` import;
- `load_jobs()` repair/preservation;
- `cron.executions` import;
- execution ledger initialization/writes;
- SQLite verification.

The timeout therefore is classified as **HARNESS PHASE-LOCALIZATION FAILURE — P6 RUNTIME CONTRACT UNRESOLVED**, not as a P6-03 or P6-04A functional failure.

The v1 failure also exited before its normal production/candidate postcondition block. The child was constrained to a disposable `HERMES_HOME`, no gateway or external job was launched, and no provider calls were requested, but the failed run itself did not independently re-run the after-snapshots. Do not overstate its `PRODUCTION_CRON_STORE_TOUCHED=false` pre-run marker as a postcondition proof.

Observer-hardened replacement:

- `scripts/hermes_upgrade/v0225_isolated_cron_compat_contract_smoke_v2.py`

v2 changes only the observation method:

- P6-03 and P6-04A run in separate disposable child processes and separate scratch homes;
- each child prints flushed phase markers before and after imports and contract operations;
- each child has a bounded 45-second timeout rather than widening the prior 90-second monolith;
- timeout/failure output records the last completed phase;
- production static config, production gateway PID identity, health, and candidate-source invariance are checked after both children even when either child fails;
- no gateway, production cron job, model, memory, STT, or TTS provider call is authorized.

Do not mark either P6 runtime sub-gate PASS until v2 operator output is captured and reconciled.

## Remaining qualification before cutover

The following work remains after the current P6 runtime gate:

- approval/runtime behavior beyond session CRUD, without assuming source assertions equal runtime acceptance;
- Memory/profile-home boundary and persistence checks using isolated state only unless broader access is explicitly authorized;
- actual model-backed Chat behavior when live provider use is explicitly authorized, including session continuity, interruption/stop, and relevant long-session risk;
- actual P4-04A STT/TTS round-trip and Orion voice behavior when live STT/TTS use is explicitly authorized;
- production pre-cutover backup;
- controlled cutover;
- full five-hard-gate production requalification.

## Authorization boundary

PR #81 remains draft and pre-install. Completed isolated sub-gates do not authorize:

- `hermes update`;
- production Hermes install/upgrade/cutover;
- profile reset;
- iai change;
- provider/model change;
- production config/credential copy into scratch;
- live model/STT/TTS provider calls without separate approval;
- `--force` gateway launch;
- second Hermes dashboard/web process;
- production memory/runtime mutation;
- destructive database rewrite;
- PR merge.

Production acceptance remains on Hermes v0.20.6 until all required hard gates pass and cutover is separately authorized.
