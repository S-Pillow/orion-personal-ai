# Hermes v0.22.5 Cron Compatibility Smoke v2 Finding

Status: **COMMON IMPORT-PATH FAILURE BEFORE P6 LOGIC — P6-03 / P6-04A RUNTIME STATUS UNRESOLVED**

Observed: 2026-10-31

Candidate: `bf0203a794a07aac3ff764972ab9087baa4e4f4e` (`v0.22.5`)

Harness tooling head used by operator: `9a4b2b04fdd75a4fa548b06f5eb49ee2f9e22da9`

## Result

The observer-hardened v2 cron compatibility smoke successfully localized the v1 timeout to a common import boundary. It did **not** reach either compatibility function under test.

### P6-03 child

The child completed scratch setup and then failed while executing:

`from cron import jobs as jobs_mod`

Last phase marker:

`P603_IMPORT_JOBS_BEGIN`

Observed path:

`cron.__init__ -> cron.scheduler -> cron.scheduler_delivery -> asyncio`

The standard-library `asyncio` import failed with:

`NameError: name 'base_events' is not defined`

The child exited in approximately 3.149 seconds. `jobs_mod.load_jobs()` was never called, so this run provides no functional evidence for or against P6-03 exact pre-repair preservation.

### P6-04A child

The child completed scratch setup and then failed while executing:

`from cron import executions as exec_mod`

Last phase marker:

`P604A_IMPORT_EXECUTIONS_BEGIN`

It reached the same common package-import path and the same standard-library `asyncio` failure:

`cron.__init__ -> cron.scheduler -> cron.scheduler_delivery -> asyncio`

The child exited in approximately 2.921 seconds. No execution-ledger row was created, transitioned, finalized, or queried, so this run provides no functional evidence for or against P6-04A durable `error_class` persistence.

## Candidate vs harness interpretation

The v2 result is more specific than v1 but still does not justify rejecting P6-03 or P6-04A. Both failures occur before their contract operations execute.

The current evidence supports only this narrower statement:

> The isolated child topology used by the P6 runtime harness cannot currently complete the exact candidate's `cron` package import because the import chain reaches a failing Windows `asyncio` initialization.

The exact cause is not yet established. Candidate gateway qualification previously launched successfully with the same isolated runtime Python, so a globally unusable Python runtime is not established. The remaining possibilities include environment-sensitive interpreter behavior, import-order/bootstrap interaction, or another Windows runtime/import condition.

Upstream Hermes issue `#56503` documents the same `asyncio` `NameError: base_events` error signature when `subprocess.Popen` is replaced before asyncio initializes. That is relevant prior evidence, but it is **not** treated as the root cause here without local reproduction. Exact v0.22.5 `_subprocess_compat.py` does not itself contain the later global `patch_subprocess_no_window()` mechanism described in that issue.

## Production and candidate postconditions

Unlike v1, v2 completed its after-state observations despite the child failures:

- production API health after: `HTTP_200|status=ok`;
- production static configuration unchanged: **PASS**;
- production gateway PID identity unchanged: **PASS**;
- candidate Git status unchanged: **PASS**;
- gateway launched by this harness: **false**;
- production cron job executed: **false**;
- model provider calls: **0**;
- memory calls: **0**;
- STT provider calls: **0**;
- TTS provider calls: **0**.

No production mutation or runtime restart is evidenced by this run.

## Next bounded oracle

Do not rerun the P6 functional harness yet.

Run:

`scripts/hermes_upgrade/v0225_windows_asyncio_import_diagnostic.py`

The diagnostic compares:

1. direct `asyncio` import under the existing scrubbed child environment;
2. direct `asyncio` import under a runtime-preserving inherited environment with sensitive credential variables removed;
3. `cron.jobs` import under both environments;
4. `cron.jobs` import after explicitly pre-importing `asyncio` under both environments.

It records whether `subprocess.Popen` is still a class before asyncio import, reports only environment-variable **presence** for interpreter-sensitive variables, prints no credential values, launches no gateway, invokes no provider, and rechecks production/candidate postconditions.

The next P6 harness correction must be based on that result rather than bypassing `cron.__init__`, widening timeouts, or assuming the upstream issue is identical.
