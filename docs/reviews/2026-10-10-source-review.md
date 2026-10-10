# Orion source review and bug fixes — 2026-10-10

Reviewed baseline: `main` at `2210b6a6cdc39e67c0ece151b15e1cf2e61d1d7c`.

## Scope and conclusion

The review traced the HUD HTTP routes, stream delivery/projection, browser session and reconnect state, operator lifecycle/provenance checks, and selected vault approval/revalidation/recovery paths. It also examined the existing test coverage, CI triggers, README, and open integration PR metadata. It is a targeted correctness review, not certification that every repository path or the installed runtime is defect-free.

The original local suites were green, but the browser tests mostly exercised individual presentation helpers or static source contracts. Controlled response-order tests exposed real state races in the asynchronous application functions. The new Windows CI also exposed an existing disposable-vault path-alias guard failure. Fixes cover the HUD, that source-only guard, tests, CI, and documentation. No installed runtime, dependency pin, production vault executor, scheduler, or deployment setting was changed.

## Confirmed findings and corrections

| Finding | User-visible consequence | Correction |
| --- | --- | --- |
| History responses were not bound to the selected session or latest request. | Switching sessions quickly could display the previous conversation under the new session. An old error could erase newer history. | Check the session and request sequence after success and failure; suppress reads during streaming; invalidate pre-turn reads. |
| Action-evidence hydration could finish after a live approval appeared. | An empty or failed old response could clear the live action projection; an older same-session result could replace newer evidence. | Reject superseded evidence requests and responses arriving during streaming/approval. |
| Reconnect checked freshness inconsistently across awaits. | A stale result could adopt an old run, hide a new approval, or overwrite a newer terminal observation. The status-refresh caller could also set READY during a new turn. | Recheck request sequence, session, locator, streaming, and approval state after awaits; guard the caller's final presentation. |
| Recovered active runs did not count as busy unless streaming. | Enter could submit a second turn, and session controls could abandon the run locator while STOP still targeted the old run. | Disable new-turn/session controls for an observed active run and guard submission/creation handlers. |
| Expired runs and disappeared sessions retained stale state. | STOP could continue targeting an expired/deleted session's run; old transcript content could remain after the selection was cleared. | Clear expired active targets and clear transcript/control state when the session disappears. A transient lookup preserves an already-authoritative STOP target; on fresh reload a locator-only reconnect interlock blocks competing turns/session changes without exposing STOP or claiming active-run authority until Hermes confirms a nonterminal run. |
| Approval choice validation performed set membership before checking type. | A JSON array or object caused an unhandled `TypeError` and connection drop. | Require a string before accepting canonical choices; invalid values return HTTP 400 without contacting Hermes. |
| Disposable-root guard compared canonical candidates with unresolved protected paths. | Parent aliases or Windows short-name spellings could defeat the intended protected-root overlap rejection. The new Windows job exposed the existing failure; the enhanced alias test reproduced it on Linux too. | Resolve both candidate and protected roots before the second overlap check, retaining the original raw-path checks. The unregistered disposable guard is the only vault runtime helper changed. |
| Ordinary pull requests had no general source-test gate. | The existing HUD workflow ran only on two named historical branches, and Phase 6 prep CI did not cover normal HUD changes. | Add Linux/Windows PR and main-branch source tests, including all Node test files. Include new tests in the existing visual workflow too. |
| README described qualified P6-05 work as an uncommitted twelve-file change. | Operators were directed to an obsolete finalizer instead of the current integration path. | Record the merged P6-04A foundation and open P6-05 PR #59; mark the earlier finalization flow historical. |

## Verification

Local environment: Linux, Python 3.12, Node; disposable files and synthetic loopback Hermes fixtures only.

| Gate | Result |
| --- | --- |
| HUD Python suite | 204 passed |
| Vault Python suite | 126 passed, 10 Windows-only tests skipped |
| Operator provenance suite | 14 passed |
| Node browser-logic suite | 42 passed, including 17 new async/control cases |
| Changed Python compile and app.js syntax | Passed |
| Workflow YAML parse and `git diff --check` | Passed |

Total: **386 passed, 10 skipped**. The new approval regression reproduces connection drops on the unchanged baseline. The async regression file also fails against the original `app.js`, covering stale responses and competing-turn submission rather than only checking source text. Positive cases preserve fresh active-run adoption and transient-error STOP behavior.

Reproduction commands:

```text
python -m unittest discover -s hud/tests -p "test_*.py"
python -m unittest discover -s hermes_plugins/orion-vault-actions/tests -p "test_*.py"
python -m unittest discover -s tests/operator -p "test_*.py"
node --test hud/tests/*.cjs
```

## Remaining qualification and integration boundaries

- This checkout cannot prove native Windows lifecycle behavior, live Hermes/Discord behavior, or installed vault permissions. The new Windows CI job exercises source fixtures, not the user's installed COMPANION runtime.
- Playwright was not installed in the local review environment, so the existing visual/reconnect browser-capture gates were not rerun locally. The new Node tests execute the actual async functions with controlled API timing; they do not replace a full browser acceptance run.
- PR #59 was open at head `d887d5994d343ea2b58f97e932f1181c095d9be6`. A read-only `git merge-tree` simulation confirmed a content conflict in `hud/static/app.js`; the bridge merged automatically. Whichever PR merges second must resolve that conflict, review the combined diff, and rerun its expanded reminder/HUD qualification. Its reminder adapter is not part of this main-branch fix.
- The first Windows CI run passed the HUD suite but failed the existing protected-parent-alias vault test. The guard correction was then reproduced locally with a protected-side alias and verified through the full disposable suite. Hosted Windows source fixtures and live installed-runtime acceptance remain separate evidence categories.
- Merge, installation, live reminder acceptance, and deployment were not performed.
