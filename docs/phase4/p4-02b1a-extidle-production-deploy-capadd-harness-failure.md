# P4-02B1A — External Idle Production Deploy CapAdd Harness Failure

**Status: HARNESS-ONLY FAILURE / NO PRODUCTION MUTATION**

Date: 2026-08-28 UTC

## Attempt

The first bounded external-idle production deployment harness passed its parser and SHA-256 gate, then stopped during production preflight with:

```text
P4_02B1A_PROD_FATAL=Accepted core CapAdd drift: CAP_CHOWN,CAP_DAC_OVERRIDE,CAP_FOWNER,CAP_KILL,CAP_SETGID,CAP_SETUID
P4_02B1A_PROD_ROLLBACK=BEGIN
P4_02B1A_PROD_ROLLBACK_HOST_BRIDGE=PASS
P4_02B1A_PROD_ROLLBACK=PASS
P4_02B1A_PROD_EXTERNAL_IDLE_DEPLOY=FAIL
```

Evidence directory:

`E:\Orion-Phase2\P4-02B1A-evidence\p4-02b1a-extidle-production-deploy-20260828T010608Z`

## Root cause

The accepted core capability set was correct. Docker inspect returned canonical capability names with the `CAP_` prefix:

```text
CAP_CHOWN
CAP_DAC_OVERRIDE
CAP_FOWNER
CAP_KILL
CAP_SETGID
CAP_SETUID
```

The harness incorrectly compared those values against the unprefixed strings `CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `KILL`, `SETGID`, and `SETUID`.

The candidate `docker run` arguments already used the intended equivalent capability additions and no security policy change was required.

## Safety disposition

The failure occurred in the immutable preflight section before candidate build/deploy, accepted-core stop/rename, container recreation, daemon stop, lifecycle control, or iai data mutation.

The rollback block had only the host-bridge cleanup path to perform and reported PASS.

Therefore:

- accepted `orion-iai-m5-c` remained running and unchanged;
- accepted container ID/StartedAt remained the pre-deployment baseline;
- `orion-iai-m5-data` was not modified by deployment logic;
- no production threshold or lifecycle-state change occurred;
- no production candidate container was started.

## Repair

The repaired harness changes only the pre/post expected Docker inspect capability names to the canonical `CAP_*` form. No deployment behavior, security boundary, capability set, mount, network, threshold, or iai source is changed by this harness repair.
