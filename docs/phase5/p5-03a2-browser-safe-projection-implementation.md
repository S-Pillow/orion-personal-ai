# P5-03A2 — Browser-Safe Projection Implementation

Status: **IMPLEMENTED ON FEATURE BRANCH / LOCAL ACCEPTANCE REQUIRED**

Branch: `feature/orion-phase5-p5-03a2-browser-safe-projection`

Base main: `1128b17224a0b02610aac88bfab3e4b0e22b9c04`

## Scope

This unit implements the browser-safe projection portion of the accepted
P5-03A1 contract after the session-chat approval compatibility transport passed
bounded runtime qualification.

It does not change Hermes, the vault mutation engine, approval authority,
recovery semantics, mutation mode, voice, memory, or lifecycle ownership.

## Implemented authority boundary

- Hermes remains session/run/tool/approval runtime authority.
- The vault plugin remains protected-action executor and structured result authority.
- The Orion bridge constructs a new allowlisted presentation object for
  consequential SSE/action evidence instead of forwarding raw consequential
  upstream objects to the browser.
- The browser remains presentation only.

## Projection behavior

The implementation adds `hud/action_projection.py` with versioned
`orion.action-projection.v1` objects.

It distinguishes `preview_ready`, `approval_requested`,
`approval_accepted`, `approval_denied`, `succeeded`, `failed`,
`refused`, `stale_plan`, `unknown`, `unobserved`, and
`unavailable`.

It does not synthesize protected `executing` or `retry_available`.

Primary stale classification requires both
`mutation_performed=false` and `recovery_required=false`.
`source_changed_before_delete` remains a failed/recovery-required result, not
a routine stale refusal.

## Browser egress hardening

The bridge now:

- parses session SSE server-side;
- allowlists approval content and removes rule/pattern keys and raw tool args;
- strips raw `run.completed.messages` from the browser stream and replaces
  them with bounded action evidence;
- sanitizes the ordinary transcript endpoint to user/assistant display rows;
- adds read-only
  `GET /api/orion/sessions/{session_id}/action-evidence` hydration derived
  from authoritative persisted Hermes session messages;
- allowlists `GET /api/orion/runs/{run_id}`;
- turns a successful approval POST into a decision-only Orion projection with
  `execution_proven=false`;
- never exposes recovery directory paths, preview nonces, proposed bytes,
  arbitrary raw tool arguments, stack/error text, or provider secrets through
  the action projection.

Persisted preview history never recreates current plan actionability. Hydration
reports historical preview evidence with current actionability unavailable.

## Browser truth behavior

The current HUD consumes the projection without beginning the P5-03B visual
redesign.

In particular:

- approval acceptance is shown as a decision while execution evidence remains pending;
- generic `tool.completed` remains descriptive tool activity only;
- authoritative vault result on `run.completed` controls protected outcome;
- a structured plugin failure overrides generic run/tool completion;
- approval visuals are cleared on terminal run failure;
- completed action evidence is rehydrated from the new read-only server
  projection after transcript load.

## Runtime evidence before implementation

The installed P5-03A2 Hermes compatibility patch passed bounded runtime
qualification at installed SHA
`7a206396aac7abe7e50fd5d346733fea85bb57160cb0a5d8a2e7feda29167c84`.

Observed acceptance included health/readiness, capabilities, two ordinary
session-chat turns, session continuity, unique run IDs, completed-run approval
cleanup/isolation, persisted session messages, no actual tool activity, no
approval request, no protected action, clean stop, unchanged installed source,
unchanged rollback evidence, and a clean Orion worktree.

## Required acceptance

Before merge:

1. Python parse all changed Python files.
2. Run existing HUD unit suite.
3. Run `hud/tests/test_action_projection.py`.
4. Run `hud/tests/test_projection_bridge.py`.
5. Run existing Node approval-rendering test.
6. Confirm no raw consequential `run.completed.messages` reaches the browser.
7. Confirm approval response cannot be rendered as execution success.
8. Confirm stale/recovery-required precedence.
9. Confirm ordinary transcript still renders persisted user/assistant messages.
10. Confirm branch worktree clean.

No installed runtime deploy or live protected action is authorized by this
implementation unit.
