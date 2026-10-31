# Hermes v0.22.5 Cron Compatibility Smoke v1 Finding

Status: **HARNESS PHASE-LOCALIZATION FAILURE — P6 RUNTIME CONTRACT UNRESOLVED**

Date: 2026-10-30

Candidate:

- Hermes v0.22.5 exact release commit `bf0203a794a07aac3ff764972ab9087baa4e4f4e`
- tooling head executed by the operator: `027772c60dfc36b4fa613dca06c6ce91d937625b`

## Observed result

The isolated P6-03 / P6-04A runtime harness started with a disposable `HERMES_HOME`, no gateway launch, no production cron job execution, and zero model/memory/STT/TTS calls requested. The single child process then exceeded the harness's 90-second timeout.

The parent raised `subprocess.TimeoutExpired` from the monolithic child invocation.

Because v1 used `subprocess.run(..., capture_output=True, timeout=90)` and did not expose partial child stdout on the timeout path, the operator output contains no reliable phase marker proving whether the child had reached or completed any of these operations:

1. import `cron.jobs`;
2. `load_jobs()` repair + P6-03 recovery preservation;
3. import `cron.executions`;
4. P6-04A execution ledger creation/terminal writes;
5. read-only SQLite verification.

Therefore the result is **not evidence that P6-03 failed** and is **not evidence that P6-04A failed**.

## Postcondition limitation

v1 performed production static-config, gateway-PID, health, and candidate-source after-snapshots only after `_run_contract()` returned. The timeout raised before that block executed.

The child environment was scrubbed and forced to the disposable `HERMES_HOME`, and the harness launched no gateway or external cron job, but the failed v1 attempt itself did not independently re-run its after-snapshot assertions. Its pre-run `PRODUCTION_CRON_STORE_TOUCHED=false` marker must not be treated as a completed postcondition proof.

## Observer correction

The replacement harness is:

- `scripts/hermes_upgrade/v0225_isolated_cron_compat_contract_smoke_v2.py`

v2 changes the observation method rather than relaxing the functional contract:

- P6-03 and P6-04A execute in separate child processes and separate disposable homes;
- each child emits flushed phase markers before/after imports and contract operations;
- each child has a bounded 45-second timeout;
- timeout/failure output records the last completed phase;
- both children are attempted independently so one unresolved sub-gate does not erase evidence for the other;
- production static config, production gateway PID identity, production health, and candidate-source invariance are checked after both children even when either child fails.

## Qualification state

The P6-03 / P6-04A isolated runtime gate remains **UNRESOLVED**.

Do not rerun v1 as a qualification oracle. Run v2 once, capture the complete output, and classify each sub-gate from its phase evidence.

No production cutover, provider use, profile reset, iai change, model/provider change, destructive database rewrite, or PR merge is authorized by this finding.
