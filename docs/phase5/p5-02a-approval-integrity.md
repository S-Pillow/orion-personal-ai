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

A second supported-looking hook exists, but it does not yet close the protected-write gate. Hermes emits `post_approval_response` with `choice`, `pattern_key`, session and tool-call correlation for CLI and gateway responses ([hook context](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L108-L138), [gateway response](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L4607-L4624), [CLI response](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/tools/approval.py#L3911-L3929)). In principle an Orion observer could accept only a fresh `once` choice for its plan key; bypassed or cached grants do not emit that fresh response on the short-circuit path. The pinned hook dispatcher logs and swallows observer failures, and this is an observation hook rather than a trusted approval receipt.

Critically, the plugin handler is called with task/session/user-task context but [no `tool_call_id` or resolved approval result](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/model_tools.py#L1478-L1511). The approval hook's correlation cannot be bound through a supported handler argument to the *same invocation*, especially after an error, retry, or concurrent call. A token-keyed in-memory "approved" flag would leave an ambiguous interval between response and execution. The runtime also returns only a block message or `None` from the [pre-tool dispatcher](https://github.com/NousResearch/hermes-agent/blob/v2026.8.27/hermes_cli/plugins.py#L6570-L6705), so a plugin handler cannot distinguish a resolved approval from a bypass, cache hit, missing directive, or dispatcher exception through that result. Keep the apply placeholder disabled.

**Required resolution contract for any mutating implementation:** a supported, per-invocation approval result must reach the protected handler or a mandatory core gate bound to the exact action/plan and tool call. The gate must block when a hook is missing, raises, or times out; reject yolo and non-human/previously cached decisions for a protected write; offer or enforce one-time consent; and consume the plan on the first attempted execution. The exact diff and canonical target must be confirmed on the actual human surface before executing. A Hermes source change, version change, or new protected-tool API needs separate owner review and qualification against the pin. Configuration alone does not repair the hook/dispatch exception path.

## Candidate source changes

- A fresh unpredictable nonce is included in each preview plan and its SHA-256 token. Recreating an identical edit produces a new plan-specific rule key rather than inheriting an earlier session/always grant for the same deterministic token.
- Edit and move preview records retain exact proposed bytes and exact diff in a bounded, expiring memory cache. Their public plan binds byte and diff hashes; the apply-tool schema still accepts only `plan_token`.
- The approval hook verifies cached bytes and diff against the plan, names the canonical target, and includes the exact unified diff. Missing, mismatched, or oversized content returns `action=block`.
- The apply handler is unchanged and always returns `p5_01_mutation_not_authorized`. A directive requesting approval is not evidence that Hermes obtained a human decision.

Local source tests use disposable roots. The existing P5-01 suite passed 16/16 and the new plan tests passed 4/4 in the scratch environment. On Windows, the owner ran `unittest discover -p "test_p5*.py" -v` against the checked-out P5-02A branch and reported 20/20 passing in 0.166 s. The pinned COMPANION Hermes `plugins doctor <source-dir> --ci` reported PASS for discovery, manifest parsing, import, and registration, with 4 tools and 1 hook. This is source-only verification; there is no live approval smoke.

## Blockers before a mutating handler

1. Prove a supported fail-closed path when the hook callback or pre-tool dispatcher raises, not just when approval itself denies or times out. Any candidate Hermes patch or dependency change requires separate owner approval and qualification against the accepted pin.
2. Prevent yolo, cron/single-query auto-approve, and cached grants from satisfying the *fresh human approval* requirement for a new vault plan. Confirm which choices the COMPANION/HUD surface actually offers and ensure token replay cannot authorize a second write.
3. Verify that the exact diff reaches the intended human approval surface without silent truncation or unacceptable disclosure through another configured gateway. The current 16,000-byte message cap is a source-side bound, not proof of delivery or privacy.
4. Implement and test atomic, recoverable edit/move execution with final containment and stale-state revalidation against disposable Windows roots. Run end-to-end denial, timeout, exception, replay, and approval tests in an isolated runtime before requesting live activation.

P5-02A source work may continue on this branch. No live plugin install, configuration grant, lifecycle restart, or real vault/inbox mutation follows from this candidate.
