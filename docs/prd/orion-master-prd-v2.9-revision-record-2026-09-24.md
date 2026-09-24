# Orion Master PRD v2.9 — Owner-Directed Revision Record

Date: 2026-09-24

Status: **OWNER-DIRECTED DRAFT / FINAL OWNER APPROVAL PENDING**

## Revision basis

Steven directed a new PRD revision after reviewing bounded donor lessons that
materially strengthen Orion's durable product/authority contract.

The v2.9 candidate is intentionally a new file. Approved v2.8 is preserved
unchanged and remains controlling until Steven explicitly approves the final
v2.9 wording.

## Normative additions

v2.9 adds or strengthens:

- authoritative runtime/plugin facts vs browser presentation state;
- allowlisted/redacted HUD projection;
- explicit presentation durability/reconnect semantics;
- truthful action lifecycle presentation around existing Phase 5 authority;
- rich but bounded Phase 5 approval/diff/evidence UX;
- voice recorder state/race/failure/ingress hardening without replacing Hermes;
- Phase 6 scheduler-owner discovery;
- crash-safe reminder persistence;
- corrupt-store fail-closed recovery;
- dirty-state / duplicate / idempotency expectations;
- per-run reminder evidence and failed-tick resilience;
- deferred explicit Persistent Goal Mode with bounded lifecycle/authority;
- Phase and acceptance-plan updates reflecting the accepted Phase 2/3
  foundation, partially open Phase 4, and active Phase 5 qualification.

## Preserved authority boundaries

No v2.9 addition changes:

- Hermes as runtime/orchestration and approval authority;
- Hermes as preferred native voice/wake authority;
- iai as persistent-memory authority;
- Obsidian as document-vault authority;
- Orion as presentation/control + narrow bounded plugins/glue;
- manual-off as the default lifecycle;
- explicit owner authorization for consequential production mutation;
- local-first and bounded-cloud rules.

## Deliberately not made normative

Donor-specific implementation details remain design evidence, including:

- nanobot class names or event-bus architecture;
- nanobot wire payload names;
- 650 ms minimum recording duration;
- MIME ordering;
- automatic WAV conversion;
- nanobot provider registry/credentials;
- nanobot cron service;
- nanobot goal metadata keys.

## Source evidence

Primary bounded donor source:

```text
HKUDS/nanobot
1457904e8d6e86088e83498b239fce1b243bec5d
```

Companion evidence record:

```text
docs/research/nanobot-bounded-donor-evidence.md
```

## DOCX integrity

Expected repository path:

```text
docs/prd/orion-master-prd-v2.9-ai-optimized-owner-directed-draft.docx
```

Rendered QA: 51 pages, visually inspected after final row-splitting fixes.

Local final SHA-256 at generation:

```text
0c7004156eb86dfb73275e0299d8f8eadc5da8dad2535f2ee39790cea7b8c8bb
```

## Approval rule

This revision record does not self-approve the PRD.

Final approval requires Steven to explicitly accept the v2.9 wording. Until
that point, v2.8 remains the controlling approved Master PRD.
