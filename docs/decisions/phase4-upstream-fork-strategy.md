# Decision — Phase 4 Upstream Fork Strategy

**Status: ACCEPTED — August 27, 2026**

## Decision

Orion will use a maintained GitHub fork for third-party applications that it materially modifies.

For Phase 4, `eadmin2/jarvis_ai` is the upstream HUD / voice / orchestration application and should be forked under the `S-Pillow` GitHub account before Orion source modifications continue.

`S-Pillow/orion-personal-ai` remains the canonical Orion integration/control repository. It should not absorb a wholesale copy of the JARVIS application source.

## Repository roles

### `S-Pillow/orion-personal-ai`

Owns:

- Orion PRD/project state references;
- architecture and trust-boundary decisions;
- phase plans and acceptance evidence;
- integration/bootstrap scripts;
- Orion-specific glue that spans multiple components.

### Orion fork of `eadmin2/jarvis_ai`

Owns:

- actual HUD/voice application source;
- user-facing Orion branding;
- Windows/runtime adaptations to the upstream application;
- Orion-specific HUD features and service integrations;
- future upstream merges/comparisons.

The fork should use the user's repository as `origin` and `eadmin2/jarvis_ai` as `upstream`.

## Initial baseline

- Upstream: `eadmin2/jarvis_ai`
- Pinned commit: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- License: MIT
- Initial Orion adaptation branch: `orion-mvp`

The upstream `LICENSE` and copyright notice remain intact.

## What not to fork by default

A dependency does not need an Orion fork merely because Orion uses it.

- iai remains an upstream dependency and canonical memory subsystem unless Orion begins carrying source-level modifications that require a maintained fork.
- Hermes remains an upstream dependency unless Orion begins carrying source-level modifications that require a maintained fork.

Integration patches, compatibility notes, and deployment glue may remain in `orion-personal-ai` when they do not require maintaining a divergent upstream source tree.

## Why

This model preserves upstream history and provenance, keeps Orion's main repository focused, allows clean upstream updates, makes product code visible on GitHub, and avoids turning vendored third-party source into an untraceable copy.

**Intent status: PRESERVED.** The approach keeps the proven upstream application intact as a foundation while making Orion's product-specific changes explicit and maintainable.
