# Orion Personal AI

Orion is a privacy-first personal AI companion project built around a local-first Hermes Agent runtime, bounded tooling, explicit trust boundaries, and evidence-driven implementation.

## Current status

Phase 0 is closed and accepted. Phase 1 is active and focused on completing the COMPANION gateway lifecycle and stable Discord conversation path.

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
