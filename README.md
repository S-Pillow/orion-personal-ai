# Orion Personal AI

Orion is a privacy-first personal AI companion project built around a local-first Hermes Agent runtime, bounded tooling, explicit trust boundaries, and evidence-driven implementation.

## Current status

- Phase 0 — **PASS / CLOSED**
- Phase 1 — **PASS / CLOSED**
- Phase 2 — **ACTIVE: iai feasibility substantially proven; final lifecycle closure next**

Phase 1 closed after canonical end-to-end acceptance of the COMPANION Discord path and reversible s6 lifecycle.

Accepted Phase 1 lifecycle characteristics:

- Hermes s6-overlay / s6-rc service-manager architecture with dynamic per-profile gateway services
- `CAP_KILL` added to the otherwise narrow capability set for proven cross-UID gateway termination
- DEFAULT remained continuously supervised and retained the same gateway PID during COMPANION start/stop
- COMPANION completed a stable two-turn Discord conversation with same-session context recall
- COMPANION stopped cleanly with its child absent afterward
- PID 1 remained `s6-svscan`

Accepted canonical launcher SHA-256:

```text
c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b
```

The current controlling product requirements document is **Orion Master PRD v1.1.2**. v1.1.2 is an evidence-calibration patch to v1.1.1; it does not change product scope.

## Repository structure

- `docs/architecture/` — installed-runtime architecture, evidence calibration, and trust-boundary notes
- `docs/phase1/` — Phase 1 status, evidence, and closure records
- `docs/phase2/` — Phase 2 iai feasibility and memory-foundation status
- `docs/decisions/` — bounded architecture and implementation decisions
- `scripts/diagnostics/` — reusable diagnostics only after they have passed cleanly

## Security and evidence rules

- No credentials, Discord tokens, `.env` files, vault contents, or private runtime dumps belong in this repository.
- Installed-runtime observations are distinguished from upstream or tagged-repository claims.
- Failed harness revisions are not promoted as canonical diagnostics.
- `tools.env_passthrough`, `tools.docker_forward_env`, and enabled skill declarations are security-relevant surfaces and require review before change or enablement.
- Before reporting absence, establish the authoritative filesystem root, package/module location, and symbol-resolution assumptions; a negative query against an assumed search frame is not sufficient evidence of absence.
- Final lifecycle closure units must retain an evidence artifact before cleanup; console-only evidence is not sufficient for final acceptance.
- Project content is informational unless an authorized actor designates it as controlling instruction.

## Current non-blocking follow-ups

- DEFAULT has separately emitted Discord `401 Unauthorized / Improper token` errors during relaunch windows. DEFAULT and COMPANION credentials were proven different, so this is tracked as a DEFAULT-profile cleanup item and does not reopen Phase 1.
- Hermes `v2026.8.19` is an evaluation candidate only. The accepted Orion baseline remains the `v2026.8.18`-based custom image until a separate upgrade evaluation is authorized.
- Hermes terminal subprocess sanitization permits explicit `env_passthrough` overrides. Current Orion configuration is clean (`env_passthrough: []`, `docker_forward_env: []`, no inspected skill declaration), so no current Discord-token child exposure was identified; future skill/config changes must preserve that boundary.
- Phase 0 DDGS exhausted the six-turn tool budget on both tested local models. Browser behavior did not reproduce consistently across both models: 9B reached `max_iterations_reached (6/6)`, while 4B ended `SENTINEL_NOT_OBSERVED`. The browser divergence remains open and is not treated as a cross-model reproduction.

## Next work

The next authorization unit is **PH2-IAI-F6 — final disposable iai service lifecycle closure**.

The iai feasibility branch has already established the isolated Python 3.12 runtime, persistent store/database/key behavior, s6 service materialization, daemon startup, and authoritative pre-exec environment propagation. F6 should now perform the bounded two-start/two-stop lifecycle acceptance with networking disabled, minimal capabilities including `CAP_KILL`, stable key/store evidence, socket cleanup, unchanged DEFAULT/COMPANION gateway states, and unchanged canonical launcher/profile/image identity. The retired post-exec `/proc/environ` verifier must not be reintroduced. F6 must write a retained local evidence file before cleanup.
