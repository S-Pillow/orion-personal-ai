# P4-02B1A v5 — manual Brain control smoke harness failure

Date: 2026-08-27

Status: **HARNESS FAILURE — NO BRAIN CONTROL REQUEST SENT**

## Observed boundary

The v5 manual-control smoke started and passed its local tool check, then failed during the first Docker preflight while reading `orion-iai-m5-c` metadata:

`Unexpected docker inspect output for orion-iai-m5-c: e`

The failure occurred before the Brain dashboard HTTP preflight, before lifecycle-state observation, and before any POST to `/api/daemon`. No `sleep`, `wake`, `consolidate`, `restart`, or `stop` control request was sent.

## Diagnosis

The harness used `(Invoke-Native ...)[0]` on a function whose single-item output is unrolled by Windows PowerShell into a scalar string. Indexing `[0]` therefore selected the first character of the container ID (`e`) instead of the first output line.

The same scalar-unrolling risk also exists in the lifecycle helper where the result of `Invoke-Native` is later indexed with `[-1]`.

## Minimum correction

Wrap both call sites with the array subexpression operator so the results remain arrays even when there is exactly one output line:

- Docker inspect: `$lines = @(Invoke-Native ...)`, then `$line = [string]$lines[0]`.
- Lifecycle helper: `$out = @(Invoke-Native ...)`, then use `$out[-1]`.

Do not change the Brain control sequence, runtime, deployed iai source, or container lifecycle for this correction.

## Safety disposition

This attempt did not touch iai memory semantics or runtime state and did not restart either the accepted core container or Brain dashboard container. P4-02B1A remains in progress at the manual control-smoke step.
