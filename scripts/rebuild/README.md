# Historical Docker recovery scripts

> **LEGACY RECOVERY ONLY — 2026-08-29.** The scripts in this directory prepare or execute the former Docker/runtime rebuild path. They are not the current ORION Master PRD v2.6 recovery path.

For current native-Windows recovery, start with:

- `scripts/phase0/Orion-Phase0-Hermes-Native-AcceptedBaseline.ps1`
- `docs/rebuild/clean-machine-bootstrap.md`
- `docs/rebuild/reproducibility-inventory.md`

Do not run `Prepare-Orion-Recovery-Workspace.ps1 -BuildRuntime` unless legacy Docker restoration is explicitly intended.
