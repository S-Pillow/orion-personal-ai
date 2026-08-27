# SP4A — Canonical Rebuild Source Candidate Closure

**Status: PASS / CLOSED — August 27, 2026**

SP4A converted the preserved Orion runtime lineage into a single canonical rebuild-source candidate without executing Docker or changing the accepted runtime.

Accepted GitHub commit:

`98aa7b73d2b14619264bcaabbbf6acadfee204e3`

Commit message:

`build: add canonical Orion runtime rebuild candidate`

## Preserved rebuild source

The canonical candidate now lives under `build/orion-runtime/rebuild/` and contains:

- pinned Hermes/ddgs base Dockerfile;
- isolated Python 3.12 + iai 3.0.0 F2 stage;
- pinned BAAI/bge-small-en-v1.5 acquisition and artifact verification;
- F5E model-bake assembly;
- iai 3.0.8 M2 upgrade stage;
- reconstructed M4 composition;
- bounded M5 `recent_thread` serializer overlay;
- final-image verification helper;
- one `build-orion-runtime.ps1` orchestration entry point;
- rebuild README and provenance notes.

The generated rebuild orchestrator defaults to plan-only and requires explicit `-Execute` before any Docker work occurs.

## Acceptance evidence

Observed SP4A output:

- `SP4A_PREFLIGHT=PASS`
- `SP4A_REPO_SYNC=PASS`
- `SP4A_GENERATED_HASHES=PASS`
- `SP4A_SECRET_LITERAL_SCAN=PASS`
- `SP4A_GENERATED_POWERSHELL_PARSE=PASS`
- `SP4A_STAGED_SCOPE=PASS`
- `SP4A_COMMIT_CREATED=PASS`
- `SP4A_WORKSPACE_CLEAN=PASS`
- `SP4A_REMOTE_MAIN_VERIFIED=PASS`
- `SP4A_NO_DOCKER_EXECUTION=PASS`
- `SP4A_NO_RUNTIME_CHANGE=PASS`
- `SP4A_REBUILD_SOURCE_CANDIDATE=PASS`

The local and remote `main` head after SP4A was `98aa7b73d2b14619264bcaabbbf6acadfee204e3`.

## Boundary

SP4A proves source preservation and parser-valid rebuild orchestration only. It does not prove that the entire image chain can be rebuilt successfully. That is SP4B.

SP4B must execute the committed rebuild candidate only against disposable `orion-rebuild-*` images/containers, verify the pinned model artifacts, iai 3.0.8, and the M5 serializer contract, and prove that the accepted live container/image/data volume remain untouched.
