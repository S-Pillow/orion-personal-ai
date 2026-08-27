# P3-05 — Controlled Edit / Move Broker Closure

**Status: PASS / CLOSED — August 27, 2026**

## Accepted implementation

- Dedicated broker container: `orion-vault-broker`.
- Authoritative vault: `C:\Personal\Me` mounted at `/workspace` for broker-controlled writes only.
- Orion draft inbox: `C:\Personal\Orion-Inbox` mounted at `/inbox`.
- Recovery store: `C:\Personal\Orion-Recovery` mounted at `/recovery`.
- Broker runs as UID/GID `10000:10000`.
- Network mode is `none`.
- Root filesystem is read-only.
- Linux capabilities are dropped and `no-new-privileges` is enabled.
- `/opt/data` is an ephemeral tmpfs and no persistent iai memory volume is mounted.
- Reusable operational script: `Orion-Phase3-P3-05-Controlled-Vault-Broker-v2.ps1`.
- Accepted provisioning/acceptance harness: `Orion-Phase3-P3-05-Provision-And-Accept-Controlled-Broker-v3.ps1`.

## Control model

P3-05 uses a preview/apply contract rather than direct unreviewed writes.

- `Preview` returns the exact target, exact unified diff, current/proposed hashes where applicable, and an approval token bound to the previewed state.
- `Apply` requires the exact approval token returned by `Preview`.
- An invalid token is treated as a policy denial, not a broker crash.
- A denied move or edit must produce no filesystem change.
- An edit is guarded by the original target SHA256 so a file changed after preview is denied rather than overwritten.
- Successful writes create recovery evidence under `C:\Personal\Orion-Recovery`.
- Restore uses the same preview/approval model and preserves the pre-restore state so recovery itself remains reversible.

Supported operations:

1. `MoveDraft` — promotes a marked Orion inbox draft to an exact relative vault path.
2. `EditNote` — previews and applies an exact full-note edit.
3. `Restore` — restores exact bytes from a recovery backup after approval.

The broker rejects absolute paths, traversal, symlink traversal, non-Markdown targets, and unapproved applies.

## Live acceptance evidence

Container/isolation checks passed:

- `P3_05_HOST_PATHS=PASS`
- `P3_05_BROKER_CONTAINER_RUNNING=PASS`
- `P3_05_BROKER_RW_BOUNDARIES=PASS`
- `P3_05_NO_MEMORY_VOLUME=PASS`
- `P3_05_EPHEMERAL_DATA_TMPFS=PASS`
- `P3_05_BROKER_HARDENING=PASS`

Move workflow passed:

- `P3_05_DISPOSABLE_DRAFT_CREATED=PASS`
- `P3_05_MOVE_PREVIEW=PASS`
- `P3_05_MOVE_PREVIEW_NO_WRITE=PASS`
- `P3_05_DENIED_MOVE_NOOP=PASS`
- `P3_05_APPROVED_MOVE=PASS`
- Accepted move recovery evidence was created at `20260827T045544Z-5f3345b243/backup.md` during the final disposable acceptance run.

Edit workflow passed:

- `P3_05_EDIT_PREVIEW_DIFF=PASS`
- `P3_05_DENIED_EDIT_NOOP=PASS`
- `P3_05_APPROVED_EDIT_EXACT=PASS`
- `P3_05_EDIT_RECOVERY_BACKUP=PASS`
- Accepted edit recovery evidence was created at `20260827T045547Z-0e79f64289/backup.md` during the final disposable acceptance run.

Recovery workflow passed:

- `P3_05_RESTORE_PREVIEW=PASS`
- `P3_05_RECOVERY_RESTORE_EXACT=PASS`
- The restored target SHA256 matched the pre-edit original bytes exactly.

Cleanup and final acceptance passed:

- `P3_05_DISPOSABLE_CLEANUP=PASS`
- `P3_05_CONTROLLED_EDIT_MOVE_BROKER=PASS`
- `P3_05_ACCEPTANCE=PASS`

The final acceptance run used disposable test material only; existing vault notes were not modified by the test.

## Acceptance-harness revisions

Two verifier/harness defects were corrected before final acceptance:

- v1 broker wrapper treated expected `status=denied` / exit 20 results as generic failures before evaluating the denial contract. v2 handles policy denial before generic non-zero exit handling and the acceptance harness explicitly verifies exit 20 plus `status=denied`.
- v2 acceptance harness had a malformed final PowerShell boolean expression combining two `Test-Path` calls. v3 parenthesized each call correctly; a same-form scan found no remaining instances.

These were harness defects, not broker-policy or vault-write failures.

## Result

P3-05 is accepted. Orion now has an isolated, approval-gated path for promoting inbox drafts, editing existing Markdown notes, and restoring exact prior bytes, with previewed diffs, denial no-op proof, optimistic-concurrency protection, and recovery evidence. iai remains separate from document write control and continues to own memory semantics.

**Intent status: PRESERVED.**
