# Phase 4 — JARVIS Orchestration and User Experience

**Status: ACTIVE — started August 27, 2026**

Phase 3 is closed for MVP. Phase 4 turns the accepted Orion subsystems into a coherent user-facing control layer without changing their underlying responsibilities.

## Governing architecture

- Hermes remains the local agent runtime.
- iai remains the authoritative memory and semantic-recall engine.
- The native iai Brain remains the authoritative detailed memory-management UI.
- Obsidian remains the authoritative human-facing document vault.
- Orion exact-source, inbox, destination-recommendation, approval, and recovery components remain the accepted document orchestration primitives.
- The JARVIS layer orchestrates these components; it must not reimplement iai memory semantics, create a second semantic index, or bypass approval boundaries.

## Phase 4 MVP objective

Provide one local Orion/JARVIS surface where the user can understand system state and naturally perform the workflows already accepted in Phases 2 and 3.

Target user flow:

`JARVIS control center -> inspect status -> talk/work with Orion -> open native Brain when needed -> create inbox draft -> receive destination recommendation -> review exact diff -> approve/deny -> apply through controlled broker -> recover/restore if needed`

## Execution sequence

### P4-01 — JARVIS control-center shell

**Status: IN PROGRESS**

Create a local read-only dashboard shell that:

- presents Orion runtime health as one coherent system;
- exposes Memory / Brain as a direct link to the native iai dashboard at `http://127.0.0.1:4477/`;
- shows the authoritative vault, Orion inbox, approvals, and recovery as distinct trust surfaces;
- reports current local runtime/container state plus bounded counts only;
- performs no vault, inbox, or memory write actions;
- establishes the visual language for the future Orion/JARVIS interface.

P4-01 acceptance requires successful local generation plus operator visual confirmation that the dashboard is useful, readable, and that the native iai Brain link opens correctly.

### P4-02 — Local orchestration bridge

Wire the accepted operational components behind a localhost-only action layer so the UI can invoke them without manual PowerShell entry. Initial scope: create inbox draft and request vault destination recommendations.

### P4-03 — Approval workflow UX

Surface P3-05 preview/apply semantics in the JARVIS interface: exact target, exact diff, explicit approve/deny, stale-preview protection, and clear result state.

### P4-04 — Recovery UX

Expose recovery evidence and approved restore through the same preview/approval model. No silent rollback or destructive action.

### P4-05 — Companion interaction surface

Bring the accepted Hermes/COMPANION interaction path into the JARVIS experience while preserving the current Hermes execution model and iai automatic memory integration.

### P4-06 — MVP orchestration acceptance

Run one bounded end-to-end user flow through the JARVIS layer and close Phase 4 for MVP if it demonstrates the accepted subsystems working together without bypasses or duplicate semantics.

## Design intent

The JARVIS layer should feel like a deliberate personal command environment rather than a generic admin dashboard. Visual design may be expressive and contemporary, but status, authority, approval, and recovery boundaries must remain immediately understandable.

The UI should make the architecture easier to use, not hide or weaken it.

**Intent status: PRESERVED.**