# P6-UPG-03 — Hermes v0.21.5 Disposable Full Migration Rehearsal

Status: **PREPARED — DISPOSABLE ONLY**

Base Orion commit:

- P6-UPG-02 qualified compatibility head: `d15f0c3c54236a4aa1b855840dad2b39602244e9`

Target Hermes:

- tag `v2026.9.24`
- package `0.21.5`
- commit `f97608f178d1ffeca59860195ab7da295f7c8e5f`

Qualified Orion compatibility artifact:

- `compat/hermes/v2026.9.24-orion-minimal-compat.patch`
- SHA-256 `b0f0811f6411dff4d1faa0fbd19a04ad0414dfc3f846f25540dc75b4f8454d9c`

This ticket does not authorize a production Hermes update, COMPANION mutation,
gateway restart, live reminder, production pin change, or merge.

## Goal

Rehearse the migration to v0.21.5 against the real Windows risk classes already
identified upstream, using disposable state and a production-read-only topology
probe. The rehearsal should answer which risks require an Orion compatibility
delta and which are better handled as production-upgrade guards.

## Risk-led acceptance

### 1. Restart-safe external cron worker dependency path

Open upstream P1 reports #122529 and #129235 describe the same failure shape:
the gateway can run with runtime dependencies injected into its in-process
`sys.path`, while the external cron worker is launched using a dependency-light
base interpreter. v0.21.5's `cron/scheduler_worker_env.py` pins the repository
root into `PYTHONPATH` but does not pin the selected runtime venv site-packages.

The exact v0.21.5 source shows a Windows legacy/base-interpreter topology:

- `hermes_cli.gateway_windows` can launch the gateway with a base Python while
  setting `VIRTUAL_ENV=<repo>/venv` and a checkout `PYTHONPATH`;
- `tools/environments/local_pythonpath.py` explicitly recognizes that exact
  `<repo>/venv` producer shape and strips both the Hermes runtime
  `Lib/site-packages` path and active-venv markers from child environments;
- `cron/scheduler_worker_env.py` then counter-pins only the repository root,
  leaving a restart-safe worker launched under the base interpreter without
  third-party dependencies.

The documented defect is accepted as upstream evidence; P6-UPG-03 no longer
spends time re-proving the broken stock behavior. The rehearsal instead builds
the dependency venv at the exact target shape `<disposable-target>/venv`,
applies the reviewed upstream source fix from commit
`f57d2357485f1cc234e438b813e75c241a09c9e7`, and qualifies the patched
candidate directly.

That upstream commit closed #122222 four days after the target release. It
modifies the same v0.21.5 worker-env helper without depending on the later PM
package: it finds the activated dependency `site-packages` already present on
the parent process's `sys.path`, excludes the interpreter's own purelib,
requires a real `pyvenv.cfg` ancestor, and restores that path next to the
checkout for the Hermes worker.

The later PM-specific implementation superseded this upstream code on newer
Hermes architecture, but the earlier `f57d235` fix is the source-backed
backport appropriate to the exact pre-PM v0.21.5 target.

The upstream backport is carried as
`compat/hermes/v2026.9.24-upstream-f57d235-worker-env.patch` alongside the
already-qualified Orion compatibility patch. A PASS means the combined
candidate is ready for P6-UPG-04 review; it does not authorize production
mutation.

### 2. Single scheduler ownership / duplicate delivery

Run exact-tag focused tests for:

- `tests/cron/test_cron_multiplex_tick_ownership.py`
- `tests/cron/test_cron_multiplex_desktop_ticker_scope.py`

This targets the Windows duplicate-ticker class reported in #57191.

### 3. Ticker health / stale lock

Run exact-tag ticker-stall and lock-error regressions where available. The
production upgrade ticket must additionally verify that the ticker heartbeat
advances after the restarted gateway is live. A stale `.tick.lock` path is
never "fixed" by deleting the pathname; #129990 shows the held inode can remain
locked until process exit.

### 4. No update during active cron work

#129947 remains open. P6-UPG-03 treats "no active cron work" as an Orion upgrade
precondition instead of relying on the updater's drain budget. The production
upgrade ticket must refuse to proceed while an execution is claimed/running or
a scheduler-owned run is active.

### 5. Interrupted update completion marker

#127284 remains open. The production upgrade path must inspect for
`source-completion-pending` before and after update. Presence is a stop
condition requiring bounded diagnosis; ordinary CLI launches must not be used
as an implicit repair loop.

### 6. Gateway return on Windows

#129171 remains open. A successful updater message is not sufficient evidence
that the gateway returned. P6-UPG-04 must independently verify process/listener
ownership and gateway status after the controlled restart.

### 7. Gateway boot warm-up

#131145 remains open on v0.21.5. The exact source allows the inbound gate to
open after a bounded warm-up wait even when turn-machinery warm-up has not
completed. P6-UPG-04 must therefore treat the gateway as not fully accepted
until warm-up completion is observed or a bounded first-turn acceptance probe
succeeds. This cannot be fully proven in an offline disposable rehearsal without
the production provider/messaging topology.

### 8. Post-restart SQLite integrity

#110007 remains open. The production upgrade must run a fresh-connection
`PRAGMA integrity_check` after the restarted gateway is actually running,
rather than relying only on updater pre-restart checks.

The disposable rehearsal self-tests the integrity guard against both a valid
SQLite database and a deliberately invalid database image.

## P6-UPG-03 verdicts

The runner has two evidence states:

- `PASS` — exact Hermes v0.21.5 + P6-UPG-02 Orion compatibility +
  upstream `f57d235` worker-env backport passed focused qualification and
  production remained unchanged.
- `STOP` — unexpected source/state/test drift or a failed invariant.

Known upstream defects are treated as decision inputs; this ticket does not
require reproducing them again when the affected target source and reviewed
upstream fix are already established.

## Production boundary

P6-UPG-03 remains disposable. Even a full PASS does not authorize:

- changing the production Hermes pin;
- modifying installed Hermes;
- changing COMPANION files;
- stopping/restarting the production gateway;
- running a live reminder;
- merging the upgrade branch.
