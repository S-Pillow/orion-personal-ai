# P6-03 Production Application Plan - Installed Hermes Compatibility Patch

Status: **PLAN AUTHORIZED / INSTALLED HERMES MUTATION NOT YET AUTHORIZED**

Prepared: 2026-09-30  
Controlling PRD: ORION Master PRD v2.9  
Accepted Hermes pin: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`  
Qualified Orion head before this plan: `1c717a72eaa10647678a073060efb29cfdc9ca58`  
Qualified patch: `compat/hermes/p6-03-jobs-corruption-preservation.patch`  
Qualified patch Git blob: `539651113098298e3f45241636701bd25d7893ef`

## 1. Authorization boundary

The owner authorized preparation of the production application plan for the installed
Hermes checkout.

That authorization permits Orion repository planning artifacts and read-only
qualification of the installed checkout. It does **not** yet authorize:

- modifying installed Hermes source;
- modifying the COMPANION profile or cron state;
- creating or running a reminder;
- restarting or stopping Hermes/gateway processes;
- changing the accepted Hermes pin;
- upgrading Hermes;
- cleaning, resetting or stashing the accepted Hermes compatibility artifacts.

A later explicit production-apply authorization is required before `cron/jobs.py`
in the installed Hermes checkout may be changed.

## 2. Frozen production target

Installed Hermes root:

`%LOCALAPPDATA%\hermes\hermes-agent`

Required HEAD:

`5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

Accepted pre-existing worktree state:

```text
 M gateway/platforms/api_server.py
?? gateway/platforms/api_server.py.orion-p4-04a.bak
?? gateway/platforms/api_server.py.orion-p4-04a.json
?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak
?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json
```

The P6-03 target `cron/jobs.py` must still match the accepted pinned Git object
before production application. Any pre-existing change to `cron/jobs.py` is a
stop condition.

## 3. Qualified mutation

The only planned installed-Hermes source mutation is application of the qualified
P6-03 patch to:

`cron/jobs.py`

The patch must not touch `gateway/platforms/api_server.py`, COMPANION runtime
files, configuration, scheduler data, execution ledger, or any other vendor source.

The patch preserves the accepted architecture:

- Hermes remains the only scheduler owner.
- Hermes remains authoritative for due computation, locking, dispatch and storage.
- Orion adds no daemon, queue, scheduler or direct `jobs.json` writer.
- P6-03 only adds pre-repair forensic preservation to Hermes' existing load/repair path.

## 4. Required read-only production preflight

Before mutation, the operator must run
`scripts/phase6/Invoke-P6-03-ProductionApplyPreflight.ps1`.

The preflight must prove:

1. Orion is on the expected prep branch and clean.
2. Installed Hermes HEAD is the accepted pin.
3. Installed Hermes worktree is exactly the accepted compatibility-artifact state.
4. `cron/jobs.py` matches the accepted HEAD blob and has no local modification.
5. The source-controlled patch is governed by `eol=lf`.
6. A disposable LF-normalized patch copy passes `git apply --check` against the installed checkout.
7. The patch declares only `cron/jobs.py` as a target.
8. COMPANION cron metadata is captured and unchanged.
9. No scheduler, job, network or runtime mutation occurs.

Any failed condition stops the ticket before production source mutation.

## 5. Planned production application sequence

After a separate explicit production-apply authorization:

1. Re-run the read-only production preflight immediately before mutation.
2. Create a timestamped backup directory **outside the Hermes Git checkout** under:
   `%LOCALAPPDATA%\hermes\orion-compat-backups\p6-03-<timestamp>\`.
3. Copy the exact pre-patch `cron/jobs.py` bytes into that directory.
4. Record a small manifest containing:
   - accepted Hermes HEAD;
   - original `cron/jobs.py` SHA-256;
   - qualified patch Git blob;
   - timestamp;
   - target relative path.
5. Apply an LF-normalized copy of the qualified patch with `git apply`.
6. Verify the changed tracked-file set adds only `cron/jobs.py` beyond the already accepted
   `gateway/platforms/api_server.py` modification.
7. Run `py_compile` on installed `cron/jobs.py`.
8. Run the existing P6-03 qualifier against the **installed patched source** while binding it
   to a disposable `HERMES_HOME`; no COMPANION store may be used.
9. Verify the installed source still reports the accepted Git HEAD. The intended post-apply
   worktree delta is a local compatibility modification to `cron/jobs.py`; the vendor pin
   itself does not move.
10. Verify COMPANION cron metadata remains unchanged.

The source-application unit stops at this point. Live activation/restart is a separate gate.

## 6. Live activation boundary

Because a running Python gateway may already have `cron.jobs` imported, source application
alone does not prove the live process is using the patch.

Before any restart or activation:

- identify the exact owner/supervisor of the active COMPANION Hermes gateway;
- capture its current process/supervisor state read-only;
- define the exact bounded restart command;
- obtain separate restart authorization;
- do not alter existing manual-off semantics.

No reminder creation or live corrupt-store test is required for source application.

## 7. Rollback

If source application or disposable post-apply qualification fails before activation:

1. restore `cron/jobs.py` from the external byte-for-byte backup;
2. verify its SHA-256 equals the recorded original hash;
3. verify Hermes HEAD remains the accepted pin;
4. verify the worktree has returned to the exact pre-P6-03 accepted state;
5. verify COMPANION cron metadata is unchanged;
6. preserve the failed temporary qualification evidence for review.

If activation has already occurred, rollback additionally requires a separately authorized
bounded restart so the restored source is loaded.

## 8. Production acceptance for the source-application unit

The production source-application unit is accepted only when all of the following are true:

- exact accepted Hermes pin retained;
- pre-existing compatibility artifacts retained untouched;
- only `cron/jobs.py` is newly modified;
- installed `cron/jobs.py` compiles;
- source-controlled patch equivalence is proven;
- full revised P6-03 disposable fixture suite passes using installed patched source;
- Orion repository remains unchanged during the local production operation;
- COMPANION cron state remains unchanged;
- no external network request, scheduler start or reminder execution occurs;
- external rollback backup and manifest exist.

This acceptance does not itself prove live gateway activation. That is a later explicit gate.
