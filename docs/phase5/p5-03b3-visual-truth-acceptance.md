# P5-03B3 — Visual + Truth Acceptance

Status: **IMPLEMENTED / EXACT-HEAD ACCEPTANCE IN PROGRESS**

Current candidate head:
`e0c62716332eaaf8c09f73e3fff9f3a9d3e8cd75`

Dependencies:

- P5-03A2 authoritative browser-safe projection;
- P5-03B1 accepted Action / Diff / Evidence UX specification;
- P5-03B2 accepted HUD implementation;
- current UI visual-convergence branch, which must not weaken the accepted
  authority/truth boundaries.

## Objective

P5-03B3 is the acceptance unit for the Phase 5B action/evidence experience.

It verifies both:

1. **visual semantics** — states remain visibly distinct and the HUD does not
   imply that approval equals execution success; and
2. **truth semantics** — consequential claims continue to come only from the
   accepted Hermes/plugin/system evidence projection.

The browser remains presentation-only. This ticket does not create a second
approval authority, action ledger, recovery authority, mutation executor, or
browser-owned consequential state.

## Accepted design contract under test

The Phase 5B action/evidence surface retains these requirements:

- cinematic dark HUD treatment;
- contextual right-side action/evidence region;
- approval decision controls visually prioritized when pending;
- exact approval/diff content preserved as literal text;
- recent evidence remains informational only;
- technical evidence remains collapsed/expandable and allowlisted;
- amber is reserved for attention/approval/stale/refusal treatment rather than
  protected-success claims;
- approval acknowledgement remains visibly distinct from execution evidence;
- authoritative success, failure, refusal, stale-plan, recovery-required,
  unavailable, and unknown states remain distinct.

## Adversarial truth matrix

The acceptance suite explicitly covers:

| Scenario | Required result |
| --- | --- |
| approval requested | decision-required presentation only |
| approval accepted | execution remains **UNPROVEN** |
| approval denied | no protected success claim |
| authoritative success | success only from complete action-specific result |
| authoritative failure | failed presentation; recovery-required preserved |
| refusal | not performed, not success |
| stale plan | not performed, not success |
| partial success-shaped payload | must not upgrade to success |
| generic `tool.completed` before authoritative plugin failure | generic lifecycle does not override failure |
| reordered tool/result mapping | canonical tool identity still required and result truth preserved |
| foreign-run terminal evidence | filtered out of selected terminal run |
| secret/private fields | excluded from browser projection and technical presentation |
| recovery ID without current inspector | current availability is not invented |
| approval accepted with no execution result | remains execution-unproven |

## Automated acceptance surfaces

### Projection truth tests

`hud/tests/test_p5_03b3_truth_acceptance.py`

This dedicated acceptance file verifies:

- decision-only approval acknowledgement;
- approval denial without execution claim;
- success/refusal/stale/failure/recovery-required matrix;
- partial success-shaped payload rejection;
- reordered tool-call/result mapping;
- generic `tool.completed` versus authoritative plugin failure;
- secret exclusion across approval/action/run-status projections;
- foreign-run/reordered terminal evidence filtering.

Existing P5-03A/P5-03B projection tests remain in force and continue to cover
exact IDs, session binding, malformed evidence, recovery precedence, hydration,
and raw consequential-field exclusion.

### Visual semantic tests

`hud/tests/test_action_workspace_semantics.cjs`

The presentation matrix verifies that:

- approval-requested and approval-accepted use attention treatment;
- approval-accepted renders `UNPROVEN`, never `SUCCEEDED`;
- stale/refused remain attention/not-performed states;
- success and failure remain separate terminal treatments;
- unavailable/unknown remain neutral explicit states;
- recovery labels never invent current availability;
- technical evidence excludes arbitrary fields.

### Browser-rendered truth matrix

The isolated visual fixture exposes:

`?fixture=truth-matrix`

through `hud/tests/probe_ui_convergence.py`.

`hud/tests/capture_ui_visuals.py` renders and captures each state at
1440×900 using the production action-workspace renderer:

- preview_ready;
- approval_requested;
- approval_accepted;
- approval_denied;
- succeeded;
- stale_plan;
- refused;
- failed;
- unavailable;
- unknown.

The fixture is presentation-only and does not mutate the vault, resolve a real
approval, create runtime authority, or establish live production evidence.

## Exact approval and evidence requirements retained

P5-03B3 continues to rely on the already accepted B1/B2 controls:

- exact approval detail remains complete and literal;
- canonical `once|session|always|deny` choices remain explicit;
- approval decision and execution result remain separate states;
- exact diff uses text rendering rather than Markdown/HTML interpretation;
- recent evidence cannot initiate an action;
- technical fields are allowlisted;
- no provider secrets, raw arbitrary args, stack traces, recovery directory
  paths, or protected file bytes are exposed.

## Scope boundary

This acceptance unit does **not** close P5-03C reconnect/hydration
qualification. Reconnect remains the separately planned next Phase 5 truth
qualification after visual convergence is accepted.

It also does not add unsupported Research/Create, project, artifact,
attachment, voice, or richer Memory Lens functionality.

## Completion gate

P5-03B3 may be marked **ACCEPTED** only when the exact candidate head passes:

1. full HUD Python test discovery;
2. Node approval/summon/action-workspace/Core renderer suites;
3. Playwright desktop/mobile visual capture;
4. the dedicated P5-03B3 truth matrix;
5. the browser-rendered truth-state matrix;
6. zero secret/private evidence leakage in covered projections;
7. branch relation and mergeability recheck.

Passing tests establish the stated bounded semantics and rendered-state
contracts. They do not by themselves constitute owner acceptance of the broader
PR #51 visual design.
