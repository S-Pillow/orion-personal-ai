# P5-02K — Persist Production Recovery Root with Mutation Disabled

Status: **OWNER AUTHORIZED / PERSISTENT COMPANION ENV CHANGE PENDING**

Branch:

```text
feature/orion-phase5-p5-02k-persist-recovery-root
```

Depends on:

- P5-02J production recovery-root creation + ACL acceptance — complete;
- accepted root:
  `C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery`;
- installed COMPANION Orion plugin remains the accepted P5-02I build;
- production mutation mode remains disabled;
- registered apply remains fail-closed.

## Purpose

P5-02K persists only the accepted recovery-root location into the COMPANION
profile environment:

```text
ORION_P5_PRODUCTION_RECOVERY_ROOT=C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery
```

This makes the recovery-root location durable across later COMPANION process
starts without enabling mutation.

P5-02K does **not** persist or enable:

```text
ORION_P5_MUTATION_MODE
ORION_P5_ALLOW_DISPOSABLE_MUTATION
ORION_P5_RECOVERY_ROOT
```

With `ORION_P5_MUTATION_MODE` absent, the installed plugin continues to resolve
production mutation mode as `disabled`.

## Owner authorization

Owner explicitly authorized:

```text
Persist ORION_P5_PRODUCTION_RECOVERY_ROOT=
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery
in the COMPANION .env while keeping production mutation mode disabled.
```

Authorized live actions are limited to the P5-02K execution boundary in this
runbook.

The authorization permits:

- byte-for-byte rollback capture of the COMPANION `.env`;
- append-only persistence of exactly the accepted production recovery-root
  assignment;
- post-write verification and rollback on failure.

The authorization does **not** permit:

- persisting or enabling `ORION_P5_MUTATION_MODE`;
- starting/restarting Hermes;
- registering the private production executor;
- changing vault/inbox ACLs;
- mutating real vault/inbox content;
- merge/deploy.

Operator source pin:

```text
179840b4ba67ba3dbba6728a542a52378d824fa8
scripts/phase5/p5-02k-persist-production-recovery-root.ps1
```

The live run must execute that exact source pin or an identical script hash.

## Persistent target

COMPANION environment file:

```text
C:\Users\spill\AppData\Local\hermes\profiles\companion\.env
```

The file is sensitive and must never be printed or included in logs.

## Change strategy

The prepared gate is intentionally append-only.

Before mutation it must:

- require Hermes manual-off;
- verify accepted COMPANION `config.yaml` SHA-256;
- verify accepted installed plugin `__init__.py` SHA-256;
- verify the accepted production recovery root exists;
- re-run P5-02J native root/inventory validation with mutation mode disabled;
- verify `ORION_P5_PRODUCTION_RECOVERY_ROOT` is absent from the current
  COMPANION `.env`;
- verify mutation/disposable variables remain absent from both the current
  process and persistent `.env`;
- capture a byte-for-byte rollback copy of `.env` when it exists, or record
  that it was absent.

The gate then appends exactly one assignment for
`ORION_P5_PRODUCTION_RECOVERY_ROOT`.

It must not normalize, sort, rewrite, or print existing `.env` content.

## Rollback

A timestamped backup directory is created under:

```text
%LOCALAPPDATA%\hermes\profiles\companion\orion\backups
```

If `.env` existed, its exact bytes are copied to:

```text
p5-02k-env-<timestamp>\.env.before
```

Metadata may record only non-secret facts such as:

- whether `.env` existed;
- its SHA-256 before/after;
- config SHA-256;
- installed plugin SHA-256;
- accepted recovery-root path;
- timestamp.

No environment contents may be written into metadata.

If post-change verification fails:

- restore the exact backup bytes when `.env` previously existed;
- delete the newly created `.env` only when it did not previously exist;
- preserve the backup directory for audit;
- do not start Hermes as a diagnostic.

## Post-change verification

The gate must verify without printing `.env`:

- exactly one active
  `ORION_P5_PRODUCTION_RECOVERY_ROOT` assignment exists;
- its value exactly equals the P5-02J accepted path;
- `ORION_P5_MUTATION_MODE` remains absent;
- disposable mutation variables remain absent;
- `config.yaml` remains byte-for-byte unchanged;
- installed plugin hash remains unchanged;
- recovery root still exists;
- recovery root remains empty;
- native root validation still passes when process-scoped to the same value;
- production mutation resolves to `disabled`;
- registered apply remains fail-closed;
- Hermes remains manual-off.

P5-02K does not start/restart Hermes. Runtime ingestion of the newly persisted
setting is a later gate.

## Explicitly out of scope

P5-02K does not authorize:

- `ORION_P5_MUTATION_MODE=mutation_enabled`;
- any non-disabled persistent mutation mode;
- registration of `_execute_production_plan_candidate`;
- replacement of `apply_plan_placeholder`;
- Hermes start/restart;
- vault/inbox ACL changes;
- real vault/inbox mutation;
- creation of a recovery transaction;
- merge/deploy;
- Hermes/Ollama/iai upgrade.

## Prepared operator artifact

Prepared source pin:

```text
179840b4ba67ba3dbba6728a542a52378d824fa8
scripts/phase5/p5-02k-persist-production-recovery-root.ps1
```

The branch delta from completed P5-02J is limited to this runbook and the
operator script. No plugin source, manifest, live COMPANION configuration, or
runtime file has been changed by source-only preparation.

The operator script requires the literal authorization token:

```text
I_AUTHORIZE_P5_02K_PERSIST_RECOVERY_ROOT
```

and fails closed without it.

The script never prints `.env` contents. It preserves existing bytes and
appends only the accepted recovery-root assignment, with exact rollback bytes
captured first.

## Acceptance markers

A successful authorized run must report:

```text
P5_02K_ROLLBACK_CAPTURED=true
P5_02K_ENV_APPEND_ONLY=true
P5_02K_RECOVERY_ROOT_ASSIGNMENT_COUNT=1
P5_02K_RECOVERY_ROOT_VALUE_MATCH=true
P5_02K_MUTATION_MODE_PERSISTED=false
P5_02K_DISPOSABLE_FLAGS_PERSISTED=false
P5_02K_NATIVE_ROOT_VALIDATION=PASS
PRODUCTION_MUTATION_MODE=disabled
PRODUCTION_MUTATION_ALLOWED=false
P5_02K_RECOVERY_INVENTORY_COUNT=0
P5_02K_CONFIG_UNCHANGED=true
P5_02K_PLUGIN_UNCHANGED=true
HERMES_MANUAL_OFF=true
P5_02K_PERSIST_RECOVERY_ROOT=PASS
```

## Next gate after P5-02K

If P5-02K passes, the next gate should start COMPANION under explicit lifecycle
authorization and verify that the runtime actually ingests the persisted
recovery-root setting while mutation mode remains disabled and registered apply
remains fail-closed.

That runtime start/stop is separately authorization-gated.
