# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion for **native Windows 11**. The accepted foundation uses a pinned Hermes Agent runtime, the named `companion` profile, a local Ollama model, Discord, a loopback Hermes API, native iai persistent memory, and an Orion-owned local HUD/presentation layer.

## Controlling baseline

The controlling product requirements document is **ORION — Master PRD v2.9**, approved 2026-09-24.

Canonical artifact and approval record:

- `docs/prd/orion-master-prd-v2.9-ai-optimized-approved.docx`
- `docs/prd/orion-master-prd-v2.9-approval-record-2026-09-24.md`

PRD v2.9 supersedes v2.8. It preserves the accepted native-Windows/manual-off authority model while adding explicit contracts for truthful runtime-to-HUD projection, reconnect durability, richer Phase 5 action/evidence presentation, bounded voice-recorder hardening, durable reminder recovery semantics, and deferred Persistent Goal Mode boundaries.

The accepted **manual-off** lifecycle model remains unchanged:

- Orion/Hermes do not start automatically at Windows login.
- Start Orion / Stop Orion are explicit operator actions.
- Hermes and iai Scheduled Tasks remain registered for vendor-supported behavior, but their LogonTriggers are disabled.
- Ollama login startup is disabled.
- iai remains its own lifecycle and persistent-memory authority.
- Orion must not add a parallel gateway, memory system, embedding/ranking stack, voice runtime, hotword service, or lifecycle supervisor without a separately approved demonstrated gap.

Historical Docker/s6/JARVIS implementation records remain useful provenance but are not the controlling native-Windows path.

## Current status

### Active Hermes v0.22.5 controlled migration — PRE-INSTALL QUALIFICATION

PR #81 is the active controlled-migration path from the accepted production Hermes `0.20.6` / `v2026.8.27` / `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` baseline toward exact upstream Hermes `v0.22.5` at `bf0203a794a07aac3ff764972ab9087baa4e4f4e`.

Production has **not** been upgraded or cut over. The accepted `companion` runtime, iai ownership, model/provider configuration, and manual-off lifecycle remain authoritative.

Qualification completed so far:

- exact v0.22.5 source candidate + retained P4-04A/P6-03/P6-04A compatibility delta — **PASS**;
- isolated standalone gateway contract v6 — **PASS WITH WINDOWS BIND-ENUMERATION LIMITATION**;
- bounded startup timing diagnostic — **PASS**, HTTP-ready in **8.285 s**;
- isolated session/profile resource contract v3 — **PASS**, HTTP-ready in **7.745 s**, Bearer auth + session create/get/patch/list/delete + scratch SQLite persistence/profile isolation proven with zero model/memory/STT/TTS provider calls.

Current gate:

- isolated P6-03 exact pre-repair `jobs.json` preservation + P6-04A durable `error_class` runtime contract — **UNRESOLVED AFTER HARNESS TIMEOUT**. The first monolithic 90-second child did not expose enough phase evidence to classify a candidate failure. Observer-hardened v2 tooling separates P6-03/P6-04A, emits flushed phase markers, and always runs production/candidate postconditions.

Canonical live status and resume point:

- `docs/hermes/hermes-v0225-qualification-status.md`
- `docs/hermes/hermes-v0225-controlled-migration.md`

PR #81 remains draft, pre-install, and fail-closed. No blind `hermes update`, production cutover, profile reset, iai change, provider/model change, live model/STT/TTS qualification, second Hermes dashboard/web process, or PR merge is authorized by the completed sub-gates.

## Resume point

- **Active engineering resume point: PR #81 Hermes v0.22.5 pre-install qualification.** Canonical status: `docs/hermes/hermes-v0225-qualification-status.md`.
- Completed on the exact v0.22.5 candidate: source qualification; isolated gateway v6; startup diagnostic (8.285 s); session/profile v3 (7.745 s, authenticated session CRUD + durable scratch persistence/profile isolation).
- Current unresolved gate: P6-03/P6-04A isolated runtime contract. v1 timed out without phase localization; rerun only with `scripts/hermes_upgrade/v0225_isolated_cron_compat_contract_smoke_v2.py` and reconcile its phase evidence.
- Production Hermes remains the accepted `0.20.6` / `v2026.8.27` / `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` baseline; PR #81 does not authorize cutover.

Current shorthand: **production remains on accepted Hermes v0.20.6; PR #81 is actively qualifying exact v0.22.5 pre-install. Gateway/startup/session-resource isolation sub-gates have passed; the P6-03/P6-04A runtime contract is unresolved pending observer-hardened v2 evidence.**
