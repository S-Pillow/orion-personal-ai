# P5-02B Disposable Mutation Candidate

Status: **SOURCE-ONLY / UNREGISTERED / WINDOWS VERIFICATION PENDING**  
Date: 2026-09-21  
Depends on: accepted P5-01 merge `33c39d4` and P5-02A approval-integrity branch

## Boundary

P5-02B is a private mutation prototype used only with disposable roots.

The registered Hermes tool `orion_vault_apply_plan` still points to `apply_plan_placeholder` and returns `p5_01_mutation_not_authorized`. No live COMPANION plugin installation, profile grant, gateway restart, or real vault/inbox mutation is authorized by this code.

The private executor is `_execute_disposable_plan_candidate()`. It cannot run unless all of the following are true:

- `ORION_P5_ALLOW_DISPOSABLE_MUTATION=1`;
- `ORION_VAULT_ROOT` is explicitly set;
- `ORION_INBOX_ROOT` is explicitly set;
- `ORION_P5_RECOVERY_ROOT` is explicitly set;
- all three roots already exist;
- recovery is disjoint from vault and inbox;
- no raw or resolved root overlaps the live defaults `C:\Personal\Me` or `C:\Personal\Orion-Inbox`.

This is defense-in-depth around a source candidate, not a substitute for the real authorization gate.

## Edit protocol

For an edit plan the executor:

1. re-loads the still-live preview and re-validates its exact cached diff/proposed bytes;
2. re-resolves the target through the existing containment/reparse policy;
3. confirms canonical target identity and the approved original SHA-256;
4. creates a plan-specific recovery directory outside both policy roots;
5. writes `original.bin` with exclusive creation, `flush()`, and `os.fsync()`;
6. writes a recovery manifest in `prepared` state;
7. writes the proposed bytes to a same-directory exclusive temporary file and fsyncs it;
8. consumes the plan before the protected replace attempt;
9. on Windows, calls native `ReplaceFileW`; non-Windows fixture execution falls back to `os.replace`;
10. verifies the final target hash;
11. marks the recovery manifest `committed`.

The token remains consumed after a protected write attempt, including an ambiguous/failed replacement. A failed post-write state is reported as recovery-required rather than retried automatically.

Why `ReplaceFileW`: Microsoft documents it as the single Windows replacement operation and notes that it preserves important attributes of the replaced file. The replacement and target are kept in the same directory/volume. Orion also writes its own recovery bytes before the call because Windows documents partial-state failure codes for replacement operations.

Reference:
https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew

Python durability reference:
https://docs.python.org/3.11/library/os.html#os.fsync

## Move-draft protocol

For an inbox-to-vault move plan the executor:

1. re-resolves and verifies source/target containment and canonical identities;
2. requires the destination parent to already exist in this first slice;
3. requires the destination to be absent;
4. re-checks source SHA-256 and the Orion draft markers;
5. writes a durable recovery copy `source.bin` and a `prepared` manifest;
6. consumes the plan;
7. creates the destination with exclusive `xb` creation so a target race cannot overwrite another file;
8. fsyncs and verifies the destination hash;
9. re-reads the source immediately before deletion;
10. if the source changed, removes the just-created target only when that target still exactly matches Orion's approved bytes;
11. otherwise removes the source;
12. verifies source absence + target hash and marks the manifest `committed`.

The protocol intentionally makes the crash window visible. If interruption occurs after target creation but before source deletion, both copies can exist and `recovery_required=true` is returned. The source is never silently deleted merely because a target exists.

This is the accepted donor direction—exclusive target creation plus verification—made explicit and testable. It does not claim a cross-root two-path transaction that Windows/Python do not actually provide.

## Failure checkpoints

The source candidate exposes a private test hook at:

- `edit_after_recovery`;
- `edit_before_replace`;
- `edit_after_replace`;
- `move_after_recovery`;
- `move_after_target_create`;
- `move_before_source_delete`;
- `move_after_source_delete`.

The hook is not a Hermes/tool argument. It exists only to inject deterministic test failures.

Expected classifications:

| Condition | Expected result |
| --- | --- |
| unknown/expired/stale plan | no mutation |
| live/default-root overlap | refuse before file operation |
| target appears before move create | source unchanged; no overwrite |
| edit interrupted after replacement | new target may exist; original recovery bytes retained; recovery required |
| move interrupted after target create | source + target may both exist; recovery required |
| source changes after target creation | do not delete source; remove target only if it is still exactly ours |
| replay after protected mutation attempt | refused |
| recovery-root collision | fail closed |
| ReplaceFileW/sharing failure | conservatively classify as mutation/recovery required once protected replace was attempted |

## Current source coverage

P5-02A adds concurrency/late-callback/attempt-limit approval tests.

P5-02B adds tests for:

- private candidate not registered as the Hermes apply handler;
- explicit disposable opt-in;
- exact/ancestor/descendant overlap with live default roots;
- post-resolution parent symlink/junction overlap;
- recovery root disjointness;
- committed edit + recovery bytes + replay refusal;
- stale edit with no recovery/mutation;
- interruption after edit replacement;
- committed move + recovery bytes + replay refusal;
- target race;
- source drift after target creation with safe target cleanup;
- interruption before source deletion with explicit recovery-required duplicate state.

The full `test_p5*.py` discovery is expected to contain **37 tests** (16 accepted P5-01 + 9 P5-02A + 12 P5-02B). This number is **not acceptance evidence until the Windows run passes**.

No GitHub Actions workflow currently executes this branch, and the ChatGPT container used during source review had no outbound DNS, so it could not clone/run the repository independently. Treat the code as pending execution.

## Tomorrow: Windows source verification

From PowerShell:

```powershell
git -C "D:\Orion\orion-personal-ai" pull --ff-only

& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  -m unittest discover `
  -s "D:\Orion\orion-personal-ai\hermes_plugins\orion-vault-actions\tests" `
  -p "test_p5*.py" -v
```

Expected discovery count: **37**.

Then run the installed-runtime no-write dispatcher probe:

```powershell
& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  "D:\Orion\orion-personal-ai\hermes_plugins\orion-vault-actions\tests\probe_hermes_dispatch.py"
```

Then doctor only:

```powershell
& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe" `
  -p companion plugins doctor `
  "D:\Orion\orion-personal-ai\hermes_plugins\orion-vault-actions" --ci
```

These operations use source/disposable fixtures. Do not start/install/enable the live plugin for this verification.

## Stop conditions before any live mutator

Do not wire `_execute_disposable_plan_candidate` into `orion_vault_apply_plan` until all of these are separately satisfied:

- Windows tests pass, including native `ReplaceFileW`;
- P5-02A fresh-once approval concurrency/replay tests pass;
- exact visual approval content is explicitly confirmed by the operator;
- full installed-Hermes approval-to-HUD no-write flow passes;
- recovery artifact location/ACL/retention is designed for production rather than the disposable env contract;
- recovery/restore behavior is implemented and tested, not merely recovery-byte creation;
- the live-install authorization unit names exact commit/profile/path/backup/rollback;
- a further explicit authorization unit names the first real protected mutation.

The disposable candidate is deliberately not the live handler.
