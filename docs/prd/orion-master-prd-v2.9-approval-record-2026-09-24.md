# Orion Master PRD v2.9 — Approval and Change Record

Date: 2026-09-24

Status: **APPROVED / CURRENT**

Owner: Steven

Supersedes: **Orion Master PRD v2.8**, approved 2026-09-10.

Canonical artifact:

`docs/prd/orion-master-prd-v2.9-ai-optimized-approved.docx`

Final DOCX SHA-256:

`f0e5614d668834959524980a29b410f38bbec67d5dc2b74a76dc5a86ff74f6b5`

## Revision purpose

v2.9 preserves Orion's accepted architecture and makes several previously implicit safety/continuity expectations normative:

1. authoritative runtime/plugin facts are distinct from browser-facing presentation state;
2. HUD payloads use an allowlisted/redacted projection boundary;
3. projected state has explicit transient/activity/completed/reconnect durability semantics;
4. reconnect/hydration comes from supported persisted truth rather than DOM, JavaScript memory, or optimistic browser state;
5. Phase 5 approvals/actions expose a truthful lifecycle from preview through approval, execution, terminal outcome, staleness, and recovery;
6. exact authoritative approval material remains inspectable and is not silently truncated;
7. Phase 4 browser recording gains bounded lifecycle/race/error/ingress-hardening requirements without replacing Hermes STT/TTS;
8. Phase 6 reminders gain crash-safe persistence, corruption handling, duplicate/idempotency, audit, and scheduler-resilience requirements;
9. Persistent Goal Mode is recorded as an explicit opt-in deferred capability with bounded authority and durable state, not a second agent runtime.

## Bounded nanobot donor decision

The exact nanobot source reviewed for v2.9 is pinned at:

`HKUDS/nanobot@1457904e8d6e86088e83498b239fce1b243bec5d`

Nanobot is reference/evidence only. v2.9 does **not** authorize or adopt:

- nanobot as Orion's runtime;
- a second gateway beside Hermes;
- a second memory engine beside iai;
- a second MCP/plugin lifecycle;
- nanobot's STT provider registry or credentials;
- a second scheduler/cron service without a demonstrated Hermes gap and separate architecture decision;
- automatic unapproved cloud fallback;
- autonomous multi-agent operation;
- unrestricted shell/filesystem authority.

Detailed donor evidence is recorded in:

`docs/research/nanobot-bounded-donor-evidence-2026-09-24.md`

## Current execution checkpoint

This PRD revision updates the planning checkpoint to the observed repository/runtime state on 2026-09-24:

- Phase 2 typed HUD and Phase 3 presentation foundation are accepted.
- Phase 4 remains partially open: draft PR #16 and issue #19 retain the final live TTS/Speak Replies OFF/audible barge-in acceptance gate.
- Phase 5 source/runtime safety is accepted through P5-02S production-move readiness.
- P5-02T first production move and P5-02U move-source restore remain separate explicit authorization boundaries.
- P5-03 is the planned truthful action-presentation/projection refinement after the current P5-02 move/restore qualification.
- Phase 6 reminder/scheduling design must start with ownership discovery and the v2.9 durability/corruption requirements.
- Persistent Goal Mode remains deferred until the active Phase 4/5 execution work is closed and a separate implementation decision is made.

## Authorization boundary

Approving/adopting PRD v2.9 is a documentation/product-contract action only.

It does **not** authorize:

- P5-02T or P5-02U;
- any new production edit, move, restore, delete, or recovery cleanup;
- a Hermes/SQLite upgrade or repair;
- a new scheduler;
- a new voice/STT/TTS stack;
- Persistent Goal Mode implementation.

The accepted P5-02S fixture and both existing production recovery records remain protected until a separately explicit owner authorization says otherwise.
