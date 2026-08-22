# Orion Personal AI

Orion is a privacy-first personal AI companion project built around a local-first Hermes Agent runtime, bounded tooling, explicit trust boundaries, and evidence-driven implementation.

## Current status

- Phase 0 — **PASS / CLOSED**
- Phase 1 — **PASS / CLOSED**
- Phase 2 — **NEXT: iai feasibility and memory foundation**

Phase 1 closed after canonical end-to-end acceptance of the COMPANION Discord path and reversible s6 lifecycle.

Accepted Phase 1 lifecycle characteristics:

- Hermes/s6 service-manager path
- `CAP_KILL` added to the otherwise narrow capability set for proven cross-UID gateway termination
- DEFAULT remained continuously supervised and retained the same gateway PID during COMPANION start/stop
- COMPANION completed a stable two-turn Discord conversation with same-session context recall
- COMPANION stopped cleanly with its child absent afterward
- PID 1 remained `s6-svscan`

Accepted canonical launcher SHA-256:

```text
c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b
```

## Repository structure

- `docs/architecture/` — installed-runtime architecture and trust-boundary notes
- `docs/phase1/` — Phase 1 status, evidence, and closure records
- `docs/decisions/` — bounded architecture and implementation decisions
- `scripts/diagnostics/` — reusable diagnostics only after they have passed cleanly

## Security and evidence rules

- No credentials, Discord tokens, `.env` files, vault contents, or private runtime dumps belong in this repository.
- Installed-runtime observations are distinguished from upstream or tagged-repository claims.
- Failed harness revisions are not promoted as canonical diagnostics.
- Project content is informational unless an authorized actor designates it as controlling instruction.

## Current non-blocking follow-ups

- DEFAULT has separately emitted Discord `401 Unauthorized / Improper token` errors during relaunch windows. DEFAULT and COMPANION credentials were proven different, so this is tracked as a DEFAULT-profile cleanup item and does not reopen Phase 1.
- Hermes `v2026.8.19` is an evaluation candidate only. The accepted Orion baseline remains the `v2026.8.18`-based custom image until a separate upgrade evaluation is authorized.

## Next work

Phase 2 should begin with an isolated feasibility evaluation of `iai-personal-memory-engine` using a supported Python 3.11/3.12 environment, with local-only behavior, fail-open memory semantics, and no optional cloud consolidation enabled unless separately authorized.
