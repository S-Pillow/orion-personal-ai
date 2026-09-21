# P5-01 Native Vault Contract

Status: source-only discovery/contract slice. No live plugin install, enablement, or vault mutation is authorized by this ticket.

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

P5-01 may close only after source tests pass and operator review confirms the source-only contract. A separate owner-approved P5-02 gate is required before live plugin installation or any protected filesystem mutation.
