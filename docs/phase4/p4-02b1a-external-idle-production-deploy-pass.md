# P4-02B1A — External Host-Idle Production Candidate Deployment

**Status: PASS — production candidate wired; autonomous lifecycle acceptance still pending**

Date: 2026-08-28 UTC

## Accepted production deployment

The bounded r5 deployment completed successfully after the host-idle producer was hardened for Windows PowerShell 5.1 process/evidence provenance and atomic replacement behavior.

Accepted markers included:

```text
P4_02B1A_PROD_HOST_IDLE_SAMPLE1=seq=1|idle_sec=5|age=0.049
P4_02B1A_PROD_HOST_IDLE_SAMPLE2=seq=2|idle_sec=0|age=0.031
P4_02B1A_PROD_HOST_IDLE_TWO_SAMPLE_PROVENANCE=PASS
P4_02B1A_PROD_HOST_IDLE_BRIDGE=PASS
DISPOSABLE_PACKAGED_CANDIDATE=PASS
P4_02B1A_PROD_PREFLIGHT_AND_BUILD=PASS
P4_02B1A_PROD_MUTATION_BOUNDARY=BEGIN
P4_02B1A_PROD_CANDIDATE_DAEMON=PASS
P4_02B1A_PROD_GATEWAY_STATE_PRESERVED=PASS
P4_02B1A_PROD_EXTERNAL_IDLE_VISIBLE=PASS
P4_02B1A_PROD_DURABLE_STATE_PRESERVED=PASS
P4_02B1A_PROD_CORE_SECURITY_TOPOLOGY=PASS
COMPANION_API_READY=YES
COMPANION_FRESH_WRAPPER_COUNT=1
COMPANION_RUNTIME_READY=PASS
P4_02B1A_PROD_HERMES_API_LISTENER=PASS
P4_02B1A_PROD_FRESH_IAI_WRAPPER=PASS
P4_02B1A_PROD_COMPANION_RUNTIME_READY=PASS
P4_02B1A_PROD_BRAIN_HTTP=PASS
P4_02B1A_PROD_DASHBOARD_UNCHANGED=PASS
P4_02B1A_PROD_THRESHOLD_OVERRIDES=NONE
P4_02B1A_PROD_DROWSY_DEFAULT_SEC=300
P4_02B1A_PROD_SLEEP_IDLE_DEFAULT_SEC=1800
P4_02B1A_PROD_SLEEP_COOLDOWN_DEFAULT_SEC=14400
P4_02B1A_PROD_EXTERNAL_IDLE_DEPLOY=PASS
P4_02B1A_PROD_READY_FOR_AUTONOMOUS_OBSERVER=PASS
```

## Production identity

- active core container: `orion-iai-m5-c`
- active core ID: `86f1b8fb97532d791c529a9e6654a43e9c04245fb44d7c00678b2fc0a5509375`
- active core StartedAt: `2026-08-28T02:23:56.327999714Z`
- candidate image ID: `sha256:db651747ed9e785fa839470d06535e37134a858e2d16077106f77ba6bd2d1517`
- iai candidate source head: `b6d356e67526ed30cc3e7a466597992fc440b800`
- host bridge feature head: `ad4bde10362ac6fa93420a9ad692610a0a14ff03`
- host bridge producer instance at deployment: `433f1759-6293-48e6-b5fb-1d7a7e39f6cf`
- host bridge PID at deployment: `30372`
- retained rollback container: `orion-iai-m5-c-pre-extidle-20260828t022325z`

Retained evidence:

`E:\Orion-Phase2\P4-02B1A-evidence\p4-02b1a-extidle-production-deploy-20260828T022325Z`

Summary:

`E:\Orion-Phase2\P4-02B1A-evidence\p4-02b1a-extidle-production-deploy-20260828T022325Z\production-deploy-summary.json`

## Safety and semantic boundary

- existing `orion-iai-m5-data` persistent volume preserved;
- durable `hippo/brain.sqlite3` byte size preserved across recreation;
- accepted capability/security/network topology preserved;
- default gateway remained down and companion gateway remained up;
- Brain dashboard sidecar unchanged;
- no iai lifecycle thresholds changed;
- no manual lifecycle-state edits;
- external host-idle evidence is visible through iai's existing `IdleDetector` boundary;
- fresh wrapper recovery was explicitly verified before acceptance;
- no Docker socket or new network listener was introduced.

## Host-idle producer hardening accepted in this run

The producer/consumer startup handshake now rejects evidence from prior runs and requires two samples from the exact child process started by the deployment harness. Identity uses producer instance UUID + PID + process start time + sequence rather than freshness alone.

The bridge's Windows PowerShell 5.1 atomic replacement path no longer passes `$null` through PowerShell method binding as the `File.Replace` backup argument. It uses a unique same-directory backup path, then removes that backup after the atomic replacement. The first observation is fail-fast; later transient failures are allowed to become stale so iai fails closed naturally.

## Remaining acceptance gate

P4-02B1A remains **IN PROGRESS**. Deployment success does not close autonomous lifecycle acceptance.

The next read-only production observation must capture authoritative native iai evidence for:

1. `WAKE -> DROWSY` on the native idle-5-minute path;
2. `DROWSY -> SLEEP` on native idle-30-minute plus sleep eligibility;
3. `SLEEP -> HIBERNATION` after the native sleep cycle completes while host idle remains valid;
4. a separate genuine foreground/Hermes memory request that returns the lifecycle to `WAKE` without Brain control clicks.

No accelerated production thresholds are authorized for this acceptance.
