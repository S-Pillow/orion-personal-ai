# P5-02A Approval Integrity Source Candidate

Status: source-only candidate, not accepted for live installation or mutation. Based on P5-01 merged at `33c39d4` and pinned Hermes `v2026.8.27` (`5fc308a`).

## Goal and boundary

P5-02A prepares exact, approval-bound edit and draft-move plans. The live COMPANION plugin is not installed, enabled, or granted `iai-mcp` access by this branch. The registered `orion_vault_apply_plan` remains a fail-closed placeholder. No code on this branch applies an edit or move to a real vault or inbox.

Orion Master PRD v2.8 requires the exact operation/diff and canonical target in the approval payload, Hermes generic approval before any protected write, stale-plan rejection, and recoverable atomic execution. The current source candidate addresses only the plan and approval-message portion.

## Pinned-runtime discovery

- [Hermes approval gate](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L3732-L3784) accepts yolo and can auto-approve configured cron and single-query requests. It also supports cached session/permanent grants. These paths cannot be treated as a fresh human decision for a new vault plan.
- [Hermes hook invocation](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/hermes_cli/plugins.py#L5466-L5555) blocks a timed-out `pre_tool_call` callback but logs and drops its exception. [Tool dispatch](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/agent/tool_executor.py#L644-L672) returns no block directive when pre-tool dispatch itself raises. The plugin's own callback now catches internal errors, but it cannot protect against those runtime-level failures.
- [Hermes directive resolution](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/hermes_cli/plugins.py#L6620-L6660) blocks an ordinary approval-gate error or denial. That protection does not cover a missing directive after a hook/dispatch exception.
- [Hermes approval notification](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L3823-L3835) can send the approval description to a gateway client. An exact vault diff may contain private content; the intended approval channel and display policy need explicit review before activation.

## Approval-resolution investigation

The original pre-tool hook remains unsuitable as the only protected-write gate. Its directive can be omitted by a callback or dispatcher exception, and the handler cannot infer an approval from a block-message-or-`None` result ([dispatch path](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/hermes_cli/plugins.py#L6570-L6705), [executor exception path](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/agent/tool_executor.py#L644-L672)). A separate `post_approval_response` observer reports `choice` and `pattern_key` on interactive CLI and gateway decisions ([CLI](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L3911-L3929), [gateway](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L4607-L4624)). A flag keyed only by the public preview token would be unsafe across retries.

**Plugin-only candidate for isolated qualification:** the apply handler itself validates the cached plan, creates a fresh unpredictable *attempt key* that is never a tool argument, and synchronously calls Hermes `request_tool_approval` with the canonical target and exact diff. A registered `post_approval_response` hook records a short-lived marker only when the key and complete description match this pending attempt and the response is a fresh human `once`. After the generic gate returns, the same handler requires both `approved=True` and this matching marker, consumes them once, revalidates all file state, and only then may mutate. Missing/mismatched/late hook events, denial, timeout, callback error, and handler exceptions refuse the write. Session/always choices are rejected even if Hermes reports `approved=True`; a new attempt gets a new key. Yolo, cached grants, cron/single-query auto-approve, and a missing pre-tool directive also cannot produce the required fresh marker. The pre-tool hook can continue blocking invalid tokens but must not be the sole approval authority.

This candidate does not need the tool-call ID passed to a handler because the handler creates the attempt key and waits for its own gate call. Hermes currently passes task/session context but [no tool-call ID or resolved gate result to a plugin handler](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/model_tools.py#L1478-L1511); that remains a blocker for *pre-tool-only* receipt designs. Hermes treats observer hook errors as best effort ([hook implementation](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L108-L138)), so the handler must require a positive marker, never infer one from the gate's `approved` flag. The internal attempt map needs a lock, bounded TTL, and removal on every outcome; concurrent and late callbacks must never authorize a different attempt.

The new `tests/probe_hermes_approval.py` is an isolated probe of the pinned Python gate's result and hook signal for fresh `once`, session/always, denial/timeout, yolo, cached approval, cron/single-query auto-approval, and observer failure. It mocks the prompt and observer delivery, so it never requests human approval or reads a vault. Owner-run Windows execution from the stated Hermes venv on the P5-02A branch passed **3/3 in 0.025 s**. The non-interactive and single-query auto-approve warnings were expected probe cases: the gate returned approval while no fresh `once` signal was observed. The script is excluded from `test_p5*.py` discovery. **It does not prove full plugin dispatch, actual UI rendering, or privacy.** Those require separate isolated runtime tests. Approval display redacts descriptions on CLI and gateway ([CLI](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L3209-L3222), [gateway](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L3823-L3834)); any changed or truncated exact diff must block before a protected write. The intended channel and once-only choice must be verified on the real approval surface.

If the plugin-only candidate cannot establish all these invariants, the alternative is a Hermes protected-tool API that enforces fresh one-time approval inside core, fails closed on hook/dispatch exceptions, and carries an immutable invocation-bound decision to the handler. A Hermes source or version change requires separate owner review and pin qualification. **Neither candidate is authorized for live vault mutation by this source-only review.**

## Candidate source changes

- A fresh unpredictable nonce is included in each preview plan and its SHA-256 token. Recreating an identical edit produces a new plan-specific rule key rather than inheriting an earlier session/always grant for the same deterministic token.
- Edit and move preview records retain exact proposed bytes and exact diff in a bounded, expiring memory cache. Their public plan binds byte and diff hashes; the apply-tool schema still accepts only `plan_token`.
- The approval hook verifies cached bytes and diff against the plan, names the canonical target, and includes the exact unified diff. Missing, mismatched, or oversized content returns `action=block`.
- The apply handler is unchanged and always returns `p5_01_mutation_not_authorized`. A directive requesting approval is not evidence that Hermes obtained a human decision.

Local source tests use disposable roots. The existing P5-01 suite passed 16/16 and the new plan tests passed 4/4 in the scratch environment. On Windows, the owner ran `unittest discover -p "test_p5*.py" -v` against the checked-out P5-02A branch and reported 20/20 passing in 0.166 s. The pinned COMPANION Hermes `plugins doctor <source-dir> --ci` reported PASS for discovery, manifest parsing, import, and registration, with 4 tools and 1 hook. This is source-only verification; there is no live approval smoke.

## Dispatcher candidate (source only)

The source candidate now also registers a `post_approval_response` observer and contains an internal `_probe_fresh_once_approval` helper. The helper checks the cached plan/diff and redaction parity, creates a private per-invocation key, calls the generic Hermes approval gate, then requires both its approved result and an exactly matching human `once` observer event. Its attempt cache is bounded and cleared after every outcome. The registered `orion_vault_apply_plan` handler is **unchanged** and always refuses; the helper is test-only and performs no filesystem mutation. The existing pre-tool approval remains in place for that placeholder, so a future implementation must replace its valid-plan escalation before using the in-handler gate to avoid double prompts.

The local disposable-root suite now passes 23/23 (16 P5-01 plus 7 P5-02A). The new `tests/probe_hermes_dispatch.py` registers a synthetic tool only in its isolated process and uses the real Hermes `model_tools.handle_function_call` dispatcher and registry while routing the plugin hooks and supplying a simulated CLI answer. It checks fresh `once`, session, yolo, missing observer, and simulated pre-dispatch exception with no write. Owner-run Windows verification at `57a3ee3`: the source suite passed **23/23 in 0.158 s**, and the isolated Hermes dispatcher probe passed **2/2 in 0.080 s**. Hermes doctor imported and registered 4 tools / 2 hooks but warned that `post_approval_response` was not listed in the manifest. Owner-run Windows doctor at `ea4e138` passed discovery, manifest parsing, import, and registration with **4 tools / 2 hooks and no warnings**, resolving the declaration warning. Python plugin source was unchanged by that manifest fix. The dispatcher probe emitted a separate SQLite version warning from `async_delegation`; no Hermes runtime change is part of this ticket. These probes do not prove actual UI rendering or safe real mutation. Source coverage now also includes two adversarial approval-attempt tests: simultaneous attempts for the same public plan use distinct private keys and cannot authorize one another; a late callback after attempt removal is inert; and attempt-cache saturation refuses before calling the approval gate. These additions are committed at `893906b`; the P5-02A approval-plan suite is now 9 tests. Together with the accepted 16 P5-01 tests and the 12 P5-02B disposable mutation/recovery tests, `test_p5*.py` discovery is expected to run 37 tests. A fresh Windows rerun is required before any new result is recorded as PASS.

## HUD approval display candidate (source only)

Review of the actual Orion HUD found two exact-display blockers: `showApproval` preferred `command` over `description`, hiding the diff when both arrived, and truncated the selected text to 1,000 characters. The [pinned Hermes API event producer](https://github.com/NousResearch/hermes-agent/blob/5fc308a70719a83cccdbba4c0e39c23f5a8239d5/gateway/platforms/api_server.py#L7744-L7763) preserves separate command and description fields and advertises canonical choices. A standalone CLI prompt check would not satisfy the PRD's HUD approval-card requirement.

The HUD source now renders both fields completely using `textContent`, preserves whitespace and literal markup, and places long details in a keyboard-focusable scroll region. Existing Hermes-advertised choices and decision routing are retained. This does not make session/always acceptable for the vault helper; it still requires a fresh `once` marker.

Local verification: **3/3 executable JavaScript renderer tests** passed, including a long exact diff, CRLF, Unicode, literal HTML, command-only/description-only events, and choice filtering. The complete Python HUD suite passed **74/74**, including a new real-bridge test that forwards the full simulated approval description through SSE and posts simulated `deny` and `once` decisions. These are source/transport tests. The isolated Windows browser fixture has now completed both simulated DENY and ALLOW ONCE with `mutation_performed=false`, and after the Ctrl+C fixture correction it returned cleanly to PowerShell. That closes isolated decision-routing/shutdown behavior. Exact visual-display acceptance is now **PASS** by operator confirmation on Windows. The operator explicitly verified that the approval card visibly showed `orion_vault_apply_plan`, the fictional canonical target `C:\Orion-Disposable-Fixture\vault\note.md`, literal `<b>literal markup</b>` text without HTML interpretation, `+END-OF-DIFF-100`, and the final `\\ No newline at end of file` marker. This closes the isolated human visual-inspection gate; terminal logs alone were not used as substitute evidence. Full installed-Hermes approval-to-HUD delivery remains the next no-write gate.

### Next operator check: real Hermes no-write HUD approval

The isolated visual gate is accepted. The next gate uses the installed Hermes approval engine's real `request_tool_approval -> _await_gateway_decision -> resolve_gateway_approval` path and the candidate's real fresh-once observer logic, while still keeping the registered apply tool and the disposable mutation candidate completely out of execution.

Run after pulling this branch:

```powershell
git -C "D:\Orion\orion-personal-ai" pull --ff-only

& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  "D:\Orion\orion-personal-ai\hud\tests\probe_real_hermes_approval_surface.py"
```

The normal COMPANION gateway/service does **not** need to be started for this isolated probe.

Open the printed loopback URL. Select `orion-hud-main` under **SESSION** and send `probe`.

1. First run: choose **DENY**. The terminal must report `fresh_once=false; mutation_performed=false; note_unchanged=true`.
2. Send `probe` again.
3. Second run: choose **ALLOW ONCE**. The terminal must report `fresh_once=true; mutation_performed=false; note_unchanged=true`.
4. Press Ctrl+C to close the fixture.

The fixture intentionally exposes only `once` and `deny`; session/always are rejected at the fixture HTTP boundary and persistence callbacks are forbidden as a second safety belt. It imports the installed Hermes approval engine and uses its real gateway approval queue/resolver, but it does not install/discover the Orion plugin, start COMPANION, load a model, call the registered apply handler, invoke the disposable mutator, or touch the live vault/inbox. The approval lifecycle hook is routed directly to the candidate observer in-process so this test covers the candidate's private fresh-once marker without changing the installed plugin set.

Windows operator execution of this gate is now **PASS**. The real-Hermes no-write fixture produced:
- DENY -> `fresh_once=false; mutation_performed=false; note_unchanged=true`;
- ALLOW ONCE -> `fresh_once=true; mutation_performed=false; note_unchanged=true`;
- both approval POSTs returned HTTP 200 through the real Orion bridge/HUD path.

This closes the real Hermes approval-engine -> Orion HUD -> human decision -> fresh-once marker path. It still does not authorize filesystem mutation.

## Blockers before a mutating handler

1. Qualify the in-handler, one-time approval candidate against the pinned runtime so a pre-hook/dispatch exception, missing observer event, concurrency, or late callback cannot authorize a write. If it fails, design and separately qualify a fail-closed Hermes core change.
2. Require an observed fresh human `once` for each internal apply attempt; reject yolo, cron/single-query auto-approve, session/always choices, cached grants, and token replay. Confirm the choices available on the COMPANION/HUD surface.
3. Verify that the exact diff reaches the intended human approval surface without silent truncation or unacceptable disclosure through another configured gateway. The current 16,000-byte message cap is a source-side bound, not proof of delivery or privacy.
4. Implement and test atomic, recoverable edit/move execution with final containment and stale-state revalidation against disposable Windows roots. Run end-to-end denial, timeout, exception, replay, and approval tests in an isolated runtime before requesting live activation.

P5-02A source work may continue on this branch. No live plugin install, configuration grant, lifecycle restart, or real vault/inbox mutation follows from this candidate.
