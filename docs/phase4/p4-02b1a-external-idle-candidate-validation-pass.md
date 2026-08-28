# P4-02B1A — External Host-Idle Candidate Validation

**Status: PASS — disposable candidate boundary accepted**

Date: 2026-08-28 UTC

## Scope

This record captures the disposable/no-network validation of the external host-idle compatibility seam proposed for Orion's Windows-hosted Docker deployment of iai 3.0.8.

The validation did not edit iai lifecycle state, change production thresholds, restart or recreate the accepted production core, or make external network calls.

## Candidate identity

- iai fork branch: `compat/orion-external-idle-signal`
- exact candidate head: `b6d356e67526ed30cc3e7a466597992fc440b800`
- candidate behavior: opt-in `IAI_MCP_EXTERNAL_IDLE_PATH` evidence consumed at iai's existing `IdleDetector` boundary
- native lifecycle policy/thresholds: unchanged

## Accepted run

Command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "E:\Orion-Phase2\Orion-Phase4-P4-02B1A-External-Idle-Candidate-Validation.ps1"
```

Observed acceptance markers:

```text
P4_02B1A_EXTIDLE_CORE_PREFLIGHT=PASS
P4_02B1A_EXTIDLE_IMAGE_ID=PASS
P4_02B1A_EXTIDLE_CANDIDATE_HEAD=b6d356e67526ed30cc3e7a466597992fc440b800
P4_02B1A_EXTIDLE_CANDIDATE_EXTRACT=PASS
P4_02B1A_EXTIDLE_HOST_IDLE_SEC=0
P4_02B1A_EXTIDLE_HOST_EVIDENCE=PASS
P4PROBE_EXTERNAL_SOURCE=external_idle_file
P4PROBE_EXTERNAL_IDLE_SEC=0
P4PROBE_NATIVE_1800_THRESHOLD=PASS
P4PROBE_FAIL_CLOSED_CASES=PASS
P4PROBE_EXTERNAL_IDLE_CANDIDATE=PASS
P4_02B1A_EXTIDLE_CORE_UNCHANGED=PASS
P4_02B1A_EXTIDLE_DISPOSABLE_VALIDATION=PASS
P4_02B1A_EXTIDLE=PASS
```

Retained local evidence:

`E:\Orion-Phase2\P4-02B1A-evidence\p4-02b1a-external-idle-candidate-20260828T004656Z`

The initial host observation was `idle_sec=0` because the operator had just interacted with Windows to launch the harness. That is useful acceptance evidence: zero is treated as valid **active** host evidence rather than being rejected or misclassified as idle.

The same run proved the exact candidate accepts the fresh host observation, preserves iai's native 1800-second sleep-eligibility boundary, rejects the bounded stale/future/malformed/invalid evidence cases, and leaves the accepted production core container unchanged.

## Production mount-topology correction

The prior compatibility-design text proposed writing on the Windows host under:

`C:\HermesAgent\data\orion-runtime\host-idle.json`

and consuming the same file at:

`/opt/data/orion-runtime/host-idle.json`.

That container path is **superseded for the accepted P4 production core**.

The current `orion-iai-m5-c` runtime does not obtain `/opt/data` from the Windows `C:\HermesAgent\data` bind. Its authoritative persistent data boundary is the Docker named volume:

`orion-iai-m5-data -> /opt/data`

Production wiring must therefore preserve that named volume and add a separate, narrow, read-only bind for the host-idle evidence:

```text
host:      C:\HermesAgent\data\orion-runtime\host-idle.json
container: /orion-host-idle/host-idle.json
mode:      read-only in container
```

The intended daemon setting becomes:

```text
IAI_MCP_EXTERNAL_IDLE_PATH=/orion-host-idle/host-idle.json
```

This correction avoids replacing or aliasing the accepted `/opt/data` volume and does not grant the container new write authority over the host-idle directory.

## Next gate

The disposable candidate gate is complete. The next bounded unit is production candidate packaging and wiring:

1. build a child image from the accepted serializer-fix image with only the candidate `idle_detector.py` overlay;
2. start the Windows idle producer;
3. prove the packaged image consumes the real host observation in a network-disabled disposable run;
4. recreate only `orion-iai-m5-c` on the same `orion-iai-m5-data` volume with the additional read-only `/orion-host-idle` bind;
5. preserve the accepted capability/security/network and gateway-state boundaries;
6. retain the stopped original core container as rollback until autonomous lifecycle acceptance is complete;
7. start iai with normal production thresholds plus only `IAI_MCP_EXTERNAL_IDLE_PATH`;
8. verify durable state, Brain, and the internal Hermes API path before beginning autonomous observation.

P4-02B1A remains **IN PROGRESS**. Final closure still requires authoritative production `WAKE -> DROWSY -> SLEEP -> HIBERNATION` evidence and a separate foreground-activity return to `WAKE`.
