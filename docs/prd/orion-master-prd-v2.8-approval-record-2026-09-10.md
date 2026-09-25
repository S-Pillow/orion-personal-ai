# Orion Master PRD v2.8 Approval Record

Date: 2026-09-10

Status: APPROVED / SUPERSEDED BY v2.9

Supersedes: Orion Master PRD v2.7

Approved artifact: `orion-master-prd-v2.8-ai-optimized-approved.docx`

Artifact SHA-256: `6b24d4d85bb1142c9284c8bd9ac202ec7cdb0f641a5b093eec6880426e107c6f`

Artifact size: `60062` bytes

## Approval basis

Steven approved Orion Master PRD v2.8 on 2026-09-10. It was the controlling normative execution specification until Steven approved Orion Master PRD v2.9 on 2026-09-24. v2.9 now supersedes v2.8; this record and artifact are retained unchanged as provenance for the prior approved baseline.

## Controlling architecture

- Hermes Agent is the runtime/orchestration and preferred native voice/wake authority.
- iai-pme is the persistent-memory authority.
- Obsidian is the durable human-authored document vault.
- Orion is the visual presentation and authorized control layer.
- Native Windows and manual-off remain the accepted operating foundation.
- The browser never receives the Hermes API key or direct filesystem mutation authority.
- Mutating vault actions require side-effect-free preview, exact target/operation evidence, Hermes generic approval, stale-state revalidation, atomic execution, and recovery information.

## Phase 5 requirements relevant to current work

- canonical containment for every vault/inbox path;
- iai-owned semantic ranking for destination recommendation;
- exact approval action, target, and relevant diff/payload;
- no protected side effect for unresolved, denied, expired, timed-out, or stale approval;
- exact, atomic, and recoverable approved execution;
- presentation and authority indicators remain descriptive rather than authorizing.

## Repository preservation

The approved DOCX is stored unchanged in `docs/prd/`. Its SHA-256 is the artifact identity for future verification. Do not silently rewrite the approved binary. A future PRD revision requires a new version, approval record, and artifact hash.
