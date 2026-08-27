# SP3 Build-Source Preservation Acceptance

**Status: PASS / CLOSED — August 27, 2026**

SP3 preserved accepted Orion runtime build-source evidence in GitHub without executing Docker or mutating the live runtime.

## Accepted commit

- `37d1b24121c68262585e0ab447e23d7c24a02ed3`
- message: `source: preserve accepted runtime build lineage`

## Preserved exact source

- `build/orion-runtime/historical/Start-Hermes.accepted.ps1`
  - SHA-256: `c265f485298d488bcd0a5f368138cef3b1db75bfddd831c794e5bbe06a411a7b`
- `build/orion-runtime/historical/Dockerfile.hermes-ddgs.accepted`
  - SHA-256: `8f8a622761cf6a4b8a90af82688469e381c3814f15a0a4e681b25ef518f0e4e6`
- `build/orion-runtime/historical/PH2-IAI-M2-v3.0.8-disposable-native-hermes-hook-wiring.ps1`
  - SHA-256: `db3b0ccd593afa762793425ac72ad0a937d5bff508dfad8e72197e0f893765ff`
- `build/orion-runtime/historical/PH2-IAI-M5-serializer-fix-build-v2.ps1`
  - SHA-256: `7df1f768cc113883d9987175614b61272a5dd0dc8d6e3ca33bb38bc7bcb349e6`

The historical M4 source script `PH2-IAI-M4-source-reviewed-final.ps1` was not present locally and is not claimed preserved.

## Preserved lineage evidence

`build/orion-runtime/accepted-build-lineage.md` records the accepted runtime chain from the pinned Hermes base through the ddgs image, isolated iai Python environment, pinned embedding model snapshot, iai 3.0.8 update, M4 composition, and M5 `recent_thread` serializer compatibility overlay.

The accepted final image remains:

- tag: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix`
- image ID: `sha256:0222e2199cbb135bf1989283b1dba7a36f936aab3f82c3fbae048659dd8b2500`

## Safety

Accepted run markers included:

- `SP3_V2_SOURCE_HASHES=PASS`
- `SP3_V2_M4_ABSENCE_CONFIRMED=PASS`
- `SP3_V2_EXACT_SOURCE_COPY=PASS`
- `SP3_V2_GIT_EXACT_BYTES=PASS`
- `SP3_V2_REMOTE_MAIN_VERIFIED=PASS`
- `SP3_V2_NO_DOCKER_COMMANDS=PASS`
- `SP3_V2_NO_RUNTIME_CHANGE=PASS`
- `SP3_V2_BUILD_SOURCE_PRESERVATION=PASS`

No Docker command was executed, no live container/image/runtime was changed, and no known literal secret pattern was committed.

## Remaining reproducibility gaps

SP3 materially reduces the rebuild gap but does not yet justify claiming a clean-machine deterministic rebuild. Remaining work includes:

- canonicalizing a fresh-machine rebuild script from the preserved evidence;
- reconstructing the M4 build step because its historical source script is missing;
- preserving/validating the F5E model acquisition and assembly path as a clean canonical build unit;
- resolving exact package/wheel provenance where required for stronger reproducibility;
- running a disposable rebuild verification without touching the accepted live runtime.

SP3 is closed. The next source-preservation unit is SP4: create a canonical, non-live rebuild implementation from the now-preserved evidence, then validate it in a disposable path before allowing it to become the documented recovery mechanism.
