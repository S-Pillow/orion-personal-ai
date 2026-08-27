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

`S-Pillow/orion-personal-ai` remains the canonical Orion integration/control repository for project state, architecture decisions, acceptance evidence, integration scripts, and cross-component glue.

The actual Orion HUD/voice application source lives in `S-Pillow/jarvis_ai`, with `eadmin2/jarvis_ai` retained as its upstream source.

The iai fork exists for reproducibility, upstream contribution work, and narrowly scoped compatibility patches when necessary. Upstream iai behavior remains controlling for MVP. The presence of the fork does not change the decision to use iai as written.

Hermes remains upstream-only unless sustained source-level divergence later justifies a fork.

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

Final acceptance markers included:

- `P4_01R4_VISIBLE_ORION_BRANDING=PASS`
- `P4_01R4_ORION_CONFIG_OVERLAY=PASS`
- `P4_01R4_UPSTREAM_MANIFEST=PASS`
- `P4_01R4_UPSTREAM_DELTA_BOUNDED=PASS`
- `P4_01R4_WORKSPACE_CLEAN=PASS`
- `P4_01R4_CODE_PUSHED_TO_FORK=PASS`
- `P4_01R4_NO_SERVER_CORE_CHANGE=PASS`
- `P4_01R4_IAI_MEMORY_INTENT_PRESERVED=PASS`
- `P4_01_REVISED_FORK_ADOPTION=PASS`

Iteration notes:

- v1 failed at PowerShell parse time before execution because of a malformed here-string.
- v2 progressed through clone/fork setup and config generation, then failed on blank-string binding inside a helper used for generated Markdown.
- v3 correctly resumed the partial workspace but assumed the HUD branding change from v2 had persisted; Git state showed only the config overlay had changed, so verification stopped before mutation.
- v4 repaired the missing branding idempotently, regenerated the bounded overlay/provenance files, committed exactly the allowed delta, and pushed the accepted branch successfully.

Canonical accepted bootstrap script is stored in `scripts/phase4/p4-01-adopt-jarvis-fork.ps1`.

This closes the earlier custom standalone dashboard-shell direction. That mockup is not the Orion product baseline.

### P4-02 — Orion runtime fit and Hermes connection

**Status: NEXT**

Run the adapted upstream server/HUD in the accepted Windows + Docker environment and connect it to the existing Hermes COMPANION runtime without replacing or weakening iai.

Initial scope:

- determine the correct host/container path to the existing Hermes API surface;
- enable/configure only the API behavior required by the upstream application;
- keep API credentials local and out of GitHub;
- adapt upstream macOS/launchd assumptions to Windows + Docker;
- resolve browser/TLS access for the HUD;
- preserve current COMPANION identity and iai automatic memory integration;
- avoid installing optional voice/cloud pieces until they are needed for MVP bring-up;
- prove typed HUD interaction and live Hermes status first, then layer voice on top.

P4-02 should test integration boundaries, not re-test iai internals.

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
