# OR-LIFE-003a Provenance Decision

Date: 2026-09-07
Decision: **ACCEPTED**
Intent-preservation status: **PRESERVED**

## Decision

For Orion Phase 1, accept iai-pme 3.0.8's native daemon-absent recall provenance label:

`_source = "daemon-down-full"`

as satisfying OR-LIFE-003a's requirement to prove correct recall from the canonical store while the daemon is absent and the system remains in HIBERNATION.

Do not patch iai solely to rename this provenance value to `direct-store`.

## Rationale

Pinned iai 3.0.8 source and vendor tests use `daemon-down-full` for the daemon-independent full structural recall path. This path opens the canonical store directly after daemon RPC is unavailable and returns semantic recall results without starting the daemon.

The earlier Orion wording that expected the literal value `direct-store` was therefore stricter than the installed vendor contract and did not preserve dependency semantics.

The acceptance criterion is updated from a literal implementation string to the actual architectural requirement:

- daemon absent before recall
- recall returns the correct result from the canonical iai store
- provenance identifies a daemon-independent/direct-store path according to the pinned vendor contract
- daemon remains absent after recall
- lifecycle remains HIBERNATION
- Hermes/iai MCP wrapper remains absent
- no wake signal, daemon port, or daemon token appears
- Windows iai Scheduled Task is not activated by the direct-read operation

For pinned iai 3.0.8, the accepted provenance value for that full path is `daemon-down-full`.

## Runtime evidence — HIBERNATION Test B

Second independent HIBERNATION cycle precondition:

```text
Lifecycle: HIBERNATION
Daemon count: 0
Wrapper count: 0
wake.signal present: False
daemon.port present: False
daemon.token present: False
TEST B PARKED STATE: READY
```

Recall command used the isolated iai CLI against marker:

`ORION_CAPTURE_FRESH_GATEWAY_20260829`

Observed:

```text
Recall exit code: 0
JSON parse: True
Recall source: daemon-down-full
Hit count: 5
Marker found: True
```

Post-read state:

```text
Lifecycle after: HIBERNATION
Daemon count after: 0
Wrapper count after: 0
wake.signal after: False
daemon.port after: False
daemon.token after: False
Task restarted: False
```

The test script printed `NEEDS REVIEW` only because its local predicate incorrectly required `_source == "direct-store"`. All runtime behavior required by the lifecycle architecture passed.

## Acceptance verdict

**OR-LIFE-003a: PASS / ACCEPTED** for pinned iai-pme 3.0.8.

This decision preserves the reason iai was selected as Orion's canonical memory/lifecycle dependency: Orion follows the supported vendor behavior rather than creating a translation layer or patching a harmless provenance label.

No memory semantics, retrieval logic, daemon behavior, lifecycle control, or persistence format is changed by this decision.
