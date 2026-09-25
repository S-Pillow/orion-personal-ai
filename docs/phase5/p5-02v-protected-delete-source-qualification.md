# P5-02V — Protected Delete Source Qualification

Status: **AUTHORIZED / SOURCE IMPLEMENTED / WINDOWS QUALIFICATION PENDING**

Authorization date: 2026-09-25

Branch: `feature/orion-phase5-p5-02v-protected-delete`

Baseline: `main` after accepted P5-02U merge
`1d8a197b3a546020f6c0c4ce0c04fbfff315c23f`.

## Closure authorization

Owner authorization covers the remaining explicitly named Phase 5 closure work:

1. protected deletion of the retained P5-02T vault target;
2. later cleanup of the retained Phase 5 recovery evidence.

This is **not** blanket authorization for unrelated future mutations.

The two destructive concerns remain separate gates. P5-02V implements and
source-qualifies the protected delete action only. Recovery pruning is not
implemented or performed in P5-02V.

## Intent-preservation check

The existing recovery contract requires target deletion after a move-source
restore to be a **separate protected delete plan with a fresh exact approval**.

P5-02V therefore does not use a direct PowerShell `Remove-Item` shortcut.

The implementation preserves the accepted architecture:

- Hermes remains the sole approval authority;
- preview is read-only;
- exact target/hash/diff are bound into an immutable plan token;
- the registered `orion_vault_apply_plan` remains the only mutation entry;
- explicit `mutation_enabled` is still required;
- the private executor remains unregistered;
- one fresh human `once` approval authorizes one exact delete attempt;
- state is revalidated after human approval;
- recovery is written before deletion;
- stale/changed/missing/ambiguous state fails closed.

## Source changes

Plugin source version advances from `0.2.0` to source candidate `0.3.0`.

New read-only tool:

`orion_vault_preview_delete`

The preview accepts only:

`target_relative_path`

and returns:

- canonical contained Markdown target;
- current SHA-256;
- Windows file identity when available;
- exact current-file -> `/dev/null` unified diff;
- target state `present`;
- immutable plan token;
- `mutation_performed=false`.

The existing public apply tool schema remains plan-token only.

## Protected delete execution

The private production executor now recognizes `delete_note`.

Before deletion it must:

- re-resolve containment;
- require the same canonical path;
- require the preview-bound hash;
- require the preview-bound Windows file identity on Windows;
- re-run recovery inventory and require zero attention;
- require fresh human `once` evidence;
- create a new recovery directory;
- durably write the exact target bytes to `deleted_target.bin`;
- write schema-v2 prepared manifest and receipt;
- re-read the protected object immediately before delete.

Deletion then uses the existing Windows retained-handle/delete-mark mechanism
when on Windows. The postcondition requires the target to be absent before the
recovery record and receipt are committed.

A committed delete recovery record classifies as:

- `committed` while the target remains absent;
- `committed_then_changed` if the target later reappears.

Prepared records remain restart-classifiable as no-effect, applied-unfinalized,
or divergent.

## Recovery semantics

A delete transaction creates its own durable recovery record containing:

- `deleted_target.bin`;
- `manifest.json`;
- `receipt.json`.

P5-02V does **not** add automatic recovery cleanup.

It also does not add an automatic delete-restore operation. The backup exists
so the destructive action is recoverable/evidenced; any later restore would
remain a separately designed and approved operation.

## Source qualification gate

Run:

`scripts/phase5/p5-02v-protected-delete-source-qualification.ps1`

with token:

`I_AUTHORIZE_P5_02V_DELETE_SOURCE_QUALIFICATION`

The qualification gate is read-only with respect to accepted production state.
It:

- requires Hermes manual-off;
- requires the P5-02U source and target both at the frozen hash;
- requires exactly the four accepted recovery IDs;
- proves the live installed plugin still matches P5-02N-qualified source;
- compiles the P5-02V source;
- runs all `test_p5*.py` regressions;
- runs Hermes plugin doctor against the **source tree**;
- confirms live installed plugin/config/.env/files/recovery remain unchanged.

## Regression coverage

P5-02V adds tests for:

- side-effect-free exact delete preview;
- stale hash revalidation refusal;
- disabled-mode pre-tool refusal;
- recovery-before-delete successful production candidate;
- failure after recovery preserving target and evidence;
- committed delete becoming `committed_then_changed` if the target reappears;
- Windows preview file-identity binding.

Existing registration regression tests are updated for the fifth read-only tool
and source manifest version `0.3.0`.

## Current production boundary

Before P5-02V qualification:

- installed plugin remains accepted `0.2.0` / P5-02N-qualified source;
- production recovery remains 4 valid records / 0 attention;
- restored inbox source is present at SHA-256
  `132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132`;
- retained vault target is present at the same SHA-256;
- mutation mode is disabled;
- Hermes is manual-off.

## Required sequencing after P5-02V

If source qualification passes:

- **P5-02W** — install/qualify plugin `0.3.0` with mutation disabled;
- **P5-02X** — execute the exact protected vault-target delete with a fresh
  human `once` approval;
- **P5-02Y** — define and execute the exact owner-approved recovery-retention
  cleanup only after the final post-delete recovery set is known.

P5-02Y must satisfy the existing retention contract: no unresolved/attention
records may be pruned, the exact records selected for removal must be explicit,
and an audit record of what was removed must be retained.

## Current stop point

P5-02V source is prepared. No source qualification result has yet been accepted.

No live plugin install, target deletion, recovery cleanup, config change, Hermes
start, or production mutation has been performed by this source-preparation
work.
