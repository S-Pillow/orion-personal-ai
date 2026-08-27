# Orion Accepted Runtime Build Lineage

Source-preservation snapshot: August 27, 2026.

## Accepted Hermes base

- upstream tag: nousresearch/hermes-agent:v2026.8.18
- linux/amd64 manifest digest: sha256:d597ca1f766ff23ff86437fe5e0f36a6049166ce91df917d9577d7418f0767de
- accepted custom image: hermes-agent-local:v2026.8.18-ddgs
- accepted custom image ID: sha256:17516e96105e957a192007cc8123f92d89b69e5676d41a8cb7bb3a42c25420f2
- added package: ddgs==9.14.4
- preserved launcher SHA-256: c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b
- preserved accepted Hermes Dockerfile SHA-256: 8f8a622761cf6a4b8a90af82688469e381c3814f15a0a4e681b25ef518f0e4e6

## iai image lineage

- orion-iai-feas:v3.0.0-f2 = sha256:1fa06fcc3f4c275ffc1109821469f0e154b47610c98b219df04aef7d60459154
- F2 installed isolated managed CPython 3.12 under /opt/iai/python
- F2 created /opt/iai/venv and installed iai-pme==3.0.0 wheel-only
- F5E baked BAAI/bge-small-en-v1.5 revision 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
- orion-iai-feas:v3.0.0-f5e = sha256:a537708bc22526990c0c5de98250603bc7ba398d123cf6ee4f090a3a7fe91a6b
- model.safetensors SHA-256: 3c9f31665447c8911517620762200d2245a2518d6e7208acc78cd9db317e21ad
- tokenizer.json SHA-256: d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66
- config.json SHA-256: 094f8e891b932f2000c92cfc663bac4c62069f5d8af5b5278c4306aef3084750
- orion-iai-feas:v3.0.8-m2 = sha256:5bc1ee2399cd1d7ad6881e6feea9ddc536ae578d00917f3d18b4479131d05216
- M2 upgraded iai-pme to 3.0.8 using binary wheels

## Combined Hermes + iai

- M4 combined the accepted Hermes custom base with /opt/iai from iai M2
- orion-hermes-iai:v2026.8.18-iai3.0.8-m4 = sha256:700eb55102b1fadad3c111968794d5b82f581b0ddb616aa028421cb63b721513
- M5 added the bounded SessionStartPayload recent_thread serializer compatibility overlay
- accepted final image: orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix
- accepted final image ID: sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500

## Historical build-source preservation

- PH2-IAI-M2-v3.0.8-disposable-native-hermes-hook-wiring.ps1 preserved
- PH2-IAI-M2 SHA-256: db3b0ccd593afa762793425ac72ad0a937d5bff508dfad8e72197e0f893765ff
- PH2-IAI-M5-serializer-fix-build-v2.ps1 preserved
- PH2-IAI-M5 SHA-256: 7df1f768cc113883d9987175614b61272a5dd0dc8d6e3ca33bb38bc7bcb349e6
- PH2-IAI-M4-source-reviewed-final.ps1 was not present locally during SP3 and is not claimed preserved

## Current rebuild status

- accepted launcher source: preserved
- accepted Hermes custom Dockerfile source: preserved
- accepted Phase 2/3 operational scripts: preserved by SP2
- available historical M2 and M5 build harnesses: preserved
- exact ddgs==9.14.4 wheel filename/hash remains unresolved
- successful F5E acquisition/assembly automation still needs a clean canonical rebuild script
- M4 historical source script is missing and must be reconstructed from evidence if needed
- byte-identical rebuild from source is not yet claimed
- exact rollback still requires separately retained private recovery artifacts and image archive
