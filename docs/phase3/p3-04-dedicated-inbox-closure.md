# P3-04 — Dedicated Orion Inbox Closure

**Status: PASS / CLOSED — August 27, 2026**

## Accepted implementation

- Dedicated host inbox: `C:\Personal\Orion-Inbox`.
- The inbox is outside the authoritative Obsidian vault at `C:\Personal\Me`.
- Dedicated writer container: `orion-inbox-writer`.
- Container image ID: `sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`.
- `/inbox` is the only persistent writable content surface and is backed by `C:\Personal\Orion-Inbox`.
- The authoritative vault is not mounted into the writer container.
- The iai COMPANION memory volume is not mounted into the writer container.
- Image-declared `/opt/data` is explicitly overlaid with an ephemeral tmpfs so the writer has no persistent memory storage.
- Container network mode is `none`.
- Container root filesystem is read-only.
- Container runs as UID/GID `10000:10000` with capabilities dropped and `no-new-privileges`.
- Reusable operational draft creator: `Orion-Phase3-P3-04-Create-Inbox-Draft.ps1`.
- Draft creation is Markdown-only, refuses overwrite, rejects nested/absolute/unsafe paths, and emits explicit Orion draft metadata.

## Acceptance evidence

Final provisioning/acceptance run returned:

- `P3_04_INBOX_HOST_EXISTS=PASS`
- `P3_04_INBOX_OUTSIDE_VAULT=PASS`
- `P3_04_INBOX_CONTAINER_RUNNING=PASS`
- `P3_04_INBOX_MOUNT_RW=PASS`
- `P3_04_NO_VAULT_MOUNT=PASS`
- `P3_04_NO_MEMORY_VOLUME=PASS`
- `P3_04_EPHEMERAL_DATA_TMPFS=PASS`
- `P3_04_NETWORK_NONE=PASS`
- `P3_04_ROOTFS_READ_ONLY=PASS`
- `P3_04_UID_GID=PASS`
- `P3_04_DRAFT_CREATE_SMOKE=PASS`
- `P3_04_DRAFT_METADATA=PASS`
- `P3_04_ACCEPTANCE_DRAFT_CLEANUP=PASS`
- `P3_04_DEDICATED_ORION_INBOX=PASS`
- `P3_04_ACCEPTANCE=PASS`

The reusable draft creator was exercised by the acceptance flow, the generated draft was visible on the host inbox, required metadata was present, and the disposable acceptance draft was removed successfully.

## Iteration notes

- Provisioning v1 correctly exposed that the selected iai image declares `/opt/data` as a Docker volume. Docker therefore created an anonymous `/opt/data` volume even though the canonical iai memory volume was never mounted. The accepted v2/v3 design explicitly overlays `/opt/data` with ephemeral tmpfs and verifies no persistent bind/volume is present there.
- Provisioning v2 then correctly exposed a mismatch between the acceptance smoke filename and the reusable creator's filename policy: the test filename began with `_`, while the creator requires an alphanumeric first character. Provisioning v3 changed only the disposable smoke filename and passed.
- Neither failed iteration modified the authoritative Obsidian vault.

## Result

Orion now has a bounded, isolated writable draft surface that is separate from the authoritative Obsidian vault and separate from iai memory. Drafts can be created without approval in the dedicated inbox; moving or editing material in the authoritative vault remains approval-gated future work.

**Intent status: PRESERVED.** The inbox adds a safe writable boundary without weakening the read-only authoritative vault model or creating a second memory system.

## Next

P3-05 — Controlled edit/move broker: approval-gated promotion or modification of authoritative vault content with exact diff/recovery behavior and denied-action no-op proof.
