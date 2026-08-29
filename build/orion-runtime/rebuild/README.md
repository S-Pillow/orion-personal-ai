# Historical Docker Runtime Rebuild Candidate

Status: **HISTORICAL / FROZEN**

This directory preserves the former Docker/container rebuild path that was developed before **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)** moved the controlling architecture to native Windows on 2026-08-29.

It is retained for provenance, regression archaeology, and explicitly requested legacy recovery. It is **not** the current Orion rebuild path and should not be executed for normal v2.6 recovery.

## Historical image chain

1. `nousresearch/hermes-agent@sha256:d597ca1f766ff23ff86437fe5e0f36a6049166ce91df917d9577d7418f0767de`
2. Hermes + `ddgs==9.14.4`
3. isolated `/opt/iai` CPython 3.12 + `iai-pme==3.0.0`
4. pinned `BAAI/bge-small-en-v1.5` snapshot revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`
5. upgrade iai to `iai-pme==3.0.8`
6. combine `/opt/iai` with the Hermes ddgs image
7. apply the bounded `recent_thread` serializer compatibility overlay

The rebuild orchestration used `orion-rebuild-*` tags and a disposable model-acquisition container. It did not use the historical accepted `orion-iai-m5-c` container, accepted iai data volume, or accepted production image tag during disposable validation.

## Historical F5E acquisition dependency

SP4B v1 proved that the accepted F2 image did not contain `huggingface_hub`.
That was an acquisition-helper dependency, not an accepted iai runtime dependency.

The acquisition helper installed `huggingface-hub==0.34.1` only inside the disposable model-acquisition container, verified that exact version, disabled Xet for acquisition, downloaded the pinned snapshot, and verified the three model artifact hashes. The next F5E image copied only `/opt/iai/hf`; the transient acquisition dependency was not copied into the final Orion runtime.

The PyPI pure-Python wheel SHA-256 for `huggingface_hub-0.34.1-py3-none-any.whl` was recorded as:

`60d843dcb7bc335145b20e7d2f1dfe93910f6787b2b38a936fb772ce2a83757c`

## Historical run mode

`build-orion-runtime.ps1` defaults to plan-only and performs Docker work only when explicitly invoked with `-Execute`.

Under v2.6, treat even `-Execute` as a **legacy recovery action requiring explicit intent**, not as the normal Orion rebuild procedure.

## Historical provenance

- historical final image ID: `sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`
- ddgs 9.14.4 pure-Python wheel SHA-256: `acb084c34bf1110c974caf7e5e5a2c1973beb4bd9e170bfd191fe5ed2d2b2d6c`
- iai 3.0.0 CPython 3.12 manylinux x86-64 wheel SHA-256: `6621624cdb6e26528eb4d0e905763e13c75802b9847def01de578825b7778bb5`

See `../accepted-build-lineage.md` for the preserved historical Docker lineage.

## Current v2.6 recovery direction

The current accepted runtime is native Windows. Recovery work should start from the native source-preservation artifacts in `scripts/phase0/` and the current root `README.md` / `docs/phase1/status.md`, not from this Docker rebuild directory.
