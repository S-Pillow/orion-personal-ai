# Hermes v0.22.5 Qualification Status

Status: **PRE-INSTALL QUALIFICATION — ACTIVE**

Last updated: 2026-10-31

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

### P6-03 / P6-04A isolated runtime compatibility contract — UNRESOLVED AT COMMON CRON IMPORT BOUNDARY

The phase-instrumented v2 runtime harness resolved the earlier v1 timeout ambiguity but did not reach either P6 compatibility operation.

P6-03 child:

- scratch setup completed;
- failure occurred at `P603_IMPORT_JOBS_BEGIN` while executing `from cron import jobs as jobs_mod`;
- exact import chain reached `cron.__init__ -> cron.scheduler -> cron.scheduler_delivery -> asyncio`;
- standard-library asyncio failed with `NameError: name 'base_events' is not defined`;
- child exited in approximately 3.149 seconds;
- `jobs_mod.load_jobs()` was never called.

P6-04A child:

- scratch setup completed;
- failure occurred at `P604A_IMPORT_EXECUTIONS_BEGIN` while executing `from cron import executions as exec_mod`;
- it reached the same `cron.__init__ -> cron.scheduler -> cron.scheduler_delivery -> asyncio` failure;
- child exited in approximately 2.921 seconds;
- no execution-ledger row was created or finalized.

Therefore neither P6-03 nor P6-04A has failed functionally. Their runtime status remains unresolved because both probes stop before the code under test executes.

v2 did complete its after-state observations:

- production API health after: `HTTP_200|status=ok`;
- production static configuration unchanged: **PASS**;
- production gateway PID identity unchanged: **PASS**;
- candidate Git status unchanged: **PASS**;
- no gateway launched by the harness;
- no production cron job executed;
- model/memory/STT/TTS provider calls remained zero.

Evidence:

- `docs/hermes/hermes-v0225-cron-compat-smoke-v1-finding-2026-10-30.md`
- `docs/hermes/hermes-v0225-cron-compat-smoke-v2-finding-2026-10-31.md`

A relevant upstream Hermes report, issue `#56503`, documents the same Windows asyncio `NameError: base_events` error signature when `subprocess.Popen` is replaced before asyncio initializes. That report is useful prior evidence but is **not** yet accepted as the local root cause. Exact v0.22.5 `_subprocess_compat.py` does not itself contain the later global `patch_subprocess_no_window()` mechanism described in that issue.

Next bounded diagnostic:

- `scripts/hermes_upgrade/v0225_windows_asyncio_import_diagnostic.py`

This diagnostic must determine whether the failure follows the scrubbed qualification environment, direct asyncio import, the cron package import path, or import ordering. It compares direct asyncio and `cron.jobs` imports under both the existing scrubbed child environment and a runtime-preserving inherited environment with sensitive credential variables removed. It also checks whether explicitly pre-importing asyncio changes the cron import result and records whether `subprocess.Popen` is still a class before asyncio import.

Do **not** rerun the P6 functional harness until this import diagnostic is reconciled. Do not bypass `cron.__init__`, widen timeouts, or assume the upstream issue is identical without local evidence.

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
