# Phase 2A Live Acceptance and Merge Closure — 2026-09-10

Status: **PASS / ACCEPTED / MERGED**

Scope: the repository's internal **Phase 2A compatibility + typed-control HUD bridge slice**. This record does **not** declare the entire PRD v2.8 Phase 2 acceptance plan closed.

## Controlling references

- ORION Master PRD v2.8, approved 2026-09-10
- accepted Hermes baseline: `v2026.8.27` / package `0.20.6`
- accepted iai baseline: `iai-pme==3.0.8`
- accepted operator publication: `2.7.4-candidate1`
- feature branch: `feature/orion-phase2a-hud-bridge`
- accepted feature head: `faec8769a34e049cd48408be2445198f7647765b`
- PR: #9, `Phase 2A: add Orion loopback HUD bridge`
- merge commit on `main`: `55a229ef77972491eff8765727ddbe26f2920b95`

## Synthetic and source gates

The final HUD suite passed **25/25** tests after the persisted-session startup fix. Coverage includes the loopback/auth bridge boundary, same-origin mutation checks, allowlisted session/run/approval routes, server-side credential handling, rejected-POST connection close behavior, progressive SSE delivery for chunked/Content-Length/close-delimited responses, explicit degraded-state presentation, suppression of empty persisted/streaming assistant cards, and one-time persisted-session history load on startup.

No dependency upgrade, configuration mutation, model call, iai mutation, or live runtime start was needed for the final synthetic gate.

## Controlled live acceptance evidence

The following evidence was accepted on the real Windows environment using the existing Start Orion / Stop Orion lifecycle only:

- HUD listener bound to loopback on `127.0.0.1:8765`; the HUD did not create a second lifecycle or speech authority.
- Real typed interaction used the persistent COMPANION Hermes conversation/session.
- Session continuity marker `ORION-2A-CONTINUITY-7319` survived HUD stop/restart and was returned from the same persisted conversation.
- Progressive assistant streaming was visibly incremental rather than completion-buffered.
- STOP functioned during a live streamed turn.
- Browser exposure audit passed: the Hermes API credential did not appear in served HTML/JS or inspected browser-visible response bodies.
- DEFAULT-vs-COMPANION separation passed with distinct credentials: COMPANION authenticated to the COMPANION API while a temporary DEFAULT credential was rejected; the original DEFAULT `.env` was restored byte-for-byte and COMPANION `.env` remained unchanged.
- COMPANION iai MCP routing through Hermes was verified against the profile-scoped installed surface.
- One explicitly authorized read-only `memory_recall` call was exercised through the typed HUD/Hermes path. The HUD Agent Activity surface showed `mcp__iai_mcp__memory_recall` with terminal state `COMPLETED`. No memory create/update/delete/fade/rescue/contradict action was authorized or performed.
- Natural Hermes detailed readiness was degraded, and the HUD truthfully rendered both `HERMES DEGRADED` and Core `DEGRADED` rather than claiming ready/online-only state.
- Persisted transcript rendering no longer produced blank ORION assistant cards around tool-only/empty records.
- After the final startup fix, `orion-hud-main` was selected on restart and its existing transcript populated automatically without toggling the session dropdown.
- Every live smoke returned to accepted manual-off state with relevant listeners `0`, Ollama processes `0`, `launcher-session.json` absent, and `active-operation.json` absent.

## Acceptance interpretation

The internal Phase 2A typed-control bridge slice is accepted and merged. The accepted implementation preserves the intended authority split: Hermes remains conversation/orchestration, iai remains persistent memory, and Orion remains a presentation/control client with a narrow loopback adapter.

This is **not** evidence that all PRD v2.8 §16.3 Typed HUD acceptance bullets are complete. In particular, the following remain outside this Phase 2A slice and must not be silently marked closed:

- explicit visible summoned-content/display path on the HUD;
- deterministic Orion Core gaze/state behavior tied to active UI/system state;
- Memory Lens handoff to the installed iai-native IAI Brain surface with installed-version-supported health/provenance context;
- any broader Phase 2/3 presentation work not exercised by the accepted typed-control proof.

## Roadmap reconciliation

The repository previously used internal planning labels `Phase 2A` through `Phase 2F`. Those labels are useful as historical subdivisions of the HUD work, but they are not peer replacements for the controlling PRD v2.8 phase table.

Future work should use the PRD v2.8 phase names as the controlling roadmap. The next development target is **PRD Phase 3 — Orion Core + adaptive workspace + memory transparency**: Core state/gaze behavior, adaptive center workspace, Memory Lens, native IAI Brain handoff, truthful local/cloud/source/authority indicators, and the summonable-panel shell. Start that work with a bounded read-only design/source inventory before new presentation code.

PRD Phase 4 voice/wake remains later and must reuse Hermes-native voice/wake unless a demonstrated gap is separately approved. Phase 5 vault actions/approvals/display-tool mutation, Phase 6 cloud/reminders, and Phase 7 device routing/LAN/mobile/proactivity/hardening remain later gates.

Core Intent Preservation: **PRESERVED**.
