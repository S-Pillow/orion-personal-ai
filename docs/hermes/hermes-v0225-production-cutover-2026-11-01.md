# Hermes v0.22.5 Production Cutover — 2026-11-01

Status: **PASS / CLOSED**

PR: #81 — `feature/hermes-v0225-controlled-migration`

## Final production result

Orion production now runs Hermes v0.22.5 at exact upstream release commit:

`bf0203a794a07aac3ff764972ab9087baa4e4f4e`

Successful cutover evidence:

- `STAGE_VENV=PASS`
- `STAGE_PYTHON_DEPS=PASS`
- `STAGE_PRODUCTS=PASS`
- `QUALIFIED_SOURCE_PRESERVED=PASS`
- published launcher: `%LOCALAPPDATA%\hermes\bin\hermes.exe`
- `HERMES_LAUNCHER=PASS`
- `ORION_HERMES_PATH=PASS`
- Ollama API healthy with accepted process-local `rocm_v7_1`
- Hermes API healthy
- HUD bridge ready and opened
- `ORION_START=PASS`
- `PRODUCTION_CUTOVER=PASS`

Rollback backup remains preserved at:

`C:\Users\spill\AppData\Local\Orion\backups\hermes-pre-v0225-20261101-032549`

## Installation path used

The successful resume used Hermes v0.22.5's supported source-install package-management stages rather than a manually bound source-tree venv:

1. verify the qualified v0.22.5 source and rollback backup;
2. remove only the incomplete manually-created `venv`;
3. run installer `venv`;
4. run installer `python-deps`;
5. run installer `products`;
6. verify source HEAD and Orion compatibility hashes remained unchanged;
7. verify the published Windows launcher;
8. start Orion through the accepted operator lifecycle.

No repository stage was run during the successful resume, so the qualified Orion-modified source checkout was not recloned or reset.

## Compatibility disposition

Retained in production:

- P4-04A authenticated bounded audio relay on the 8642 API-server gateway;
- P6-03 exact pre-repair `jobs.json` byte preservation;
- P6-04A durable execution `error_class` persistence.

Retired because v0.22.5 provides the relevant native behavior:

- old Orion P5 approval compatibility backport;
- old P6-04 durable-run-evidence implementation.

## Acceptance interpretation

This migration is complete for the personal Orion deployment. The owner explicitly ended further exhaustive qualification before cutover. Historical cron/asyncio diagnostics remain useful provenance but are not the resume point and do not reopen the migration by default.

Future problems should be handled as concrete Orion/Hermes defects if they occur during normal use.

The earlier qualification documents remain historical records of the pre-cutover decision process. This file is the canonical closure record for the v0.22.5 migration.
