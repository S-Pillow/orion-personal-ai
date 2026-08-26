# Phase 2 Closure — iai Memory Foundation

## Status

**CLOSED — August 26, 2026**

Phase 2 is closed for Orion MVP execution. iai 3.0.8 is the accepted canonical memory subsystem for COMPANION. Orion will build around iai rather than reimplementing or independently revalidating its internal memory algorithms.

## Closure basis

Accepted setup-specific evidence includes:

- isolated Python 3.12 iai runtime alongside Hermes
- persistent encrypted store and key across restart/recreation
- real Discord recall after container recreation
- active Hermes ambient capture/recall hooks
- native `memory_contradict` behavior with preserved history and temporal closure
- native fade/forget-hint and rescue behavior
- exact installed recall-wrapper fail-open behavior
- official iai backup and disposable restore
- native iai Brain dashboard at host-local `http://127.0.0.1:4477/`
- native JSONL export of the accepted store
- whole-store administrative erase procedure proven against a disposable official restore
- current profile-store isolation with no alias into COMPANION's `.iai-mcp` store

Primary detailed evidence remains in:

- `docs/phase2/ph2-iai-f6-closure.md`
- `docs/phase2/m5-memory-recall-closure.md`
- `docs/phase2/m6-iai-core-acceptance.md`
- `docs/phase2/iai-feasibility-status.md`

## MVP execution disposition for legacy Phase 2 criteria

The approved Master PRD v1.1.3 contains several Phase 2 criteria written before the final owner direction to treat iai as a proven canonical subsystem and test only Orion/setup integration boundaries. The following disposition records the later execution decision without silently claiming those older criteria were performed.

### Ten or more controlled capture sessions

**Disposition: NOT REQUIRED FOR MVP PHASE CLOSURE.**

Reason: the supported ambient capture path, persistent store, recreation behavior, and real Discord recall path are already proven in the Orion setup. Repeating a fixed session count would primarily revalidate iai behavior rather than an unresolved Orion integration boundary.

### Natural-language "Correct this memory" routing

**Disposition: DEFERRED ORION UX.**

The native iai correction operation is accepted. Earlier natural-language tests did not invoke `memory_contradict`; no iai defect was established. Orion will not add custom memory semantics or SOUL-based substitute correction logic for Phase 2. Convenience routing may be added after the MVP foundation is operating.

### Visible degraded-memory state

**Disposition: DEFERRED TO ORION STATUS/HUD INTEGRATION.**

The exact installed recall wrapper's fail-open contract is proven. A visible degraded-memory indicator requires a user-facing status surface and belongs with later Orion HUD/observability work. It does not block Phase 3 vault retrieval.

### Real end-to-end chat outage smoke

**Disposition: OPTIONAL FOLLOW-UP.**

The exact installed wrapper already returned exit 0 and empty stdout with recall unavailable. A live Discord outage smoke may be performed opportunistically, but it is not required to re-open Phase 2.

### Production backup-policy hardening

**Disposition: CROSS-PHASE HARDENING.**

The native backup/restore path is proven. iai's native archive includes `.crypto.key`; Orion's final production policy must separately satisfy the higher-level requirement for separated recovery material, retention, encrypted off-active-directory copies, visible backup failure, and recovery status. That hardening remains required before final production acceptance but does not block Phase 3 retrieval work.

## Intent preservation

**Intent status: PRESERVED.**

Closing Phase 2 on this basis preserves the reason iai was chosen: Orion uses the proven native memory engine and its semantics, while custom Orion work is built around it. No parallel store, replacement ranking model, custom forgetting lifecycle, or alternate correction model is introduced.

## Phase transition

**Phase 3 — Vault retrieval and draft inbox — is authorized to begin.**

The Phase 3 implementation must preserve the approved vault boundaries: full vault read access is read-only, retrieval is bounded and deterministic, a dedicated Orion inbox is the writable draft surface, and existing-note edits/moves remain approval-gated and recoverable.
