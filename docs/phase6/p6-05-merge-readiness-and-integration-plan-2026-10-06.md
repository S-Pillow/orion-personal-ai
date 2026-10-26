# P6-05 Reminder CRUD + HUD — Merge Readiness and Integration Plan

Status: **IMPLEMENTATION QUALIFIED / COMMITTED / PUSHED; DIRECT MERGE BLOCKED BY BRANCH HISTORY**

Date: 2026-10-06

## Current qualified implementation

P6-05 is complete as a repository implementation on:

- branch: `feature/p6-05-reminder-crud-hud`
- commit: `b255aeb4a86daa2fc2a54688a2cae7a4b9ec9456`
- commit subject: `feat: add Hermes-backed reminder CRUD HUD`

The commit contains exactly 16 P6-05 files and was produced from parent:

- `69309e1559428ffee0455ed9f476222600e392a4`

Post-correction qualification completed successfully:

- reminder regression suite: **41/41 PASS**
- full HUD regression suite: **244/244 PASS**
- JavaScript syntax check: PASS
- Python compile checks: PASS
- `git diff --check`: PASS
- exact 16-file scope: PASS
- local working tree after commit: clean
- remote feature branch SHA verification: PASS

The final uncertainty correction also proved:

- mutations do not depend on post-mutation execution-history lookup;
- a post-mutation projection failure does not retry create;
- mutation-side 5xx responses are projected as outcome `uncertain`;
- unavailable adapter is treated as a definite pre-mutation failure;
- the HUD performs read-only reconciliation before retry and blocks further mutation if state cannot be confirmed.

No live reminder, Discord delivery, COMPANION configuration change, Hermes restart, deploy, or P6-06 action was performed by P6-05 qualification.

## Current main and topology blocker

Current `main` is:

- `5da4a9a326423e02f5d00b40a59c4192a10321a0`

GitHub compare reports:

- merge base: `5ab6f44ae4c87044dcff528fef8e75345b703e74`
- feature branch relative to current `main`: **96 commits ahead / 4 commits behind**
- the 96 ahead commits comprise the 95-commit Phase 6 history already present before P6-05 plus the single P6-05 implementation commit.

The four commits added to `main` after the merge base are documentation/checkpoint commits from the 2026-10-05 P6-05 handoff. They modify:

- `README.md`
- `docs/phase6/p6-05-correction-resume-plan-2026-10-05.md`
- `scripts/phase6/Invoke-P6-05-FinalizeCorrection.ps1`

The P6-05 implementation commit modifies 16 HUD/test files and does not include those documentation paths.

### Blocker

Do **not** directly merge `feature/p6-05-reminder-crud-hud` into `main` and do **not** open a normal merge PR from that branch to `main`.

A direct branch merge would import the branch's 95 pre-P6-05 commits that are not in current `main`, expanding the integration far beyond the authorized P6-05 unit.

This is a history/topology blocker, not an implementation-quality blocker.

## Research basis for the integration method

The integration method was checked against current Git documentation:

1. `git merge-base` identifies the best common ancestor for two histories. The repository comparison confirms `5ab6f44...` as the common base between current `main` and the P6-05 feature line.
2. `git cherry-pick` applies the change introduced by a specified commit onto the current branch and requires a clean working tree. This is the correct primitive when only the P6-05 commit should be transferred instead of merging the entire feature history.
3. `git cherry-pick -x` adds the source commit identity to the new commit message. Git documents this as useful when cherry-picking between publicly visible branches; both Orion branches are published on GitHub, so `-x` provides useful provenance.
4. If a cherry-pick conflicts, Git records `CHERRY_PICK_HEAD`; `git cherry-pick --abort` returns to the pre-sequence state. The planned integration must stop and abort rather than improvise conflict resolution under the same authorization.
5. `git patch-id --stable` provides a stable identifier for a patch and is suitable for verifying that the integrated commit represents the same change as the qualified source commit despite receiving a new commit SHA.

Reference documentation:

- https://git-scm.com/docs/git-merge-base
- https://git-scm.com/docs/git-cherry-pick
- https://git-scm.com/docs/git-patch-id

## Pre-integration proof required

Before any cherry-pick, the integration unit should prove all of the following:

1. local repository is clean;
2. current `origin/main` is exactly `5da4a9a326423e02f5d00b40a59c4192a10321a0` unless a later read-only review explicitly requalifies a newer main;
3. source commit is exactly `b255aeb4a86daa2fc2a54688a2cae7a4b9ec9456`;
4. source parent is exactly `69309e1559428ffee0455ed9f476222600e392a4`;
5. the 16 P6-05 paths have identical preimages between `origin/main` and the source parent;
6. the source commit touches exactly those 16 paths;
7. there is no cherry-pick already in progress.

The preimage check is important. It verifies the actual files the patch expects, rather than assuming a commit applies merely because a high-level compare reported no overlapping documentation paths.

## Authorized integration design — not yet executed

The next integration unit should be deliberately narrow:

1. Fetch refs read-only.
2. Verify exact `origin/main`, source commit, source parent, clean worktree, and no sequencer/cherry-pick state.
3. Create a **fresh integration branch from current `origin/main`**. Do not rebase or rewrite the qualified feature branch.
4. Verify identical preimages for all 16 P6-05 paths between `origin/main` and `b255aeb4^`.
5. Cherry-pick **only** `b255aeb4a86daa2fc2a54688a2cae7a4b9ec9456` using `git cherry-pick -x`.
6. If Git reports any conflict, run `git cherry-pick --abort`, verify the integration branch returned to its starting commit, and stop. No conflict resolution should be improvised in that unit.
7. Verify the resulting commit touches exactly the same 16 paths.
8. Compare stable patch IDs for the source P6-05 commit and the integration commit. They must match.
9. Run compile checks, JavaScript syntax check when Node is available, the 41 reminder tests, the complete HUD test suite, and `git diff --check`.
10. Verify the integration branch is exactly one commit ahead of its main base and that the working tree is clean.
11. Do not push or merge until the integration result is separately reviewed and authorized.

## Why the qualified feature branch stays untouched

The existing feature branch is evidence. It contains the exact qualified P6-05 commit that passed the final 41/41 and 244/244 gates and was remote-SHA verified.

Rebasing it, force-pushing it, or merging `main` into it before integration would alter that evidence and make diagnosis harder. The fresh-main cherry-pick model separates:

- the immutable qualified source commit;
- the current-main integration candidate;
- the later documentation closure.

## Documentation drift to close after integration qualification

Current main documentation predates final P6-05 qualification. The 2026-10-05 resume document still describes the implementation as local/final-qualification-pending and points to the old finalization script.

After a main-based integration candidate is qualified, a separate documentation closure should record:

- final P6-05 implementation commit and integration commit;
- 41/41 reminder and 244/244 HUD acceptance;
- uncertainty-semantics correction;
- feature-branch push verification;
- history/topology blocker and selective-integration method;
- final integration qualification result;
- P6-06 remains separate and still requires live Discord-destination qualification and explicit production authorization.

The obsolete `Invoke-P6-05-FinalizeCorrection.ps1` should be retired or clearly marked historical only after the integration candidate is accepted. Do not use it against the completed P6-05 implementation.

## Lessons carried forward from the correction session

The P6-05 correction sequence exposed tooling failures that must not be repeated:

- do not use brittle exact-string source transforms when semantic/AST-scoped edits or plain reviewed patches are available;
- do not pass raw Git blob data through Windows PowerShell text pipelines when byte identity matters;
- prefer Git object identity (`rev-parse`, `cat-file`, `hash-object`) for artifact verification;
- verify transformation/self-test fixtures independently before asking the operator to run them;
- make failure gates stop the entire execution unit so later unconditional PASS markers cannot run after failure;
- use exact precondition hashes or semantic preimage checks before mutation;
- keep a mutation helper small: repair one thing, then run ordinary direct qualification commands;
- preserve qualified evidence branches instead of rewriting them merely to make history look cleaner.

These are process controls, not reasons to change the P6-05 architecture.

## Current next action

P6-05 is **ready for a main-based cherry-pick integration qualification**, not ready for a direct feature-branch merge.

No integration branch, cherry-pick, push, PR, merge, deployment, Hermes restart, reminder creation, Discord delivery, COMPANION mutation, or P6-06 work is authorized by this document alone.
