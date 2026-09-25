# Orion Master PRD v2.9 Approval Record

Date: 2026-09-24

Status: APPROVED / CURRENT

Supersedes: Orion Master PRD v2.8

Approved artifact: `orion-master-prd-v2.9-ai-optimized-approved.docx`

Artifact SHA-256: `72e8b3916a1a3229a081fb13422b9c65ac10f2b8f847ffebb77819eed4178ce0`

Artifact size: `71183` bytes

## Approval basis

Steven approved Orion Master PRD v2.9 on 2026-09-24 after full content and rendered-DOCX review. Sections 0 through 22 are the current normative execution specification. Sections 23 and 24 contain authoritative references and the approval record. v2.9 supersedes v2.8; prior approved PRDs remain retained for provenance and comparison.

Approval of the PRD does **not** itself authorize runtime, code, configuration, deployment, or production mutation. Every separately gated action retains its existing authorization boundary. In particular, P5-02T first production move and P5-02U move-source restore remain separately authorization-gated.

## v2.9 normative additions

v2.9 preserves the accepted Orion authority model and adds explicit requirements for:

- authoritative runtime/system facts versus browser presentation projection;
- allowlisted/redacted browser-facing event and action payloads;
- explicit presentation durability and reconnect hydration from persisted truth;
- richer Phase 5 approval/action lifecycle and expandable technical evidence;
- separation between approval acknowledgement and verified execution success;
- bounded Phase 4 recorder/transcription ordering and failure hardening;
- Phase 6 reminder persistence, corrupt-store preservation, replay/idempotency, audit, and scheduler resilience;
- deferred Persistent Goal Mode with explicit activation, bounded objective state, lifecycle, persistence, work allowance, and no authority expansion.

## Controlling architecture retained

- Hermes Agent remains runtime/orchestration and preferred native voice/wake authority.
- iai-pme remains persistent-memory authority.
- Obsidian remains the durable human-authored document vault.
- Orion remains the presentation/control and narrow integration layer.
- Native Windows and manual-off remain the accepted operating foundation.
- Browser-visible state describes observed authority; it never grants authority.
- No second general event bus, scheduler, gateway, memory engine, approval engine, or speech stack is introduced without a demonstrated gap and separate approval.

## Donor/reference boundary

HKUDS/nanobot is recorded as pinned donor/reference evidence at commit `1457904e8d6e86088e83498b239fce1b243bec5d`. Orion adopts bounded architectural lessons only. Nanobot is not an Orion runtime dependency or authority, and code reuse requires separate explicit authorization in the applicable implementation ticket.

See `docs/research/nanobot-bounded-donor-evidence.md`.

## Repository preservation

The approved v2.9 DOCX is stored as a new version under `docs/prd/`. The v2.8 DOCX and approval record remain retained. The SHA-256 above is the artifact identity for future verification; do not silently rewrite the approved binary. A future material PRD revision requires a new version, explicit owner approval, a new approval record, and a new artifact hash.
