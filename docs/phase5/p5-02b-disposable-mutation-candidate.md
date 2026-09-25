# P5-02B Disposable Mutation Candidate

Status: **SOURCE-ONLY / UNREGISTERED / WINDOWS HANDLE-HARDENING VERIFIED**  
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
9. on Windows, binds the preview to the source's volume + 128-bit file ID and later reopens that exact source with `GENERIC_READ | DELETE`, `FILE_SHARE_READ` only, and `FILE_FLAG_OPEN_REPARSE_POINT`;
10. rejects a same-path/same-bytes replacement whose file ID no longer matches the approved preview;
11. keeps that source handle open while the destination is created and verified, blocking new conflicting write/delete/rename opens;
12. if another process already holds conflicting write/delete access, the guard open fails before recovery/target creation; otherwise the guard remains held through the operation;
13. re-reads the source through the held handle immediately before deletion as a final content check, then removes the just-created target only if unexpected drift is detected and that target still exactly matches Orion's approved bytes;
14. otherwise marks the held source object for deletion with `SetFileInformationByHandle(FileDispositionInfo)` and closes the same handle;
15. verifies source-path absence + target hash and marks the manifest `committed`.

On non-Windows fixture execution the earlier path-based re-read/unlink behavior remains so the source logic stays testable cross-platform. The production target is Windows, where the held handle materially narrows the final read-to-delete TOCTOU window.

Microsoft documents that `FILE_ID_INFO` combines the volume serial with a 128-bit file ID to identify a file on one computer, and that `FileDispositionInfo` requires a handle opened with DELETE access. The guard intentionally opens with only `FILE_SHARE_READ`: new conflicting write/delete/rename opens fail while the operation is in flight. Windows evaluates share compatibility when the guard is opened, so an existing writer with write access causes the guard open to fail rather than being grandfathered into the protected interval. The held-handle re-read remains a final content check for unexpected state changes.

References:
https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle

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
- `move_after_delete_mark` (Windows only);
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
| source path is replaced with same bytes after preview | Windows file-ID mismatch; refuse before recovery/mutation |
| new write/rename/delete open after source guard is held | sharing violation; approved source remains protected |
| pre-existing writer has conflicting write access | held guard cannot open; refuse before recovery or target mutation |
| interruption after Windows delete mark but before normal completion | fail/recovery-required; recovery manifest remains prepared even if handle close completes deletion |
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
- interruption before source deletion with explicit recovery-required duplicate state;
- Windows preview binding to source file ID and rejection of a same-path/same-bytes replacement;
- Windows blocking of a new conflicting source writer while the held guard is active;
- Windows refusal when a writer handle already holds conflicting write access;
- Windows interruption immediately after handle-based delete marking.

Windows verification at branch head `2e97019` is now **PASS**:

- `test_p5*.py`: **40/40 passed** in 0.412s;
- installed-Hermes dispatcher probe: **2/2 passed** in 0.083s;
- plugin doctor: **PASS**, manifest `orion-vault-actions 0.1.0`, 4 tools / 2 hooks;
- Windows-specific file-ID replacement rejection passed;
- pre-existing writer refusal before mutation passed;
- handle-based delete interruption classification passed;
- existing edit/move recovery, replay, containment, alias, and approval-integrity tests remained green.

The Hermes probe still emits the known SQLite 3.40.1 WAL-reset warning and falls back to `journal_mode=DELETE`; it did not cause a P5 test failure and is tracked separately from this source gate.

This closes the Windows handle-hardening verification gate. The registered `orion_vault_apply_plan` handler remains the refusing placeholder; no live vault/inbox mutation is enabled.

## Next gate: production recovery/restore design

Windows source verification is complete. The next source-only gate is to turn the disposable recovery bytes/manifests into an explicit production recovery contract before any live mutator is wired:

- choose a recovery root outside both vault and inbox;
- define owner-only ACL expectations and startup validation;
- define immutable receipt fields that survive process restart;
- classify prepared/committed/recovery-required states deterministically;
- implement read-only recovery inspection;
- implement restore as a separately previewed and approval-gated action;
- test edit restore, move duplicate-state recovery, missing/corrupt artifact refusal, stale target/source state, replay, and crash/interruption;
- define retention/pruning without automatic deletion of unresolved recovery-required artifacts.

No live plugin install or real vault mutation is part of this gate.

## Stop conditions before any live mutator

Do not wire `_execute_disposable_plan_candidate` into `orion_vault_apply_plan` until all of these are separately satisfied:

- the current 40-test Windows suite passes, including native `ReplaceFileW`, source file-ID binding, held-handle sharing behavior, pre-existing-writer drift detection, and handle-based source deletion;
- P5-02A fresh-once approval concurrency/replay tests pass;
- exact visual approval content is explicitly confirmed by the operator;
- full installed-Hermes approval-to-HUD no-write flow passes;
- recovery artifact location/ACL/retention is designed for production rather than the disposable env contract;
- recovery/restore behavior is implemented and tested, not merely recovery-byte creation;
- the live-install authorization unit names exact commit/profile/path/backup/rollback;
- a further explicit authorization unit names the first real protected mutation.

The disposable candidate is deliberately not the live handler.
