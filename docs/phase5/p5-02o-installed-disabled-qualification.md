# P5-02O — Installed-but-Disabled Qualification

Status: **PASS / INSTALLED-BUT-DISABLED QUALIFICATION ACCEPTED / MUTATION STILL DISABLED / HERMES MANUAL-OFF RESTORED**

Date: 2026-09-23

Branch:

```text
feature/orion-phase5-p5-02o-installed-disabled-qualification
```

Accepted P5-02N qualified code head:

```text
faf8b4787d8e6fb668eb5e9d754104910b4b401a
```

Depends on:

- P5-02N source-only acceptance;
- installed/runtime state accepted through P5-02L;
- COMPANION config SHA-256
  `34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7`;
- installed pre-P5-02O plugin `__init__.py` SHA-256
  `FCFA3DDC4A86B99691FB003CF4421027C5CC3CA22AC99ADBCCEEE8D3B3C7B5DA`;
- persisted production recovery root
  `C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery`;
- production mutation mode absent and therefore resolved as `disabled`;
- Hermes manual-off baseline.

## Purpose

P5-02O installs the exact P5-02N-qualified plugin source into the COMPANION
profile while production mutation remains disabled.

The gate proves:

- rollback exists before plugin replacement;
- the installed plugin bytes come from the exact accepted P5-02N source pin;
- installed plugin doctor succeeds;
- the registered public apply handler is
  `apply_plan_production_guarded`;
- the private production executor remains unregistered;
- the public apply schema remains `plan_token`-only;
- disabled `pre_tool_call` blocks without an approval rule;
- disabled public apply returns `production_mutation_not_enabled`;
- disabled public apply does not enter the private production executor;
- disabled verification creates no approval-attempt state;
- the live COMPANION toolset remains exactly four Orion vault tools;
- production recovery inventory remains empty;
- COMPANION config and `.env` bytes remain unchanged;
- Hermes returns to manual-off.

## Owner authorization

The owner explicitly authorized P5-02O after accepting P5-02N.

Authorized live actions:

- capture exact rollback copies of the installed plugin, COMPANION
  `config.yaml`, and COMPANION `.env`;
- create a temporary detached Git worktree at the exact accepted P5-02N code
  head;
- replace only the installed `orion-vault-actions` plugin directory with the
  exact accepted source;
- run source and installed-location plugin doctor;
- start only the COMPANION Hermes gateway;
- run the installed-but-disabled verifier;
- stop COMPANION and return Hermes to manual-off;
- automatically restore the prior plugin/config/environment bytes if the gate
  fails after installation starts.

Not authorized:

- persisting or setting `ORION_P5_MUTATION_MODE`;
- `mutation_enabled`;
- production mutation invocation;
- real vault/inbox edit, move, restore, or delete;
- production recovery transaction creation;
- recovery-record deletion;
- vault/inbox/recovery ACL changes;
- COMPANION config changes;
- COMPANION `.env` changes;
- plugin capability expansion;
- Hermes/Ollama/iai upgrades;
- login-startup changes.

## Exact source installation

The operator gate creates a detached worktree at exactly:

```text
faf8b4787d8e6fb668eb5e9d754104910b4b401a
```

and copies only:

```text
hermes_plugins\orion-vault-actions
```

from that worktree into:

```text
%LOCALAPPDATA%\hermes\profiles\companion\plugins\orion-vault-actions
```

The current documentation/operator branch is not treated as the install source.
This prevents documentation-only commits after qualification from silently
changing the installed source pin.

## Rollback

Before plugin replacement, the gate creates a timestamped directory under:

```text
%LOCALAPPDATA%\hermes\profiles\companion\orion\backups
```

containing:

- exact prior plugin directory;
- exact `config.yaml` bytes;
- exact `.env` bytes;
- non-secret metadata containing hashes and source pins.

The `.env` contents are never printed.

If a failure occurs after plugin replacement begins, the gate:

1. stops COMPANION if a gateway start was issued;
2. restores the prior plugin directory;
3. restores exact `config.yaml` bytes;
4. restores exact `.env` bytes;
5. verifies the prior hashes;
6. leaves production recovery evidence untouched;
7. preserves the backup directory.

A failure with `P5_02O_ROLLBACK_RESTORED=false` is a hard stop requiring
manual inspection before any retry.

## Runtime verifier

The verifier loads the installed plugin directly and checks the registered
surface while the live COMPANION gateway is healthy.

For the disabled-apply proof it creates only a temporary disposable vault/inbox
under the OS temporary directory. It creates one temporary note solely to
obtain a valid preview token, then verifies:

- `pre_tool_call` returns `block` with no approval rule key;
- `apply_plan_production_guarded` returns
  `production_mutation_not_enabled`;
- a sentinel private executor is never reached;
- approval-attempt state does not increase;
- the temporary note bytes remain unchanged.

No real vault or inbox path is used for this check.

## Prepared operator artifacts

```text
scripts/phase5/p5-02o-installed-disabled-gate.ps1
scripts/phase5/p5-02o-installed-disabled-verify.py
```

The operator gate requires the literal authorization token:

```text
I_AUTHORIZE_P5_02O_INSTALLED_DISABLED
```

## Execution

From the Orion repository root, with the P5-02O branch checked out and clean:

```powershell
& ".\scripts\phase5\p5-02o-installed-disabled-gate.ps1" `
  -AuthorizationToken "I_AUTHORIZE_P5_02O_INSTALLED_DISABLED"
```

Do not set any Phase 5 mutation environment variable before running the gate.

## Required acceptance markers

A successful run must include:

```text
P5_02O_ROLLBACK_CAPTURED=true
P5_02O_MUTATION_MODE_PERSISTED=false
P5_02O_DISPOSABLE_FLAGS_PERSISTED=false
P5_02O_RECOVERY_INVENTORY_COUNT=0
P5_02O_HERMES_MANUAL_OFF_PREINSTALL=true
P5_02O_SOURCE_DOCTOR=PASS
P5_02O_INSTALLED_DOCTOR=PASS
P5_02O_INSTALLED_SOURCE_MATCH=true
P5_02O_INSTALLED_PLUGIN_VERSION=0.2.0
P5_02O_GATEWAY_HEALTHY=true
P5_02O_HERMES_DOTENV_LOADED=true
P5_02O_EFFECTIVE_RECOVERY_ROOT_MATCH=true
PRODUCTION_MUTATION_MODE=disabled
PRODUCTION_MUTATION_ALLOWED=false
P5_02O_NATIVE_ROOT_VALIDATION=PASS
P5_02O_RECOVERY_INVENTORY_COUNT=0
P5_02O_RECOVERY_ATTENTION_COUNT=0
P5_02O_REGISTERED_APPLY_HANDLER=apply_plan_production_guarded
P5_02O_PRIVATE_EXECUTOR_REGISTERED=false
P5_02O_APPLY_SCHEMA_PLAN_TOKEN_ONLY=true
P5_02O_DISABLED_PRETOOL_BLOCK=true
P5_02O_DISABLED_APPLY_REFUSED=true
P5_02O_DISABLED_APPROVAL_ATTEMPT_CREATED=false
P5_02O_DISABLED_EXECUTOR_CALLED=false
P5_02O_LIVE_ORION_TOOLSET_FOUND=true
P5_02O_LIVE_ORION_TOOL_COUNT=4
P5_02O_RUNTIME_VERIFY=PASS
P5_02O_GATEWAY_STOPPED=true
P5_02O_CONFIG_UNCHANGED=true
P5_02O_ENV_UNCHANGED=true
P5_02O_RECOVERY_ROOT_STILL_EMPTY=true
P5_02O_MUTATION_INVOCATION=false
HERMES_MANUAL_OFF=true
P5_02O_INSTALLED_DISABLED_QUALIFICATION=PASS
```

## Stop conditions

Fail closed and do not continue if:

- repository worktree is dirty;
- the expected P5-02O branch is not checked out;
- the exact P5-02N source commit is unavailable;
- Hermes is already running;
- accepted COMPANION config, installed-plugin, Hermes commit, or P4-04A patch
  hashes differ;
- any ambient or persisted mutation/disposable setting exists;
- the persisted recovery root is missing, duplicated, mismatched, or non-empty;
- source or installed plugin doctor fails;
- installed source hashes differ from the exact qualified worktree;
- COMPANION config or `.env` changes;
- gateway readiness fails;
- registered handler/schema/private-executor checks fail;
- disabled apply creates approval state or reaches the private executor;
- live toolset differs from the expected four tools;
- any recovery record appears;
- Hermes cannot return to manual-off.

## Observed live result — PASS

The authorized P5-02O installed-but-disabled gate completed successfully on
2026-09-23.

Rollback was captured before plugin replacement at:

```text
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\backups\p5-02o-installed-disabled-20260923-040536
```

Exact installed source pin:

```text
faf8b4787d8e6fb668eb5e9d754104910b4b401a
```

Observed pre-install and installation evidence:

```text
P5_02O_ROLLBACK_CAPTURED=true
P5_02O_MUTATION_MODE_PERSISTED=false
P5_02O_DISPOSABLE_FLAGS_PERSISTED=false
P5_02O_RECOVERY_INVENTORY_COUNT=0
P5_02O_HERMES_MANUAL_OFF_PREINSTALL=true
P5_02O_SOURCE_DOCTOR=PASS
P5_02O_INSTALLED_DOCTOR=PASS
P5_02O_INSTALLED_SOURCE_MATCH=true
P5_02O_INSTALLED_PLUGIN_VERSION=0.2.0
```

Both source and installed-location Hermes Plugin Doctor reported **4 tools /
2 hooks**.

Observed live runtime evidence:

```text
P5_02O_GATEWAY_HEALTHY=true
P5_02O_HERMES_DOTENV_LOADED=true
P5_02O_EFFECTIVE_RECOVERY_ROOT_MATCH=true
PRODUCTION_MUTATION_MODE=disabled
PRODUCTION_MUTATION_ALLOWED=false
P5_02O_NATIVE_ROOT_VALIDATION=PASS
P5_02O_RECOVERY_INVENTORY_COUNT=0
P5_02O_RECOVERY_ATTENTION_COUNT=0
P5_02O_REGISTERED_APPLY_HANDLER=apply_plan_production_guarded
P5_02O_PRIVATE_EXECUTOR_REGISTERED=false
P5_02O_APPLY_SCHEMA_PLAN_TOKEN_ONLY=true
P5_02O_DISABLED_PRETOOL_BLOCK=true
P5_02O_DISABLED_APPLY_REFUSED=true
P5_02O_DISABLED_APPROVAL_ATTEMPT_CREATED=false
P5_02O_DISABLED_EXECUTOR_CALLED=false
P5_02O_LIVE_ORION_TOOLSET_FOUND=true
P5_02O_LIVE_ORION_TOOL_COUNT=4
P5_02O_RUNTIME_VERIFY=PASS
```

The disabled apply verification used disposable temporary note roots only. It
proved that a valid preview token still blocks before approval/executor
delegation when production mutation is disabled.

Observed shutdown/post-state:

```text
P5_02O_GATEWAY_STOPPED=true
P5_02O_CONFIG_UNCHANGED=true
P5_02O_ENV_UNCHANGED=true
P5_02O_RECOVERY_ROOT_STILL_EMPTY=true
P5_02O_MUTATION_INVOCATION=false
HERMES_MANUAL_OFF=true
P5_02O_INSTALLED_DISABLED_QUALIFICATION=PASS
```

No production recovery transaction was created. No real vault/inbox edit,
move, restore, or delete was invoked. COMPANION configuration and persisted
environment bytes remained unchanged.

## Acceptance

P5-02O is accepted.

The installed COMPANION plugin is now the exact P5-02N-qualified `0.2.0`
source and the live registered apply handler is
`apply_plan_production_guarded`, but production mutation remains disabled.

P5-02O acceptance does **not** authorize a production edit, move, restore,
delete, or any future `mutation_enabled` state.

Any bounded production mutation gate requires a new owner authorization naming
the exact action and target, with its own rollback/recovery plan.
