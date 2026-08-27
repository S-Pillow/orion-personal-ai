# P4-01 Revised — Fork-First Upstream HUD Adoption Closure

**Status: PASS / CLOSED — August 27, 2026**

## Accepted result

Orion now uses the real `jarvis_ai` application as its HUD / voice / orchestration source baseline instead of the earlier standalone custom dashboard mockup.

Accepted repository topology:

- Orion integration/control repo: `S-Pillow/orion-personal-ai`
- Orion HUD fork: `S-Pillow/jarvis_ai`
- HUD upstream: `eadmin2/jarvis_ai`
- pinned HUD upstream commit: `88998de8369e9d36f6d434b5e01feb93fcf1c33f`
- Orion adaptation branch: `orion-mvp`
- accepted branch head: `aeb0643f8119a4d4f8b78a950194e9778eea4af2`

The user also created `S-Pillow/iai-personal-memory-engine` as the Orion compatibility/upstream-tracking fork of `CodeAbra/iai-personal-memory-engine`. This does not change iai's role as Orion's canonical memory subsystem.

## Accepted P4-01 delta

The final branch delta from the pinned upstream HUD commit is exactly:

- `ORION-UPSTREAM.md`
- `server/config/server.orion.example.yaml`
- `server/hud/index.html`

The baseline adoption:

- preserves the upstream MIT license and attribution;
- changes visible JARVIS product identity to Orion;
- changes the displayed/default conversation identity to `orion-main`;
- changes the displayed/default session scope to `orion:user:main`;
- adds Orion-specific config/provenance without mutating the upstream example config;
- makes no `server/server.py` change;
- makes no iai change;
- makes no vault-service or runtime-secret change.

## Final acceptance evidence

Final successful run reported:

- `P4_01R4_GIT_AVAILABLE=PASS`
- `P4_01R4_WORKSPACE_PRESENT=PASS`
- `P4_01R4_ORIGIN_IS_FORK=PASS`
- `P4_01R4_UPSTREAM_REMOTE=PASS`
- `P4_01R4_BRANCH_READY=PASS`
- `P4_01R4_UPSTREAM_PIN=PASS`
- `P4_01R4_EXISTING_CHANGES_BOUNDED=PASS`
- `P4_01R4_LICENSE_PRESERVED=PASS`
- `P4_01R4_VISIBLE_ORION_BRANDING=PASS`
- `P4_01R4_ORION_CONFIG_OVERLAY=PASS`
- `P4_01R4_UPSTREAM_MANIFEST=PASS`
- `P4_01R4_LOCAL_COMMIT_READY=PASS`
- `P4_01R4_UPSTREAM_DELTA_BOUNDED=PASS`
- `P4_01R4_WORKSPACE_CLEAN=PASS`
- `P4_01R4_CODE_PUSHED_TO_FORK=PASS`
- `P4_01R4_NO_SERVER_CORE_CHANGE=PASS`
- `P4_01R4_IAI_MEMORY_INTENT_PRESERVED=PASS`
- `P4_01_REVISED_FORK_ADOPTION=PASS`

## Iteration record

- v1: PowerShell parse failure before execution due malformed here-string.
- v2: fork setup and config work progressed, then blank-string parameter binding failed while generating Markdown.
- v3: safely resumed the partial workspace but correctly stopped when it found the expected Orion HUD branding had not actually been written.
- v4: repaired the missing branding idempotently, regenerated bounded overlay/provenance files, committed exactly the allowed delta, and pushed the branch successfully.

These failed iterations were harness/bootstrap defects. No iai or production runtime behavior was changed by them.

## Canonical script

Accepted bootstrap/repair implementation:

`scripts/phase4/p4-01-adopt-jarvis-fork.ps1`

## Next

P4-02 — Orion runtime fit and Hermes connection.

The next work should bring up the forked upstream server/HUD against the accepted Windows + Docker environment, prove typed interaction with the existing Hermes COMPANION path first, and preserve iai automatic memory behavior without re-testing iai internals.

**Intent status: PRESERVED.**
