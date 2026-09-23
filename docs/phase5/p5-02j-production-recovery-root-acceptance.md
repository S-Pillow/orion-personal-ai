# P5-02J — Production Recovery Root Location and ACL Acceptance

Status: **COMPLETE / PRODUCTION RECOVERY ROOT + ACL ACCEPTED / MUTATION STILL DISABLED**

Branch:

```text
feature/orion-phase5-p5-02j-production-recovery-root
```

Depends on:

- P5-02G production guardrails — source/Windows verified;
- P5-02H preview-only COMPANION installation — accepted;
- P5-02I installed-runtime disposable mutation qualification — complete.

## Purpose

P5-02J selects and qualifies the persistent production recovery directory that
future Orion vault mutations will use for durable recovery manifests, backup
bytes, and non-authorizing receipts.

This ticket does **not** enable production mutation, register the private
production executor, persist mutation mode, or mutate the real vault/inbox.

The controlling invariant is:

> Recovery storage must be a fixed-local, disjoint, non-reparse Windows
> directory whose DACL does not grant write-like rights to broad principals,
> and the installed plugin must accept it while production mutation remains
> disabled.

## Proposed production recovery location

The proposed exact root is:

```text
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery
```

Operator-form equivalent:

```powershell
Join-Path $env:LOCALAPPDATA "hermes\profiles\companion\orion\production-recovery"
```

Rationale:

- it is outside `C:\Personal\Me`;
- it is outside `C:\Personal\Orion-Inbox`;
- it is separate from disposable recovery roots;
- it is tied to the accepted COMPANION profile rather than the plugin
  installation directory;
- its parent `...\companion\orion` already hosts the preserved P5 rollback
  backup area, so P5-02J does not need to create a new parent hierarchy;
- it can be ACL-protected independently;
- plugin reinstalls/replacements do not require deleting this directory.

P5-02J does not create this directory until explicit owner authorization.

## Required ACL

The root must have inheritance disabled and must not retain inherited ACEs.

Allowed explicit Full Control principals:

- the current COMPANION operator Windows SID;
- `SYSTEM` — `S-1-5-18`;
- `BUILTIN\Administrators` — `S-1-5-32-544`.

The current operator must remain the directory owner.

The following broad principals must not receive allowed write-like rights:

- Everyone — `S-1-1-0`;
- Authenticated Users — `S-1-5-11`;
- BUILTIN\Users — `S-1-5-32-545`.

The installed plugin's native validator is the final acceptance check for its
supported DACL policy. P5-02J additionally requires the operator script to
observe a protected DACL and no unexpected explicit allow principals.

## Existing production validator

The installed P5-02I plugin already contains read-only production-root
validation. It requires:

- real vault root exists;
- real inbox root exists;
- production recovery root exists;
- no vault/inbox/recovery path contains a reparse component;
- all three roots are disjoint after resolution;
- Windows raw-path overlap is also rejected;
- recovery root is on a fixed local volume;
- current process can list the directory and request child-directory creation
  access;
- no allowed write-like ACE exists for Everyone, Authenticated Users, or
  BUILTIN\Users;
- callback/conditional allow ACEs fail closed.

The validator never repairs ACLs and the plugin never creates the production
recovery root.

## Owner authorization

Owner explicitly authorized:

```text
P5-02J production recovery-root creation and ACL acceptance at
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery
```

Authorized live actions are limited to the P5-02J execution boundary in this
runbook. In particular, the authorization permits creation of exactly that
directory and replacement of only that new directory's ACL with the accepted
protected ACL.

The authorization does **not** extend to:

- persisting `ORION_P5_PRODUCTION_RECOVERY_ROOT`;
- setting `ORION_P5_MUTATION_MODE=mutation_enabled`;
- registering the private production executor;
- starting/restarting Hermes;
- changing vault/inbox ACLs;
- mutating real vault/inbox content;
- merge/deploy.

Operator script source pin:

```text
c39d07dfce69ed9797318eec0d48edc05d26acf6
scripts/phase5/p5-02j-production-recovery-root.ps1
scripts/phase5/p5-02j-verify-production-recovery-root.py
```

The live run must execute that exact source pin or an identical script hash.

## P5-02J execution boundary

A future explicitly authorized P5-02J operator run may do only the following:

1. require Hermes manual-off;
2. verify accepted COMPANION config and installed-plugin hashes;
3. require production mutation-related process/persistent settings to remain
   absent;
4. require the proposed recovery root to be absent;
5. require the existing `...\companion\orion` parent to exist and not be a
   reparse point;
6. create exactly the proposed recovery directory;
7. replace only that new directory's DACL with the accepted protected ACL;
8. run the installed plugin's native production-root validator with
   `ORION_P5_PRODUCTION_RECOVERY_ROOT` set **process-only**;
9. run the bounded production recovery inventory against the empty root;
10. require mutation mode `disabled` and `mutation_allowed=false`;
11. verify the persistent COMPANION config and `.env` files are unchanged;
12. leave Hermes manual-off.

If validation fails, the operator script may remove the newly created directory
only when it is still empty. It must never remove a non-empty or pre-existing
directory.

## Explicitly out of scope

P5-02J does not authorize:

- persisting `ORION_P5_PRODUCTION_RECOVERY_ROOT` into COMPANION `.env`;
- setting `ORION_P5_MUTATION_MODE=mutation_enabled`;
- setting any production mutation mode persistently;
- registering `_execute_production_plan_candidate`;
- changing `orion_vault_apply_plan` away from `apply_plan_placeholder`;
- starting/restarting Hermes;
- changing vault/inbox ACLs;
- moving or editing any real vault/inbox document;
- creating any production recovery transaction;
- merge/deploy;
- Hermes/Ollama/iai upgrade.

## Prepared operator artifacts

Source-only preparation is complete at the current branch head.

Prepared files:

```text
scripts/phase5/p5-02j-production-recovery-root.ps1
scripts/phase5/p5-02j-verify-production-recovery-root.py
```

The PowerShell gate requires the literal runtime token:

```text
I_AUTHORIZE_P5_02J_PRODUCTION_RECOVERY_ROOT
```

It will not run without that token.

The Python verifier is read-only. It process-scopes the candidate production
recovery root, keeps mutation mode absent/disabled, calls the installed plugin's
native root validator and bounded inventory, requires an empty inventory, and
proves registered apply still fails closed.

The P5-02J branch delta from the accepted P5-02I completion commit is docs and
operator scripts only. No plugin source, manifest, COMPANION configuration, or
runtime file is changed by this preparation.

## First live invocation — SAFE PRE-EXECUTION STOP

The first authorized operator invocation did not enter the P5-02J gate script.

Windows PowerShell blocked direct invocation of the pinned `.ps1` because
script execution is disabled by the host execution policy:

```text
PSSecurityException
running scripts is disabled on this system
FullyQualifiedErrorId : UnauthorizedAccess
```

Because the script was rejected before execution:

- the proposed production recovery root was not created by P5-02J;
- no ACL was changed;
- no production environment setting was persisted;
- no plugin/native validator ran;
- no vault/inbox content was touched.

The temporary source worktree was subsequently removed.

Operator-control correction:

- do **not** change LocalMachine/User execution policy;
- rematerialize the exact authorized source pin
  `c39d07dfce69ed9797318eec0d48edc05d26acf6`;
- invoke that exact script in a child Windows PowerShell process with
  `-ExecutionPolicy Bypass -File`;
- this bypass is process-scoped only and does not persist an execution-policy
  change;
- use the child process exit code directly rather than relying on
  `$LASTEXITCODE` after an in-process PowerShell script-policy exception.

P5-02J remains authorized and pending. No acceptance marker has been earned yet.

## Acceptance markers

A successful authorized operator run must report at least:

```text
P5_02J_ROOT_CREATED=true
P5_02J_ACL_INHERITANCE_PROTECTED=true
P5_02J_ACL_EXPECTED_PRINCIPALS_ONLY=true
P5_02J_NATIVE_ROOT_VALIDATION=PASS
PRODUCTION_MUTATION_MODE=disabled
PRODUCTION_MUTATION_ALLOWED=false
P5_02J_RECOVERY_INVENTORY_COUNT=0
P5_02J_RECOVERY_ATTENTION_COUNT=0
P5_02J_CONFIG_UNCHANGED=true
P5_02J_ENV_UNCHANGED=true
HERMES_MANUAL_OFF=true
P5_02J_PRODUCTION_RECOVERY_ROOT_ACCEPTANCE=PASS
```

## Stop / rollback conditions

Stop immediately if:

- the candidate root already exists;
- the parent path is missing or has a reparse component;
- COMPANION config or installed-plugin hash differs from the accepted baseline;
- a production mutation environment value is already present;
- root resolution overlaps vault or inbox;
- the volume is not fixed-local;
- broad write ACLs remain;
- the current identity cannot access the root as required;
- native validation or inventory fails;
- recovery inventory is non-empty;
- Hermes starts unexpectedly.

On failure after P5-02J created the root:

- if and only if the directory remains empty, remove that newly created root;
- preserve the parent and every pre-existing path;
- do not change COMPANION configuration;
- do not attempt a mutation as a diagnostic.

## Observed live result — PASS

The authorized P5-02J live gate completed successfully.

Accepted production recovery root:

```text
C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\production-recovery
```

Observed:

- Hermes scheduled task remained registered but no gateway process was running;
- ACL inheritance was protected;
- ACL contained only the accepted principals;
- current operator remained owner;
- production recovery root was created at the exact authorized path;
- installed plugin native root validation passed;
- production mutation mode remained `disabled`;
- `mutation_allowed=false`;
- recovery inventory count was 0;
- recovery attention count was 0;
- inventory was not truncated;
- registered apply remained fail-closed;
- no real vault/inbox mutation occurred;
- COMPANION config remained unchanged;
- COMPANION `.env` remained unchanged;
- Hermes remained manual-off;
- child PowerShell process exited 0;
- operator worktree was cleaned.

Acceptance markers:

```text
P5_02J_ACL_INHERITANCE_PROTECTED=true
P5_02J_ACL_EXPECTED_PRINCIPALS_ONLY=true
P5_02J_ROOT_CREATED=true
P5_02J_NATIVE_ROOT_VALIDATION=PASS
PRODUCTION_MUTATION_MODE=disabled
PRODUCTION_MUTATION_ALLOWED=false
P5_02J_RECOVERY_INVENTORY_COUNT=0
P5_02J_RECOVERY_ATTENTION_COUNT=0
P5_02J_RECOVERY_INVENTORY_TRUNCATED=false
P5_02J_REGISTERED_APPLY_FAIL_CLOSED=true
P5_02J_REAL_VAULT_INBOX_MUTATION=false
P5_02J_CONFIG_UNCHANGED=true
P5_02J_ENV_UNCHANGED=true
HERMES_MANUAL_OFF=true
P5_02J_PRODUCTION_RECOVERY_ROOT_ACCEPTANCE=PASS
P5_02J_CHILD_EXIT_CODE=0
P5_02J_OPERATOR_WORKTREE_CLEANED=true
```

P5-02J is accepted and complete.

This completion does **not** persist
`ORION_P5_PRODUCTION_RECOVERY_ROOT` into COMPANION configuration and does not
authorize or enable production mutation.

## Next gate after P5-02J

If P5-02J passes, the next gate should separately decide whether to persist
`ORION_P5_PRODUCTION_RECOVERY_ROOT` into the COMPANION environment while
keeping production mutation mode disabled.

That persistent configuration change remains separately authorization-gated.
