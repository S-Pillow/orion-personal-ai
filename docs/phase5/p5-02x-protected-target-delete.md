# P5-02X — Protected Retained-Target Delete

Status: **AUTHORIZED / GATE PREPARED / EXECUTION PENDING**

Authorization date: 2026-09-25

Branch: `feature/orion-phase5-p5-02x-protected-target-delete`

Baseline: `main` after accepted P5-02W merge
`956282ef5a8765b672e720d5ca1bf27cf88cd3e3`.

Installed protected-delete plugin source:
`211255ff9abfa04101760c7e3358b521a3e530ae`.

## Authorized action

P5-02X authorizes exactly one protected `delete_note` action:

```text
target: C:\Personal\Me\_Orion-P5-Move-Canary.md
target relative path: _Orion-P5-Move-Canary.md
current SHA-256: 132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132
resulting target state: absent
```

The exact Windows target file identity is captured by the registered read-only
delete preview immediately before approval and becomes part of the immutable
plan token. P5-02X requires that same file identity again after the human
decision and immediately before deletion.

P5-02X does **not** authorize changing/removing the restored inbox source.

## Protected reference source

The restored source must remain:

```text
C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md
```

with:

```text
SHA-256: 132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132
Windows file ID: 5e1aeb8a1aeb5d91:67660100000036010000000000000000
```

before and after the delete.

## Frozen target bytes

```text
---
orion_draft: true
status: draft
date: 2026-09-24
origin: p5-02s-controlled-fixture
---
# Orion Phase 5 Move Canary
state: inbox
gate: first-production-move
```

with one trailing LF.

## Exact deletion diff

```diff
--- vault/_Orion-P5-Move-Canary.md
+++ /dev/null
@@ -1,9 +0,0 @@
----
-orion_draft: true
-status: draft
-date: 2026-09-24
-origin: p5-02s-controlled-fixture
----
-# Orion Phase 5 Move Canary
-state: inbox
-gate: first-production-move
```

Exact diff SHA-256:

```text
74c256be2c280ecabb7175d3f18cba214dfb37b34f595ef72146921c6133c0cf
```

## Required recovery baseline

Before P5-02X, production recovery must contain exactly these four valid records
with zero attention:

- `33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f`
  — `edit_note` — `committed_then_changed`
- `1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27`
  — `restore_edit` — `committed`
- `8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6`
  — `move_draft` — `committed_then_changed`
- `5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175`
  — `restore_move_source` — `committed`

Historical recovery evidence is fingerprinted by the PowerShell wrapper and must
remain byte-identical during P5-02X.

## Gate artifacts

```text
scripts/phase5/p5-02x-protected-target-delete.ps1
scripts/phase5/p5-02x-protected-target-delete.py
```

The parent gate requires:

- exact P5-02X branch and clean repository;
- Hermes manual-off based on port 8642 listener state;
- installed plugin exactly matching P5-02V-qualified `0.3.0` source;
- installed plugin doctor PASS;
- runner compile PASS;
- restored source and retained target both at the frozen SHA-256;
- edit canary at the accepted restored hash;
- exact four accepted recovery IDs;
- mutation mode absent from the parent process.

The child runner independently:

- loads the registered live tools from the exact installed plugin path;
- requires internal plugin version `p5-02v-0.3.0`;
- requires registered `preview_delete` and guarded apply handlers;
- requires the private executor to remain unregistered;
- validates vault/inbox/recovery roots with mutation disabled;
- validates exact four-record / zero-attention recovery baseline;
- validates source path/bytes/hash/file ID;
- validates target path/bytes/hash;
- dispatches registered delete preview while mutation remains disabled;
- validates exact target path/hash/state, Windows file ID, and deletion diff hash;
- rechecks source/target/recovery after preview;
- enables `ORION_P5_MUTATION_MODE=mutation_enabled` only inside the child
  process around one registered apply dispatch;
- requires fresh Hermes human **ONCE** approval;
- removes mutation mode in `finally`;
- verifies source unchanged, target absent, and new committed delete recovery.

## Expected new recovery record

On success, P5-02X creates a fifth recovery record whose ID equals the immutable
delete plan token.

Expected directory entries:

```text
deleted_target.bin
manifest.json
receipt.json
```

Expected recovery state:

- action = `delete_note`;
- manifest = `committed`;
- classification = `committed`;
- `deleted_target.bin` SHA-256 = frozen target SHA-256;
- target current SHA after deletion = absent;
- recovery required = false;
- receipt committed/finalized;
- approval surface = `cli`;
- approval choice = `once`;
- authorization reusable = false.

## Failure policy

P5-02X never automatically recreates the target and never cleans recovery
evidence.

If apply is denied, times out, errors, or produces ambiguous state:

- preserve the inbox source exactly as found;
- preserve whatever target state actually exists;
- preserve every recovery record;
- do not retry automatically;
- do not invoke P5-02Y;
- do not perform a second mutation.

## Expected successful post-state

- restored inbox source present and byte-identical;
- restored source Windows file identity unchanged;
- retained vault target absent;
- new delete recovery committed;
- recovery inventory exactly 5 valid records / 0 attention;
- mutation mode disabled after the bounded child process;
- installed plugin unchanged;
- config / `.env` unchanged;
- unrelated edit canary unchanged;
- Hermes manual-off;
- no recovery cleanup.

## P5-02Y remains separate in sequence

The standing closure authorization covers P5-02Y, but cleanup is intentionally
sequenced after P5-02X because the exact final recovery set is not known until
the delete recovery ID exists.

P5-02Y must name the exact records selected for removal and retain an audit
record of the cleanup.

## Current stop point

P5-02X is authorized and the guarded gate is prepared.

The protected target deletion has not yet been executed by repository
preparation. Production recovery remains at the accepted four-record P5-02U/W
state until the Windows gate succeeds.
