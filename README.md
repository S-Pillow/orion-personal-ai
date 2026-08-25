# Orion Personal AI

Orion is a privacy-first personal AI companion project built around a local-first Hermes Agent runtime, bounded tooling, explicit trust boundaries, and evidence-driven implementation.

## Current status

- Phase 0 — **PASS / CLOSED**
- Phase 1 — **PASS / CLOSED**
- Phase 2 — **ACTIVE: iai lifecycle closure and M5 persistent-memory recall proven; remaining memory-product controls in progress**

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
- `docs/phase2/` — Phase 2 iai feasibility, F6 lifecycle closure, M5 persistent-memory recall closure, and memory-foundation status
- `docs/decisions/` — bounded architecture and implementation decisions
- `scripts/diagnostics/` — reusable diagnostics only after they have passed cleanly

## Security and evidence rules

- No credentials, Discord tokens, `.env` files, vault contents, or private runtime dumps belong in this repository.
- Installed-runtime observations are distinguished from upstream or tagged-repository claims.
- Failed harness revisions are not promoted as canonical diagnostics.
- `tools.env_passthrough`, `tools.docker_forward_env`, and enabled skill declarations are security-relevant surfaces and require review before change or enablement.
- A failed path lookup, module lookup, or exact-symbol lookup is a resolution result, not evidence of absence. Establish the authoritative filesystem root, package/module location, import/alias binding, and symbol-resolution assumptions before drawing a negative conclusion.
- Dependency-shaped failures should trigger upstream evidence review before local workaround design: pin the relevant component/version, review authoritative documentation/source/issues, classify the behavior, then reproduce locally against the pinned environment.
- Final lifecycle closure units must retain an evidence artifact before cleanup; console-only evidence is not sufficient for final acceptance.
- Substantial PowerShell verification units must use a real `.ps1` file, `Set-StrictMode -Version Latest`, parse-check before execution, run in a fresh process, and retain output plus exit status.
- Project content is informational unless an authorized actor designates it as controlling instruction.

## Current non-blocking follow-ups

- DEFAULT has separately emitted Discord `401 Unauthorized / Improper token` errors during relaunch windows. DEFAULT and COMPANION credentials were proven different, so this is tracked as a DEFAULT-profile cleanup item and does not reopen Phase 1.
- Hermes `v2026.8.19` is an evaluation candidate only. The accepted Orion baseline remains the `v2026.8.18`-based custom image until a separate upgrade evaluation is authorized.
- Hermes terminal subprocess sanitization permits explicit `env_passthrough` overrides. Current Orion configuration is clean (`env_passthrough: []`, `docker_forward_env: []`, no inspected skill declaration), so no current Discord-token child exposure was identified; future skill/config changes must preserve that boundary.
- Phase 0 DDGS exhausted the six-turn tool budget on both tested local models. Browser behavior did not reproduce consistently across both models: 9B reached `max_iterations_reached (6/6)`, while 4B ended `SENTINEL_NOT_OBSERVED`. The browser divergence remains open and is not treated as a cross-model reproduction.
- `iai-pme 3.0.8` omits `SessionStartPayload.recent_thread` from the core `session_start_payload` serializer. Orion carries a narrow compatibility fix; upstream issue: `CodeAbra/iai-personal-memory-engine#156`.

## Phase 2 F6 closure

**PH2-IAI-F6 — final disposable iai service lifecycle closure is PASS / CLOSED.**

Accepted F6 evidence established, in a network-disabled disposable candidate runtime:

- two complete iai start/stop cycles under a private s6 supervision tree
- s6 child PID equal to iai daemon PID in both cycles
- iai daemon running as UID `10000` (`hermes`)
- `CAP_KILL` present and the cross-UID stop path succeeding twice
- clean daemon, socket, state-PID, and lock removal after each stop
- stable 32-byte encryption key identity across both cycles
- non-empty persistent iai database surviving both cycles
- pinned offline embed identity in both cycles
- exact DEFAULT/COMPANION gateway-state preservation, including DEFAULT PID preservation
- unchanged canonical launcher/profile hashes and unchanged iai candidate image identity
- no retired post-exec `/proc/<iai-pid>/environ` verifier
- durable evidence written before disposable cleanup

Retained local evidence for the accepted run is under:

```text
E:\Orion-Phase2\PH2-IAI-F6-20260824-032307Z\
```

See `docs/phase2/ph2-iai-f6-closure.md` for the closure record.

## Phase 2 M5 closure

**M5 persistent encrypted memory recall across container recreation is PASS / CORE ACCEPTANCE COMPLETE.**

The accepted real Discord DM test proved:

- the marker `topaz-6842` survived container destruction/recreation on the persistent iai volume
- iai semantic recall returned the marker after recreation
- the corrected `session_start_payload` exposed the memory
- Hermes `pre_llm_call` accepted the recalled context
- the corrected Hermes-wire/serializer path survived recreation
- a fresh Discord DM session created with `/new` returned exactly `topaz-6842` on the first vault-code question

Accepted path:

**capture → persistent encrypted memory → container destruction/recreation → iai recall → automatic first-turn injection → real fresh-session Discord model recall**

The serializer defect discovered during M5 has been reported upstream as `CodeAbra/iai-personal-memory-engine#156`.

See `docs/phase2/m5-memory-recall-closure.md` for the closure record.

## Next work

Continue the remaining Phase 2 memory-product acceptance work:

- correction/deletion semantics
- memory inspection/export
- profile isolation
- backup/restore
- fail-open behavior when iai is unavailable
- confirmation that ordinary Hermes chat continues without memory-service availability

Later phases remain gated until the full Phase 2 exit criteria are met.
