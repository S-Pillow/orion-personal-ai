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

The new `tests/probe_hermes_approval.py` is an isolated probe of the pinned Python gate's result and hook signal for fresh `once`, session/always, denial/timeout, yolo, cached approval, cron/single-query auto-approval, and observer failure. It mocks the prompt and observer delivery, so it never requests human approval or reads a vault. Run it explicitly with the pinned Hermes venv Python; it is excluded from `test_p5*.py` discovery. **It does not prove full plugin dispatch, actual UI rendering, or privacy.** Those require separate isolated runtime tests. Approval display redacts descriptions on CLI and gateway ([CLI](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L3209-L3222), [gateway](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L3823-L3834)); any changed or truncated exact diff must block before a protected write. The intended channel and once-only choice must be verified on the real approval surface.

If the plugin-only candidate cannot establish all these invariants, the alternative is a Hermes protected-tool API that enforces fresh one-time approval inside core, fails closed on hook/dispatch exceptions, and carries an immutable invocation-bound decision to the handler. A Hermes source or version change requires separate owner review and pin qualification. **Neither candidate is authorized for live vault mutation by this source-only review.**

## Candidate source changes

- A fresh unpredictable nonce is included in each preview plan and its SHA-256 token. Recreating an identical edit produces a new plan-specific rule key rather than inheriting an earlier session/always grant for the same deterministic token.
- Edit and move preview records retain exact proposed bytes and exact diff in a bounded, expiring memory cache. Their public plan binds byte and diff hashes; the apply-tool schema still accepts only `plan_token`.
- The approval hook verifies cached bytes and diff against the plan, names the canonical target, and includes the exact unified diff. Missing, mismatched, or oversized content returns `action=block`.
- The apply handler is unchanged and always returns `p5_01_mutation_not_authorized`. A directive requesting approval is not evidence that Hermes obtained a human decision.

Local source tests use disposable roots. The existing P5-01 suite passed 16/16 and the new plan tests passed 4/4 in the scratch environment. On Windows, the owner ran `unittest discover -p "test_p5*.py" -v` against the checked-out P5-02A branch and reported 20/20 passing in 0.166 s. The pinned COMPANION Hermes `plugins doctor <source-dir> --ci` reported PASS for discovery, manifest parsing, import, and registration, with 4 tools and 1 hook. This is source-only verification; there is no live approval smoke.

## Blockers before a mutating handler

1. Qualify the in-handler, one-time approval candidate against the pinned runtime so a pre-hook/dispatch exception, missing observer event, concurrency, or late callback cannot authorize a write. If it fails, design and separately qualify a fail-closed Hermes core change.
2. Require an observed fresh human `once` for each internal apply attempt; reject yolo, cron/single-query auto-approve, session/always choices, cached grants, and token replay. Confirm the choices available on the COMPANION/HUD surface.
3. Verify that the exact diff reaches the intended human approval surface without silent truncation or unacceptable disclosure through another configured gateway. The current 16,000-byte message cap is a source-side bound, not proof of delivery or privacy.
4. Implement and test atomic, recoverable edit/move execution with final containment and stale-state revalidation against disposable Windows roots. Run end-to-end denial, timeout, exception, replay, and approval tests in an isolated runtime before requesting live activation.

P5-02A source work may continue on this branch. No live plugin install, configuration grant, lifecycle restart, or real vault/inbox mutation follows from this candidate.
