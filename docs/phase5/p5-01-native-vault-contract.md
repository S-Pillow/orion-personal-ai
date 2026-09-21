# P5-01 Native Vault Contract

Status: P5-01 accepted at the source-only boundary on 2026-09-21. No live plugin install, enablement, or vault mutation is authorized by this acceptance.

## Accepted architecture

Orion Phase 5 uses a native Hermes plugin under the COMPANION profile. Hermes remains the sole local agent/gateway and the generic approval authority. The Orion HUD remains presentation/control only and does not receive provider credentials or direct filesystem mutation authority.

The historical Phase 3 Docker-era vault broker is a behavioral donor, not a Phase 5 runtime.

## P5-01 contract

P5-01 is intentionally non-mutating.

1. A read-only preview operation canonicalizes the requested inbox/vault paths.
2. Containment is checked after normalization and real-path resolution.
3. Absolute paths, parent traversal, symlink/junction/reparse-point escape, non-Markdown targets, invalid UTF-8, and missing required state fail closed.
4. Preview returns the exact operation, target, unified diff, current/proposed hashes as applicable, and an immutable SHA-256 plan token.
5. Preview itself performs no protected filesystem mutation.
6. A later mutation-class Hermes tool must be intercepted by a `pre_tool_call` plugin hook returning `{"action":"approve", ...}`.
7. That approval directive must use Hermes's existing generic human-approval machinery; Orion does not implement a second approval authority.
8. Approval scope must be plan-specific rather than a blanket vault-write grant.
9. After approval, the future mutation handler must re-resolve containment and revalidate all preview-bound hashes/state before any write.
10. Stale, denied, timed-out, unavailable, unresolved, or mismatched approval/state fails closed with no protected side effect.
11. P5-02 or later owns the first real atomic/recoverable vault mutation implementation and live mutation smoke.

## Hermes integration seam

Accepted Hermes v0.20.6 supports native user plugins via `plugin.yaml` plus Python `register(ctx)`.

The plugin `pre_tool_call` hook may return an approval directive:

```json
{
  "action": "approve",
  "message": "human-readable exact operation/target summary",
  "rule_key": "plan-scoped-rule"
}
```

Hermes routes that directive through its existing generic approval gate. API-server runs emit `approval.request`, wait for a human decision, and resume only after the run approval endpoint records the decision.

The existing Orion HUD already consumes `approval.request` and posts the advertised approval choice back through the server-side bridge. P5-01 must reuse that path.

## Donor behavior retained from Phase 3

The accepted Phase 3 broker proved several behaviors that should be preserved natively:

- relative-path-only inputs;
- canonical root containment;
- symlink traversal rejection;
- Markdown-only note bounds;
- UTF-8 enforcement;
- SHA-bound preview plans;
- unified diffs;
- optimistic stale-preview detection;
- recovery snapshots before mutation;
- temp-file plus atomic replacement for edit/restore;
- exclusive target creation and post-write hash verification for draft moves;
- iai-backed destination recommendation instead of a second semantic ranking system.

The Docker execution mechanism itself is not retained.

## Runtime baseline

On 2026-09-21 the COMPANION profile reported no user-installed Hermes plugins:

```text
hermes -p companion plugins list --user --json
[]
```

This establishes a clean pre-P5-01 native-plugin baseline.

The same COMPANION profile currently reports the existing iai MCP server as enabled:

```text
MCP Servers:
iai-mcp    ...    all    enabled
```

This is the preferred Phase 5 destination-recommendation seam. P5-01 must reuse native iai recall/search behavior through the already configured `iai-mcp` authority and must not revive the historical Docker recommender or introduce a second semantic ranker.

## Source verification evidence

Windows source verification on 2026-09-21 passed:

- `test_p5_01.py`: 13/13 tests passed in 0.133 s;
- Hermes `plugins doctor <source-dir> --ci`: runtime discovery, manifest parsing, import, and registration passed;
- doctor reported 4 registered tools and 1 `pre_tool_call` hook with no warnings;
- verification used the source tree only and did not install or enable the plugin.

The tested behaviors include side-effect-free edit and move previews, no creation of missing target directories during preview, absolute/traversal-path rejection, Markdown-only enforcement, symlink/junction/reparse escape rejection, expired/unknown plan blocking, plan-scoped approval rule keys, a known-plan apply placeholder that still refuses mutation, native iai recall-order preservation, ambiguous lossy `doc:` tag rejection, and fail-closed handling of iai errors.

## iai destination-recommendation seam

The historical Phase 3 recommender remains a behavioral donor only. Its accepted semantic rule is retained:

1. use iai's native recall/search result ordering;
2. derive candidate vault directories only from source/provenance paths already associated with recalled vault records;
3. validate each candidate against the current authoritative vault and canonical containment rules;
4. return advisory recommendations with evidence/provenance;
5. do not add Orion-side embeddings, semantic ranking, or a second memory store;
6. do not mutate the draft or vault during recommendation.

The current P5-01 source now implements this as `orion_vault_recommend_destination`:

- the draft text is sent to iai `memory_recall`, which remains the semantic ordering authority;
- `memory_temporal_recall` is used only to recover each recalled record's `doc:` tag through a supported read-only MCP call;
- Orion scans the authoritative vault read-only and computes iai's deterministic `doc:` tag for each contained Markdown file;
- a recalled record is eligible only when its tag maps to exactly one current vault file;
- lossy-tag collisions, missing metadata, reparse-point paths, and non-contained candidates are omitted rather than guessed;
- recommendation order follows `memory_recall`; Orion adds no semantic reranking;
- no direct iai store access is used.

The 13/13 Windows result above applies to commit `835509f`. After PR #21 became ready for review, three preview findings were addressed in source: reject NTFS alternate data stream and invalid Windows component forms, preserve leading whitespace in valid relative filenames, and delimit diff records when either side lacks a final newline. On Windows at `574c2a3`, Hermes doctor passed with 4 tools / 1 hook; the 16-test suite reported 15 passes and one test-fixture failure because Windows CRLF left a trailing CR. The fixture now uses explicit CRLF bytes without a terminal newline and passes with the full 16-test suite in a disposable non-Windows checkout. The corrected suite passed 16/16 on Windows in 0.139 s at `25cb56b`; Hermes doctor passed on the unchanged plugin code at `574c2a3`. Owner/operator review confirmed source-only P5-01 acceptance on 2026-09-21. No live install, MCP grant, restart for activation, or protected filesystem mutation is authorized by these checks.

Hermes plugins have no MCP access by default. A later owner-approved live install would also require the COMPANION plugin entry to grant only `mcp_allowlist: ["iai-mcp"]`. P5-01 does not make that config change.

## P5-01 source scope

Allowed in this ticket:

- source-controlled native plugin skeleton;
- read-only path/containment helpers;
- read-only preview schemas and handlers;
- a fail-closed placeholder mutation tool for approval-contract testing;
- a `pre_tool_call` approval interceptor for the mutation-class tool;
- fixture/unit tests proving preview is side-effect-free;
- tests for traversal and symlink/reparse containment behavior;
- tests proving the mutation-class tool is intercepted for approval while the placeholder handler still refuses mutation;
- documentation of install/rollback procedure without performing the install.

Not allowed in this ticket:

- copying/installing/enabling the plugin in the live COMPANION profile;
- modifying the live Obsidian vault or Orion inbox;
- real move/edit/delete/restore application;
- bypassing Hermes approval;
- adding a second approval authority;
- Docker/WSL runtime dependencies;
- Phase 4 voice/wake changes.

## Acceptance boundary

P5-01 may close only after the source tests pass, Hermes doctor passes, the read-only native iai destination-recommendation seam is implemented/tested, and operator review confirms the source-only contract.

A separate owner-approved P5-02 gate is required before live plugin installation or any protected filesystem mutation. Passing P5-01 does not itself authorize copying the plugin into COMPANION, enabling it, restarting Hermes for it, or applying a move/edit/delete/restore.
