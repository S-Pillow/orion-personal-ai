# Phase 4 — Orion Orchestration and User Experience

**Status: ACTIVE — started August 27, 2026**

Phase 3 is closed for MVP. Phase 4 turns the accepted Orion subsystems into a coherent user-facing control layer without changing their underlying responsibilities.

## Governing architecture

- Hermes remains the local agent runtime.
- iai remains the authoritative memory and semantic-recall engine.
- The native iai Brain remains the authoritative detailed memory-management UI.
- Obsidian remains the authoritative human-facing document vault.
- Orion exact-source, inbox, destination-recommendation, approval, and recovery components remain the accepted document orchestration primitives.
- `eadmin2/jarvis_ai` is the upstream HUD / voice / orchestration application baseline.
- `S-Pillow/jarvis_ai` is the maintained Orion application fork.
- `CodeAbra/iai-personal-memory-engine` remains the behavioral authority for iai.
- `S-Pillow/iai-personal-memory-engine` is maintained as a compatibility/upstream-tracking fork, not as a divergent Orion memory design.
- The Orion layer may adapt and extend the HUD application but must not reimplement iai memory semantics, create a second semantic index, or bypass accepted approval boundaries.

## Repository strategy

`S-Pillow/orion-personal-ai` remains the canonical Orion integration/control repository for project state, architecture decisions, acceptance evidence, integration scripts, deterministic rebuild instructions, and cross-component glue.

The actual Orion HUD/voice application source lives in `S-Pillow/jarvis_ai`, with `eadmin2/jarvis_ai` retained as its upstream source.

The iai fork exists for reproducibility, upstream contribution work, and narrowly scoped compatibility patches when necessary. Upstream iai behavior remains controlling for MVP. The presence of the fork does not change the decision to use iai as written.

Hermes remains upstream-only unless sustained source-level divergence later justifies a fork.

Accepted implementation code must be preserved in GitHub. Documentation-only closure is not sufficient when code/configuration created the accepted runtime state. The project-wide rebuild policy is recorded in `docs/decisions/source-reproducibility-and-rebuild.md`.

## Upstream application baseline

Approved HUD upstream:

- repository: `https://github.com/eadmin2/jarvis_ai`
- pinned baseline commit: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- license: MIT; upstream copyright and license notice retained
- Orion fork: `https://github.com/S-Pillow/jarvis_ai`
- Orion branch: `orion-mvp`

Why this baseline is being adopted:

- it is already designed around Hermes Agent;
- it provides a browser HUD, typed chat, voice transport, live tool activity, STOP/barge-in behavior, approval cards, media panels, usage/machine views, and a Hermes plugin surface;
- its server already uses Hermes' Sessions API for persistent conversation and run/approval events;
- reusing the application preserves development effort for Orion-specific integration instead of recreating the same shell.

The upstream application was primarily tested on macOS/Apple Silicon. Orion's runtime is Windows + Docker, so launchd-specific deployment, host paths, TLS setup, service management, and networking must be adapted rather than copied blindly.

## Phase 4 MVP objective

Provide one local Orion surface where the user can talk/work with the companion, see agent activity and approvals, reach the native iai Brain, create and manage drafts, and invoke the already-accepted Orion vault workflow naturally.

Target user flow:

`Orion HUD -> talk/type to Hermes companion -> iai memory works automatically -> inspect native Brain when needed -> create inbox draft -> iai-backed destination recommendation -> exact diff -> approve/deny -> controlled broker apply -> recovery/restore when needed`

## Execution sequence

### P4-01 Revised — Fork-first upstream JARVIS adoption

**Status: PASS / CLOSED — August 27, 2026**

Accepted implementation:

- fork `S-Pillow/jarvis_ai` exists and is the local `origin`;
- `eadmin2/jarvis_ai` is retained as `upstream`;
- exact upstream baseline pinned to `88998de8369e9d36f6d434b5e01feb93fcf1c33f`;
- upstream MIT license/attribution preserved;
- local/remote Orion branch is `orion-mvp`;
- accepted remote branch head is `aeb0643f8119a4d4f8b78a950194e9778eea4af2`;
- bounded branch delta contains only:
  - `ORION-UPSTREAM.md`
  - `server/config/server.orion.example.yaml`
  - `server/hud/index.html`
- visible JARVIS product branding was changed to Orion;
- Orion conversation/scope labels were changed to `orion-main` / `orion:user:main`;
- no `server/server.py` change occurred;
- iai, vault services, runtime secrets, and existing production containers were not modified.

Canonical accepted bootstrap script is stored in `scripts/phase4/p4-01-adopt-jarvis-fork.ps1`.

This closes the earlier custom standalone dashboard-shell direction. That mockup is not the Orion product baseline.

### P4-02 — Orion runtime fit and Hermes connection

**Status: IN PROGRESS**

Run the adapted upstream server/HUD in the accepted Windows + Docker environment and connect it to the existing Hermes COMPANION runtime without replacing or weakening iai.

#### P4-02A — read-only runtime-fit discovery

**Status: PASS / CLOSED — August 27, 2026**

Accepted v2 evidence:

- HUD workspace branch `orion-mvp` at `aeb0643f8119a4d4f8b78a950194e9778eea4af2` and clean;
- accepted Hermes/iai container `orion-iai-m5-c` running;
- image `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix` confirmed;
- Docker published ports: none;
- container bridge address observed as `172.17.0.3` during the acceptance run;
- container port `8642`: CLOSED;
- container port `9119`: CLOSED;
- Windows localhost port `8642`: CLOSED;
- Windows localhost port `9119`: CLOSED;
- Windows localhost native iai Brain port `4477`: OPEN;
- host Python: `3.11.3`;
- resolved Hermes API route: `not-listening`;
- required Orion HUD source layout present;
- no configuration write, no container change, and no secret output occurred.

Conclusion: P4-02B must **enable Hermes API service behavior first**. Publishing or proxying port `8642` alone would not work because no service is currently listening on that port. After enablement, expose the API to the Orion HUD using the accepted local security model. Native iai Brain is already reachable independently on `4477` and should remain the memory-management destination.

The first P4-02A revision failed only in the diagnostic probe because nested Windows PowerShell -> Docker -> Python argument handling stripped quotes from embedded Python. No runtime/configuration mutation occurred. v2 removed nested Python execution and read Linux socket tables directly.

Canonical accepted script: `scripts/phase4/p4-02a-runtime-fit-discovery-v2.ps1`.

#### P4-02B — Hermes API enablement and Orion HUD runtime integration

**Status: NEXT — blocked only by source-preservation pass**

Before changing the accepted runtime, finish preserving the Phase 2/3 operational code and custom Hermes+iai image build recipe identified in `docs/rebuild/reproducibility-inventory.md`.

Then:

- enable only the Hermes API behavior required by the upstream Orion HUD;
- keep API credentials local and out of GitHub;
- expose the API through the smallest safe local/container boundary;
- preserve current COMPANION identity and iai automatic memory integration;
- adapt upstream macOS/launchd assumptions to Windows + Docker;
- resolve browser/TLS access for the HUD;
- prove typed HUD interaction and live Hermes status before installing optional voice/cloud components.

P4-02 tests integration boundaries, not iai internals.

### P4-03 — Orion document actions in the HUD

Wire the already-accepted Phase 3 operational components into the Orion interface: create inbox drafts, request iai-backed destination recommendations, and resolve exact source notes when requested.

### P4-04 — Approval and recovery UX

Surface P3-05 preview/apply semantics in the Orion HUD: exact target, exact diff, explicit approve/deny, stale-preview protection, recovery evidence, and approved restore. Existing upstream approval-event UX may be reused where it preserves the Orion trust model.

### P4-05 — Native iai Brain and companion experience

Add the native iai Brain as the Memory / Brain destination from Orion. Preserve the upstream voice/typed-chat interaction model where useful, but ensure iai remains the actual memory authority and Orion-specific document actions remain outside iai.

### P4-06 — MVP orchestration acceptance

Run one bounded end-to-end flow through the Orion application and close Phase 4 for MVP if the accepted subsystems work together without bypasses, duplicate memory semantics, or hidden write paths.

## Intent preservation

**Intent status: PRESERVED.**

Using `jarvis_ai` as the application baseline preserves the reason Orion chose Hermes: a Hermes-native interaction shell rather than a competing agent runtime or UI stack. The iai fork does not change Orion's memory design; upstream iai remains authoritative and the fork is only a compatibility/tracking surface. Orion remains a distinct product because its iai memory system, Obsidian authority model, document workflow, trust boundaries, deployment environment, and product identity remain controlling.
