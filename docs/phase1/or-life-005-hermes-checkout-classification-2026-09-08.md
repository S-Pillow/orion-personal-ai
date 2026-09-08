# OR-LIFE-005 Hermes Checkout Classification — 2026-09-08

Status: **PIN MATCH / TRACKED TREE CLEAN / ONE UNTRACKED BACKUP FILE**

Read-only classification of `C:\Users\spill\AppData\Local\hermes\hermes-agent` after v2.7.4 candidate Gate 1D preflight returned `HERMES_CHECKOUT_NOT_CLEAN`.

## Findings

- `git rev-parse HEAD` = `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (exact approved Hermes pin).
- `git diff --name-status` returned no tracked modifications.
- `git diff --cached --name-status` returned no staged modifications.
- The only untracked file is:
  - `plugins/platforms/discord/adapter.py.orion-pre-17157-20260829-224911.bak`
- `git diff --stat` and `git diff --cached --stat` were empty.

## Interpretation

The Hermes source checkout itself is at the approved pin with no tracked-source drift. The preflight block is caused solely by an Orion-created backup artifact retained inside the checkout from the earlier Discord #17157 investigation. The #17157 patch was not applied.

The backup must not be deleted casually. Before retrying preflight, preserve its hash and move/copy it to an Orion backup location outside the Hermes checkout, verify the external copy, then remove only the original untracked backup from the checkout. Do not run `git reset`, `git clean`, `git checkout`, `git restore`, or `git stash`.

Core Intent Preservation: **PRESERVED**.
