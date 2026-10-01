# P6-04 Production Application Plan - Durable Run Evidence

Status: **APPLICATION PREPARED / INSTALLED HERMES MUTATION NOT YET AUTHORIZED**

Prepared: 2026-10-01

Accepted Hermes pin: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

Qualified P6-03 installed `cron/jobs.py` SHA-256:
`3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5`

Qualified P6-04 patch:

- path: `compat/hermes/p6-04-durable-run-evidence.patch`
- Git blob: `31c1127e032b0a7ea09ecfd92ed3eaa1d5b0542f`
- SHA-256: `abe54cd59e217f60c01fd8ae68e1cfb1782b7267ff7b98a035b4481f66f787ed`

Qualified installed-source target hashes after patch:

- `cron/executions.py`: `a7a146921af20f97594258f4672c68e0c4955e7c1a1b361e857be8b4e470d208`
- `cron/scheduler.py`: `6c0a43c175aab8e7d2a0107f6b067bcfa42f9a55650ab8cc761824c37fb02bfe`

## Research conclusions before preparation

The production application unit follows the already accepted P6-03 source-application
pattern, but P6-04 has two additional constraints.

First, the accepted Hermes execution ledger initializes schema inside every
`_transaction()`. The P6-04 migration therefore becomes live only when a process using
the patched `cron.executions` module opens a ledger transaction. Copying the source files
alone does not require or justify touching COMPANION `executions.db`.

Second, the running COMPANION gateway may continue using modules already loaded before the
source change. Source application and live activation are therefore separate authorization
boundaries. P6-04 source application must leave the current gateway running and must prove
the live COMPANION schema remains at the pre-P6-04 columns until a later bounded activation.

Git application policy for this unit:

- both target worktree files must still match the accepted pinned Git objects;
- the exact qualified patch Git blob and SHA-256 must match;
- patch scope must be exactly `cron/executions.py` and `cron/scheduler.py`;
- `git apply --check` must pass immediately before source mutation;
- no `--3way`, reject-file, whitespace-fix or fuzzy recovery path is allowed;
- any target drift is a stop condition, not something to merge around.

SQLite migration policy:

- the source change uses only additive nullable `ALTER TABLE ... ADD COLUMN` operations;
- existing execution rows are preserved;
- no table rebuild/drop is used;
- `PRAGMA table_info(executions)` is used to make migration idempotent;
- source application itself does not open the COMPANION ledger through patched Hermes code.

## Prepared gates

Read-only preflight:

`scripts/phase6/Invoke-P6-04-ProductionApplyPreflight.ps1`

This gate verifies:

1. Orion branch is correct and clean.
2. P6-04 patch Git blob, SHA-256 and LF policy match the qualified artifact.
3. Hermes HEAD is the accepted pin.
4. Installed Hermes dirty state is exactly the accepted P4/P5 artifacts plus P6-03
   `cron/jobs.py`.
5. P6-03 `cron/jobs.py` retains its accepted hash.
6. `cron/executions.py` and `cron/scheduler.py` still match the accepted pinned Git
   objects.
7. COMPANION has zero reminder jobs.
8. COMPANION execution ledger has zero rows and the original pre-P6-04 schema.
9. Ledger inspection uses SQLite read-only mode.
10. `git apply --check` passes against the installed checkout.
11. Orion, Hermes and COMPANION logical state remain unchanged.

Production source-application gate:

`scripts/phase6/Invoke-P6-04-ProductionSourceApply.ps1`

This gate is prepared but **must not be run without separate explicit owner authorization**.

When authorized, it will:

1. repeat all identity and drift gates;
2. create exact-byte external backups of both target source files under
   `%LOCALAPPDATA%\hermes\orion-compat-backups\p6-04-<timestamp>\`;
3. create a manifest containing original hashes, expected patched hashes, Hermes head,
   Orion head and patch identities;
4. rerun `git apply --check`;
5. apply only the exact qualified patch;
6. require exact qualified SHA-256 values for both patched target files;
7. require Hermes dirty scope to add only `cron/executions.py` and
   `cron/scheduler.py`;
8. compile both patched modules to temporary bytecode targets;
9. run full P6-04 qualification against installed source with a disposable
   `HERMES_HOME`;
10. rerun the P6-03 corruption-preservation qualification against the combined installed
    source using a second disposable home;
11. verify COMPANION still has zero jobs, zero execution rows and the old schema;
12. leave the live gateway untouched;
13. roll back both target files byte-for-byte if a post-apply gate fails.

## Explicit non-authorizations

Preparation and source application do not authorize:

- a gateway restart/start/stop;
- creation, editing, running or deletion of a live reminder;
- migration testing by directly writing COMPANION `executions.db`;
- Hermes upgrade;
- Git reset/clean/stash of accepted compatibility changes;
- changes to `cron/jobs.py`, gateway compatibility files, Scheduled Tasks or Startup
  persistence;
- P6-05 implementation.

## Later live-activation boundary

After source application is separately accepted, a later P6-04 activation unit must
reconcile the running gateway and use Hermes' own Windows lifecycle path.

On the first patched execution-ledger transaction after activation,
`_initialize_schema()` is expected to add `scheduled_at` and
`delivery_outcome` to the existing COMPANION `executions` table.

Live activation acceptance must verify the two columns exist afterward, existing row count
remains correct, no reminder is created merely to force migration, and the gateway/ticker
is healthy. A live reminder belongs to the later P6-06 acceptance matrix rather than the
source-application step.
