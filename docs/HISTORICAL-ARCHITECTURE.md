# Historical Architecture Index

Status: **REFERENCE ONLY — 2026-08-29**

The controlling Orion architecture is **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)** and the native-Windows implementation sequence.

This file maps repository areas that contain valid historical evidence from the earlier Docker/s6/Jarvis architecture. These paths are intentionally preserved rather than deleted so old links, hashes, and acceptance evidence remain auditable.

## Historical-only areas

Unless a file has been separately updated to say otherwise, treat the following as historical/reference material:

- `build/orion-runtime/`
- `docs/phase2/`
- `docs/phase3/`
- `docs/phase4/`
- `scripts/phase2/`
- `scripts/phase3/`
- `scripts/phase4/`
- `scripts/rebuild/`

## Historical decisions

- `docs/decisions/ADR-0001-s6-cap-kill-lifecycle.md`
- `docs/decisions/phase4-upstream-fork-strategy.md`

These retain engineering value but are no longer controlling architecture decisions.

## Current areas

Current v2.6 execution should begin from:

- root `README.md`
- `docs/phase1/status.md`
- `docs/decisions/source-reproducibility-and-rebuild.md`
- `docs/rebuild/reproducibility-inventory.md`
- `docs/rebuild/clean-machine-bootstrap.md`
- `scripts/phase0/Orion-Phase0-Hermes-Native-AcceptedBaseline.ps1`

## Current phase state

- Phase 0 native Hermes: **PASS / CLOSED**
- Phase 1 native iai: **IN PROGRESS / PAUSED** at the stock `iai-pme==3.0.8` Windows daemon `signal.SIGHUP` compatibility defect
- HUD work: deferred until Phase 1 acceptance

Historical material must not be cited as proof that a current native-Windows requirement has passed unless that behavior is separately revalidated under v2.6.
