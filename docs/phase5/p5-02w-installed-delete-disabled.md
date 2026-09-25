# P5-02W — Installed Protected-Delete Plugin, Mutation Disabled

Status: **AUTHORIZED / GATE PREPARED / WINDOWS EXECUTION PENDING**

Authorization date: 2026-09-25

Branch: `feature/orion-phase5-p5-02w-installed-delete-disabled`

Baseline: `main` after accepted P5-02V merge
`fbeeb800dd20d57ab4a0e0fcd8225ce51d71adbb`.

Qualified protected-delete source:
`211255ff9abfa04101760c7e3358b521a3e530ae`.

Accepted currently installed source:
`faf8b4787d8e6fb668eb5e9d754104910b4b401a`.

## Purpose

P5-02W installs exactly the P5-02V-qualified Orion vault-actions plugin
`0.3.0` into the COMPANION profile while production mutation remains disabled.

This is an installed/runtime qualification gate only.

It does **not** authorize or perform the P5-02X target deletion.

## Installed candidate

Plugin source version:

`p5-02v-0.3.0`

Manifest version:

`0.3.0`

Registered Orion toolset after installation must contain exactly:

- `orion_vault_preview_edit`
- `orion_vault_preview_move_draft`
- `orion_vault_preview_delete`
- `orion_vault_recommend_destination`
- `orion_vault_apply_plan`

The private production executor must remain unregistered.

The public apply schema remains plan-token only.

## Required pre-state

P5-02W requires:

- Hermes manual-off before installation;
- installed plugin still exactly matching the accepted P5-02N `0.2.0` source;
- source candidate exactly matching the accepted P5-02V source commit;
- mutation mode absent/disabled;
- config and `.env` unchanged from accepted baseline;
- restored move source present at frozen SHA-256;
- retained vault target present at frozen SHA-256;
- unrelated edit canary at accepted restored hash;
- exactly the four accepted P5-02U recovery IDs;
- no recovery attention state.

## Gate behavior

Operator gate:

`scripts/phase5/p5-02w-installed-delete-disabled.ps1`

Runtime verifier:

`scripts/phase5/p5-02w-installed-delete-disabled-verify.py`

The PowerShell gate:

1. verifies manual-off using the actual TCP listener on port 8642;
2. validates the accepted P5-02U production state;
3. fingerprints every production recovery evidence file;
4. backs up current plugin/config/.env for rollback;
5. proves the installed plugin matches accepted P5-02N source;
6. proves the new source matches the P5-02V-qualified commit;
7. doctors the qualified source;
8. atomically replaces the installed plugin directory with the exact qualified source tree;
9. doctors the installed location;
10. confirms production files/recovery/config/.env remain unchanged;
11. starts COMPANION temporarily for disabled-runtime verification;
12. runs the installed runtime verifier;
13. stops COMPANION and requires port 8642 no longer listening;
14. rechecks every protected production artifact.

If installation or runtime verification fails after replacement, the gate restores
the previous plugin from the rollback capture and preserves production evidence.

## Installed runtime verifier

While mutation remains disabled, the runtime verifier requires:

- internal plugin version `p5-02v-0.3.0`;
- exactly five registered Orion tools;
- delete preview handler is `preview_delete`;
- guarded public apply handler is unchanged;
- private production executor remains unregistered;
- delete preview schema exposes only `target_relative_path`;
- public apply schema exposes only `plan_token`;
- native production-root validation succeeds but reports mutation disallowed;
- exact four-record P5-02U recovery baseline remains valid with zero attention;
- a disposable delete preview succeeds without deleting its temporary fixture;
- disabled pre-tool apply blocks before approval;
- disabled public apply refuses before private executor entry;
- no approval attempt is created;
- live authenticated `orion_vault` toolset contains exactly five expected tools.

## Production recovery baseline

Expected IDs and read-time classifications:

- `33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f`
  — `edit_note` — `committed_then_changed`
- `1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27`
  — `restore_edit` — `committed`
- `8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6`
  — `move_draft` — `committed_then_changed`
- `5c9b264a465f468c2f172f880fc89878e63368480c3eecfd0fb37212b159e175`
  — `restore_move_source` — `committed`

## Expected successful post-state

- installed plugin exactly matches the P5-02V qualified source;
- installed plugin manifest version = `0.3.0`;
- protected delete preview registered live;
- production mutation mode remains absent/disabled;
- production recovery remains exactly 4 records / 0 attention;
- recovery evidence fingerprint unchanged;
- restored inbox source unchanged;
- retained vault target unchanged;
- edit canary unchanged;
- config unchanged;
- `.env` unchanged;
- Hermes returned to manual-off;
- no production mutation invoked.

## Current stop point

P5-02W gate is prepared. The live installed plugin is still `0.2.0` until the
Windows gate executes successfully.

P5-02X target deletion and P5-02Y recovery cleanup remain later closure gates.
