# P5-02T — First Production Move

Status: **AUTHORIZED / GATE PREPARED / EXECUTION PENDING**

Authorization date: 2026-09-25

Branch:

\`\`\`text
feature/orion-phase5-p5-02t-first-production-move
\`\`\`

Repository baseline:

\`\`\`text
main after P5-02S + PRD v2.9 merge: fc89e4efbe6869a26c41505acb553585c6fbb90e
\`\`\`

Installed Orion plugin source remains pinned to the P5-02N-qualified code:

\`\`\`text
faf8b4787d8e6fb668eb5e9d754104910b4b401a
\`\`\`

## Owner authorization

Steven explicitly authorized P5-02T on 2026-09-25.

That authorization is limited to exactly one production action:

\`\`\`text
action: move_draft
source: C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md
target: C:\Personal\Me\_Orion-P5-Move-Canary.md
\`\`\`

No other source, target, action, recovery mutation, cleanup, deletion, or follow-up restore is authorized by P5-02T.

The operator script requires the literal scope token:

\`\`\`text
I_AUTHORIZE_P5_02T_EXACT_PRODUCTION_MOVE
\`\`\`

That token authorizes only the bounded script scope. The actual production mutation still requires the separate live Hermes human **ONCE** decision after the exact move preview is shown.

## Controlling baseline

Orion Master PRD v2.9 is the approved/current repository baseline.

PRD approval does not itself authorize production mutation. This P5-02T authorization is the separate owner authorization for the exact first production move described in this document.

Accepted P5-02S state immediately before P5-02T:

- Hermes manual-off;
- production mutation mode absent/disabled;
- installed plugin exact-match to qualified P5-02N source;
- production recovery inventory = 2 records;
- production recovery attention count = 0;
- controlled move source exists in the accepted inbox;
- future vault target is absent;
- P5-02S-B read-only preview matched the frozen source/target/hash/file-ID/diff contract.

## Frozen P5-02T contract

Source relative path:

\`\`\`text
_Orion-P5-Move-Canary.md
\`\`\`

Source canonical path:

\`\`\`text
C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md
\`\`\`

Target relative path:

\`\`\`text
_Orion-P5-Move-Canary.md
\`\`\`

Target canonical path:

\`\`\`text
C:\Personal\Me\_Orion-P5-Move-Canary.md
\`\`\`

Frozen source SHA-256:

\`\`\`text
132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132
\`\`\`

Frozen source Windows file identity:

\`\`\`text
5e1aeb8a1aeb5d91:eec0070000001f000000000000000000
\`\`\`

Frozen exact diff SHA-256:

\`\`\`text
61e4f48a0964aec273217a87dc3d7ac706f2a6525886420ee5e6d80fcb26a587
\`\`\`

Exact source bytes, UTF-8 without BOM and LF newlines:

\`\`\`text
---
orion_draft: true
status: draft
date: 2026-09-24
origin: p5-02s-controlled-fixture
---
# Orion Phase 5 Move Canary
state: inbox
gate: first-production-move
\`\`\`

with one trailing LF.

Exact move preview:

\`\`\`diff
--- /dev/null
+++ vault/_Orion-P5-Move-Canary.md
@@ -0,0 +1,9 @@
+---
+orion_draft: true
+status: draft
+date: 2026-09-24
+origin: p5-02s-controlled-fixture
+---
+# Orion Phase 5 Move Canary
+state: inbox
+gate: first-production-move
\`\`\`

The target must remain absent until the qualified move executor creates it.

## Accepted historical recovery baseline

P5-02T requires exactly these two existing recovery IDs before execution:

\`\`\`text
33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f
1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27
\`\`\`

Expected read-time state:

- P5-02Q edit record: valid, no attention, manifest committed, classification \`committed_then_changed\`;
- P5-02R restore record: valid, no attention, manifest committed, classification \`committed\`;
- total recovery count = 2;
- attention count = 0.

Any different recovery inventory blocks P5-02T before the move approval.

## Gate artifacts

\`\`\`text
scripts/phase5/p5-02t-first-production-move.ps1
scripts/phase5/p5-02t-first-production-move.py
\`\`\`

The PowerShell wrapper:

- requires the exact P5-02T branch and a clean working tree;
- requires Hermes manual-off;
- rejects ambient or persisted mutation/disposable settings;
- rechecks the accepted config and unrelated edit-canary baseline;
- requires exactly the two accepted recovery IDs;
- proves installed plugin code and manifest exactly match the P5-02N-qualified source;
- runs installed plugin doctor;
- compiles the Python runner before execution;
- does not persist mutation mode;
- does not start Hermes gateway;
- never auto-restores, deletes the target, or cleans recovery evidence.

The Python runner independently:

- binds both registered Orion move-preview/apply handlers to the exact verified installed \`plugin_dir\__init__.py\`;
- requires the private production executor to remain unregistered;
- validates the exact vault/inbox/recovery roots;
- requires production mutation disabled before preview;
- validates the exact two-record historical recovery baseline;
- rechecks exact source path, bytes, hash, and frozen Windows file identity;
- requires exact absent target and non-reparse paths;
- dispatches the registered move preview while mutation remains disabled;
- independently verifies every frozen plan field and the exact diff hash;
- rechecks source bytes/file ID and absent target after preview;
- enables \`ORION_P5_MUTATION_MODE=mutation_enabled\` only inside the child process immediately around one registered apply dispatch;
- requires a fresh Hermes human **ONCE** approval;
- removes mutation mode in a \`finally\` path;
- verifies source absent, target exact, and a new committed move recovery/receipt record;
- preserves state and recovery evidence on any failure.

## Expected live approval

Immediately before the protected mutation, the runner prints the exact frozen source, source file ID/hash, target, and full exact diff.

Proceed only if those values exactly match this document.

At the Hermes prompt, **ONCE** is the only accepted choice.

Session, always, denial, timeout, missing approval, reused approval, or any changed plan must fail closed.

## Expected successful post-state

A successful P5-02T run must leave:

- inbox source absent;
- vault target present at the exact canonical target path;
- vault target SHA-256 exactly
  \`132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132\`;
- a new recovery ID equal to the immutable P5-02T move plan token;
- new recovery action = \`move_draft\`;
- new recovery manifest state = \`committed\`;
- new recovery classification = \`committed\`;
- new recovery backup file = \`source.bin\`;
- new recovery backup SHA-256 = frozen source SHA-256;
- new receipt committed/finalized with no reconciliation requirement;
- approval surface = \`cli\`;
- approval choice = \`once\`;
- authorization reusable = false;
- production recovery inventory = exactly 3 valid records;
- recovery attention count = 0;
- previous P5-02Q/P5-02R records still valid with their accepted classifications;
- mutation mode absent/disabled after the bounded child process;
- COMPANION config and \`.env\` unchanged;
- installed Orion plugin unchanged;
- unrelated edit canary unchanged;
- Hermes manual-off.

Expected new recovery-directory entries:

\`\`\`text
manifest.json
receipt.json
source.bin
\`\`\`

## Failure policy

P5-02T never automatically undoes a partial or completed move.

If the registered apply is denied, errors, or reports any unclean state, the gate must stop and preserve observed state exactly as found.

In particular, the gate must not automatically:

- recreate the inbox source;
- delete the vault target;
- alter a new prepared/committed recovery record;
- delete or rewrite prior recovery records;
- invoke P5-02U;
- perform any second production mutation.

If a failure occurs after target creation or source removal, preserve both filesystem state and all recovery evidence for read-only reconciliation.

## P5-02U remains separate

P5-02T authorization does **not** authorize P5-02U.

A later P5-02U move-source restore, if separately authorized, may recreate the removed inbox source from the committed P5-02T \`source.bin\` recovery evidence.

That restore must not silently delete the vault target. Target deletion is a separate action class and remains separately approval-gated.

## Current stop point

P5-02T is authorized and the guarded gate is prepared on this branch.

The production move has **not** yet been executed by this repository preparation.

Do not update this document to PASS and do not update repository current-state claims until the Windows gate has actually run and its complete acceptance evidence has been reviewed.
