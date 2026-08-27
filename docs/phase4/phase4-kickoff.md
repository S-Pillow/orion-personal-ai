# Phase 4 — Orion Orchestration and User Experience

**Status: ACTIVE — started August 27, 2026**

Phase 3 is closed for MVP. Phase 4 turns the accepted Orion subsystems into a coherent user-facing control layer without changing their underlying responsibilities.

## Governing architecture

- Hermes remains the local agent runtime.
- iai remains the authoritative memory and semantic-recall engine.
- The native iai Brain remains the authoritative detailed memory-management UI.
- Obsidian remains the authoritative human-facing document vault.
- Orion exact-source, inbox, destination-recommendation, approval, and recovery components remain the accepted document orchestration primitives.
- `eadmin2/jarvis_ai` is adopted as Orion's upstream HUD / voice / orchestration application baseline rather than rebuilding an equivalent interface from scratch.
- Third-party applications that Orion materially modifies should live in maintained forks rather than being copied wholesale into `orion-personal-ai`.
- The Orion layer may adapt and extend the upstream application, but must not reimplement iai memory semantics, create a second semantic index, or bypass accepted approval boundaries.

## Repository strategy

`S-Pillow/orion-personal-ai` remains the canonical Orion integration/control repository for project state, architecture decisions, acceptance evidence, integration scripts, and Orion-specific orchestration glue.

The HUD application itself should live in a fork of `eadmin2/jarvis_ai` under the `S-Pillow` account. The fork is where Orion HUD source changes belong; the original repository remains the `upstream` remote so upstream history and future comparisons remain intact.

Only dependencies Orion materially changes need forks. iai and Hermes remain upstream dependencies unless Orion begins carrying source-level changes that justify maintained forks.

## Upstream application baseline

Approved upstream:

- Repository: `https://github.com/eadmin2/jarvis_ai`
- Pinned baseline commit: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- License: MIT; upstream copyright and license notice must remain intact.

Why this baseline is being adopted:

- It is already designed around Hermes Agent.
- It provides a browser HUD, typed chat, voice transport, live tool activity, STOP/barge-in behavior, approval cards, media panels, usage/machine views, and a Hermes plugin surface.
- Its server already uses Hermes' Sessions API for persistent conversation and run/approval events.
- Reusing the proven application preserves development effort for Orion-specific integration rather than recreating the same shell.

The upstream implementation was primarily tested on macOS/Apple Silicon. Orion's runtime is Windows + Docker, so launchd-specific deployment, host paths, TLS setup, service management, and networking must be adapted rather than copied blindly.

## Phase 4 MVP objective

Provide one local Orion surface where the user can talk/work with the companion, see agent activity and approvals, reach the native iai Brain, create and manage drafts, and invoke the already-accepted Orion vault workflow naturally.

Target user flow:

`Orion HUD -> talk/type to Hermes companion -> iai memory works automatically -> inspect native Brain when needed -> create inbox draft -> iai-backed destination recommendation -> exact diff -> approve/deny -> controlled broker apply -> recovery/restore when needed`

## Execution sequence

### P4-01 Revised — Fork-first upstream JARVIS adoption

**Status: IN PROGRESS**

Purpose: establish a reproducible Orion working branch from the proven upstream application and retain the actual product source on GitHub.

Required implementation:

1. fork `eadmin2/jarvis_ai` under the `S-Pillow` account;
2. clone that fork locally as the Orion HUD workspace;
3. retain `eadmin2/jarvis_ai` as the `upstream` remote;
4. pin the initial Orion baseline to upstream commit `88998de8369e9d36f6d434b5e01feb93fcf1c33f`;
5. retain upstream MIT license and attribution;
6. rebrand only the user-facing HUD identity from JARVIS to Orion at first;
7. create an Orion configuration/provenance overlay rather than mutating the upstream example configuration;
8. push the bounded `orion-mvp` adaptation branch to the fork so actual Orion HUD code is stored on GitHub;
9. leave `server/server.py`, Hermes protocol behavior, iai, vault services, and runtime secrets unchanged during baseline adoption.

The first bootstrap script revision failed at PowerShell parse time before execution because of a here-string parsing defect. Because parsing failed before execution, it did not clone repositories or change local runtime/GitHub state. The corrected v2 bootstrap removes PowerShell here-strings from the generated-content path and adopts the fork-first remote model.

P4-01 Revised acceptance requires:

- fork accessible under `S-Pillow`;
- `origin` points to the fork;
- `upstream` points to `eadmin2/jarvis_ai`;
- exact upstream commit pin verified;
- MIT license preserved;
- bounded Orion branding/config/provenance delta;
- actual Orion source branch pushed to the fork;
- no `server/server.py` change;
- iai memory intent preserved.

This supersedes the earlier custom read-only dashboard-shell direction. That standalone mockup is not the Orion product baseline and should not receive further implementation effort.

### P4-02 — Orion runtime fit and Hermes connection

Run the adapted upstream server in the accepted Windows/Docker environment and connect it to the existing Hermes COMPANION runtime without replacing or weakening iai. Resolve host/container networking, API-server exposure, local secrets, TLS/browser access, and service lifecycle using Orion's current runtime model rather than upstream launchd assumptions.

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

Using `jarvis_ai` as the application baseline preserves the reason Orion chose Hermes in the first place: it gives us a Hermes-native interaction shell rather than building a competing agent runtime or UI stack. Orion remains a distinct product because its accepted iai memory system, Obsidian authority model, document workflow, trust boundaries, deployment environment, and product identity remain controlling. The upstream application is a foundation to adapt, not a replacement for Orion's architecture.
