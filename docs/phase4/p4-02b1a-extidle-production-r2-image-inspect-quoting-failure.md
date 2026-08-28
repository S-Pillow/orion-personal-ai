# P4-02B1A — External Idle Production Deploy r2 Image Inspect Quoting Failure

**Status: HARNESS FAILURE — production core unchanged**

Date: 2026-08-28 UTC

## Summary

The r2 production deploy harness passed parser/hash gates, production immutable preflight, and durable-store fingerprinting. It then successfully built the local/no-network external-idle candidate image, but failed while verifying the image provenance label.

Observed fatal marker:

```text
P4_02B1A_PROD_FATAL=inspect external-idle candidate image failed with exit 64: template parsing error: template: :1: function "org" not defined
```

The failing command used a Docker Go-template argument containing an embedded quoted label name:

```text
{{index .Config.Labels "org.orion.p4.extidle.head"}}
```

Under Windows PowerShell native argument transport, the embedded quotes were not preserved as intended, so Docker parsed `org.orion...` as a template function token.

## What completed

- accepted production core/gateway immutable preflight passed;
- durable fingerprint preflight passed using the corrected `hippo/brain.sqlite3` location;
- exact iai candidate source was extracted;
- local candidate image build completed with `--network none`;
- candidate image tag: `orion-hermes-iai:v2026.8.18-iai3.0.8-m5-extidle-b6d356e`;
- overlay application inside the image reported PASS.

## What did not occur

The failure happened before the host-idle bridge was started and before the production mutation boundary.

No production core stop, rename, recreate, daemon stop/start, persistent-volume replacement, lifecycle-state edit, threshold change, gateway mutation, or Brain deploy occurred.

The rollback phase therefore only performed host-bridge cleanup/no-op handling and completed successfully.

Retained local evidence:

`E:\Orion-Phase2\P4-02B1A-evidence\p4-02b1a-extidle-production-deploy-20260828T014632Z`

## Correction

The next harness revision removes Docker Go-template label lookup entirely for candidate-image verification. It uses full `docker image inspect` JSON and PowerShell `ConvertFrom-Json`, then reads the exact label through the parsed object. This avoids another quoted native-argv boundary.

The already-built candidate image may be reused only if its parsed JSON label `org.orion.p4.extidle.head` exactly matches candidate head `b6d356e67526ed30cc3e7a466597992fc440b800`.

P4-02B1A remains **IN PROGRESS**.
