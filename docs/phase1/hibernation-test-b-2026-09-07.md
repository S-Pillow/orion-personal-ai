# Phase 1 HIBERNATION Test B — Daemon-Down Recall

Date: 2026-09-07
Status: **RUNTIME PASS / PROVENANCE-CONTRACT DISCREPANCY REQUIRES DECISION**

Controlling baseline: ORION Master PRD v2.6, native-Windows Phase 1.

## Purpose

Use a second independent HIBERNATION cycle to verify that useful memory recall remains available while iai is parked and that the direct daemon-down read path does not wake the daemon.

This test is distinct from Test A, which measured fresh-wrapper wake latency from a separate HIBERNATION cycle.

## Preconditions

Second-cycle parked state was confirmed before the recall:

```text
Lifecycle before: HIBERNATION
Daemon count before: 0
Wrapper count before: 0
wake.signal before: False
daemon.port before: False
daemon.token before: False
Task last run before: 9/7/2026 4:49:44 AM
```

## Recall command

The canonical isolated iai CLI was invoked directly with the known captured marker:

`iai.exe recall ORION_CAPTURE_FRESH_GATEWAY_20260829 --limit 5 --json`

No Hermes/COMPANION gateway or iai MCP wrapper was started.

## Runtime result

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

Therefore the daemon-down recall path returned the correct known memory and did not wake the daemon, create a wrapper, create IPC port/token files, advance the lifecycle out of HIBERNATION, or trigger the Windows iai Scheduled Task.

## Provenance label discrepancy

The initial Orion acceptance script expected top-level `_source == "direct-store"`, so it printed:

`OR-LIFE-003a DIRECT-STORE FALLBACK: NEEDS REVIEW`

Pinned iai 3.0.8 source and tests show that the full daemon-absent structural recall path is intentionally labeled:

`_source = "daemon-down-full"`

The vendor test suite explicitly asserts that exact label for the full structural daemon-independent path. This is therefore not evidence that the fallback malfunctioned; it is a contract mismatch between Orion's PRD wording and pinned vendor behavior.

## Verdict

Behavioral/runtime result: **PASS**

- correct memory returned
- daemon remained absent
- wrapper remained absent
- lifecycle remained HIBERNATION
- no wake signal
- no IPC port/token files
- Scheduled Task not restarted

Provenance-contract result: **DISCREPANCY**

The runtime returned vendor-defined `daemon-down-full`, while the current Orion requirement text expects `_source: "direct-store"`.

Per Orion's dependency-governance rule, installed/pinned vendor behavior must be treated as authoritative evidence and discrepancies must be surfaced rather than silently reinterpreted. Do not patch or relabel iai solely to satisfy the older Orion string unless an explicit architecture/requirements decision requires it.

Intent-preservation status: **PRESERVED** for the runtime behavior. No Orion supervisor, second memory engine, or replacement recall system was introduced.

## Next decision

Resolve the provenance contract before marking OR-LIFE-003a fully closed:

1. accept `daemon-down-full` as the canonical iai 3.0.8 provenance for the full daemon-independent direct-store recall path and update Orion acceptance wording accordingly; or
2. if the literal `direct-store` string is semantically required by an external consumer, document that requirement and consider a minimal compatibility translation at the Orion boundary rather than modifying iai retrieval semantics.

Do not rerun Test B; the second HIBERNATION cycle already produced sufficient runtime evidence.
