# Orion Runtime Rebuild Candidate

Status: SOURCE CANDIDATE - NOT YET DISPOSABLE-VALIDATED

This directory turns the accepted Orion runtime lineage into one clean rebuild path.
It does not replace the accepted live runtime until a separate disposable validation
proves the rebuilt image behavior.

## Image chain

1. `nousresearch/hermes-agent@sha256:d597ca1f766ff23ff86437fe5e0f36a6049166ce91df917d9577d7418f0767de`
2. Hermes + `ddgs==9.14.4`
3. isolated `/opt/iai` CPython 3.12 + `iai-pme==3.0.0`
4. pinned `BAAI/bge-small-en-v1.5` snapshot revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`
5. upgrade iai to `iai-pme==3.0.8`
6. combine `/opt/iai` with the Hermes ddgs image
7. apply the bounded `recent_thread` serializer compatibility overlay

The rebuild orchestration uses `orion-rebuild-*` tags and a disposable model-acquisition
container. It does not use the accepted `orion-iai-m5-c` container, accepted iai data
volume, or accepted production image tag.

## Run modes

`build-orion-runtime.ps1` defaults to plan-only. It performs Docker work only when
explicitly invoked with `-Execute`.

SP4A preserves this source candidate in GitHub. SP4B is responsible for executing it
against disposable images/containers and comparing the result with accepted behavioral
contracts before this path is promoted as Orion's recovery mechanism.

## Known provenance

- accepted final image ID: `sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`
- ddgs 9.14.4 pure-Python wheel SHA-256 observed from PyPI: `acb084c34bf1110c974caf7e5e5a2c1973beb4bd9e170bfd191fe5ed2d2b2d6c`
- iai 3.0.0 CPython 3.12 manylinux x86-64 wheel SHA-256 observed from PyPI: `6621624cdb6e26528eb4d0e905763e13c75802b9847def01de578825b7778bb5`
- exact iai 3.0.8 wheel artifact hash remains to be captured during SP4B
- exact dependency closure is not yet claimed byte-identical

The preserved accepted lineage remains in `../accepted-build-lineage.md`.
