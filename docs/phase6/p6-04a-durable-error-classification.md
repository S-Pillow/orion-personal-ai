# P6-04A Durable Error Classification Delta

Status: **DISPOSABLE GENERATION / QUALIFICATION PREPARED - INSTALLED HERMES NOT AUTHORIZED**

Prepared: 2026-10-01

Controlling requirement: OR-REM-009 requires each reminder/scheduled execution to retain
bounded run evidence including error/failure classification where applicable.

## Research result

Accepted Hermes currently classifies cron failures in
`agent/monitoring/cron_health.py::classify_cron_error()`, but that value is projected
only into monitoring events. The durable execution ledger stores raw `error` text and,
after P6-04, also stores `scheduled_at` and `delivery_outcome`. It does not retain
`error_class`.

The existing classifier categories are:

- `auth_failed`
- `rate_limited`
- `timeout`
- `network_error`
- `dispatch_failed`
- `interrupted`
- `empty_response`
- `invalid_config`
- `unknown`

Importing `agent.monitoring.cron_health` directly from `cron.executions` would create
an avoidable dependency cycle because `cron_health.py` imports
`cron.scheduler.get_running_job_ids`, while `cron.scheduler` imports
`cron.executions`.

The narrow design therefore extracts the existing classifier unchanged into a neutral,
dependency-light `cron/error_classification.py` module. Both the monitoring projection
and durable execution ledger import that same classifier, preserving one classification
grammar rather than duplicating rules.

## Planned source delta

Disposable P6-04A changes exactly:

- `cron/error_classification.py` - new shared classifier module containing the existing
  classification semantics;
- `agent/monitoring/cron_health.py` - imports and re-exports the shared classifier instead
  of defining a second implementation;
- `cron/executions.py` - adds nullable `error_class TEXT`, idempotent additive migration,
  durable classification for failed terminal writes, and durable `interrupted`
  classification for recovered abandoned executions.

Successful executions retain `error_class = NULL`.

Historical rows migrated from the P6-04 schema also retain `NULL`; P6-04A does not
retroactively guess classifications for prior rows. New failed/unknown terminal writes
receive the classifier result at the same transaction that writes terminal status/error.

## Qualification strategy

The generation gate creates a disposable local clone from the installed Hermes repository,
forces deterministic Git line-ending behavior inside that clone, checks out the accepted
Hermes pin, and applies the already qualified P6-03 and P6-04 patches. That state is
committed as the disposable qualification baseline. After the P6-04A transform and direct
qualification pass, the exact three-file candidate is committed separately and the
installation patch is generated commit-to-commit with Git using `--binary --full-index`.
A second disposable clone checks out the baseline commit, applies the generated patch,
and must reproduce the exact already-tested source hashes. This avoids archive/re-init
worktrees, `git add -N`, and dependence on global Windows CRLF settings.

COMPANION safety is verified using authoritative logical state from the existing read-only
production-state probe: job count, execution-row count, execution schema, and read-only
SQLite access. Volatile ticker-heartbeat timestamps and generic cron-directory metadata
are intentionally excluded because a healthy live scheduler is expected to update them.

Qualification requires:

1. exact accepted Hermes pin and current installed P6-03/P6-04 source hashes;
2. no installed Hermes, COMPANION, or live-job mutation;
3. exactly three changed source paths;
4. Python compile success for the new shared classifier, execution ledger, and monitoring
   projection;
5. classifier semantic parity across all current categories;
6. failed terminal rows retain raw error plus durable `error_class`;
7. successful rows keep `error_class=NULL`;
8. recovered interrupted rows persist `error_class=interrupted`;
9. terminal immutability remains intact;
10. migration from the current P6-04 schema adds only nullable `error_class` and preserves
    historical rows;
11. the Git-generated commit-to-commit patch applies cleanly to a fresh checkout of the
    disposable P6-03/P6-04 baseline commit and reproduces exact tested source hashes;
12. full P6-04 durable-run-evidence regression remains green;
13. full P6-03 corruption-preservation regression remains green;
14. external network attempts remain zero;
15. installed Hermes HEAD/status/source hashes remain unchanged; and
16. COMPANION logical job count, execution row count, and execution schema remain unchanged
    while volatile heartbeat metadata is allowed to advance normally.

Prepared artifacts:

- `scripts/phase6/p6-04a-build-disposable-source.py`
- `scripts/phase6/p6-04a-disposable-error-classification-qualification.py`
- `scripts/phase6/Invoke-P6-04A-GenerateAndQualifyPatch.ps1`

Running the generation gate is disposable only. It does not authorize installing the
resulting patch, restarting the gateway, changing COMPANION state, or creating a reminder.
