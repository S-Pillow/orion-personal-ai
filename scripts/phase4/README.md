# Phase 4 scripts

This directory contains both current PRD v2.8 operator tooling and preserved historical scripts.

## Current PRD v2.8 tooling

- `p4-04a-hermes-audio-gateway.py` — fail-closed source patcher for the accepted Hermes `0.20.6` gateway. It verifies the exact expected Git blob before applying, compile-checks the patched module, creates a rollback backup/manifest, supports verification and exact rollback, and includes a synthetic self-test.
- `p4-04a-hermes-audio-gateway.ps1` — Windows operator wrapper that resolves the Hermes Python/module path, runs the patcher, and refuses Apply/Rollback while port 8642 is listening. It never restarts Hermes automatically.

These P4-04A files are current work and are not part of the historical archive below.

## Historical archive

> **SUPERSEDED / REFERENCE ONLY — 2026-08-29.** The older P4-01/P4-02 Jarvis/HUD/container scripts in this directory belong to the former implementation direction. They are preserved for provenance and explicitly requested legacy recovery only.
