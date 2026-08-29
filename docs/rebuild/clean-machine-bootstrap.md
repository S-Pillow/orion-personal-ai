# Orion clean-machine source and recovery procedure

Status: **NATIVE-WINDOWS RECOVERY IN PROGRESS — updated 2026-08-29**

This procedure prevents Orion from depending on one workstation. It has been realigned to **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**.

## Current architecture

The controlling runtime is native Windows, not the former Docker/s6 stack.

Current accepted baseline:

- Hermes tag `v2026.8.27`
- package `0.20.6`
- commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- profile `companion`
- Windows persistence task `Hermes_Gateway_companion`
- loopback API `127.0.0.1:8642`
- local Ollama model `qwen3.5-hermes:9b`
- verified context `65536`

## Source repositories

Clone at minimum:

- `S-Pillow/orion-personal-ai`
- `S-Pillow/iai-personal-memory-engine`

`S-Pillow/jarvis_ai` is historical/possible-future HUD source and is not required for the current Phase 0/1 recovery path.

## Native Phase 0 recovery

The accepted Phase 0 reproducibility artifact is:

`scripts/phase0/Orion-Phase0-Hermes-Native-AcceptedBaseline.ps1`

Use its `Verify` mode first on a machine believed to contain the accepted baseline. Use `Configure` only when intentionally reconstructing the accepted Phase 0 state and after reviewing local secret inputs/rollback requirements.

Example verification:

```powershell
powershell.exe `
  -NoProfile `
  -ExecutionPolicy Bypass `
  -File ".\scripts\phase0\Orion-Phase0-Hermes-Native-AcceptedBaseline.ps1" `
  -Action Verify
```

The script never runs `hermes update` and does not print API or Discord secret values.

## Native Phase 1 recovery status

Native Phase 1 is not yet accepted.

Current known state:

- Python 3.11 dedicated venv
- `iai-pme==3.0.8`
- crypto initialization passed
- Rust embedder passed
- Scheduled Task registration succeeded
- daemon startup is blocked by an upstream Windows `signal.SIGHUP` compatibility defect

Do not treat iai capture/recall/HIBERNATION as recoverable accepted features yet. When an accepted compatibility solution exists, this procedure must be extended with exact Phase 1 install/configure/verify/rollback steps.

## Historical Docker recovery

The former Docker rebuild tooling remains in:

- `scripts/rebuild/`
- `build/orion-runtime/rebuild/`
- historical SP4 documentation

Those paths are frozen for legacy recovery and provenance. They are **not** the normal v2.6 recovery procedure. Do not execute the historical Docker build path unless legacy restoration is explicitly intended.

## Private recovery material

Keep these outside GitHub:

- API/server credentials
- Discord credentials
- iai encryption key or accepted backup containing it
- Obsidian vault contents when applicable
- intentionally retained private exports/backups

## Current recovery claim

As of 2026-08-29:

- native Phase 0 recovery source: **preserved and accepted**
- native Phase 1 recovery source: **incomplete**
- full v2.6 clean-machine reconstruction: **not yet claimed**

The historical SP4B Docker rebuild remains valid evidence for the former architecture only.
