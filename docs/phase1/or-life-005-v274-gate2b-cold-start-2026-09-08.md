# OR-LIFE-005 — v2.7.4 candidate1 Gate 2B controlled cold start

Date: 2026-09-08
Package: Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip
Status: START FUNCTIONAL PASS; PERFORMANCE FOLLOW-UP REQUIRED

## Preconditions
- Hermes API unhealthy/off before start.
- Ollama API unhealthy/off before start.
- Ollama process count 0.
- Hermes source HEAD exactly `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`.
- Hermes checkout clean.
- Hermes and iai Scheduled Tasks retained with LogonTriggers disabled.

## Candidate start result
- Candidate `Start-Orion.ps1` returned `ORION READY`.
- Exit code: 0.
- Elapsed: 17.5 seconds.
- Hermes API healthy after start: true.
- Ollama API healthy after start: true.
- `launcher-session.json` exists.
- `active-operation.json` absent after successful completion.
- Hermes source remained clean.
- Hermes task remained Ready with zero enabled LogonTriggers.
- iai task was Running with zero enabled LogonTriggers, consistent with vendor on-demand wake.

## Resource telemetry
Temporary observer sampled 19 times during start + post-ready hold.
- Minimum reported free physical RAM: 264 MB.
- Maximum Ollama working set: 480 MB.
- Maximum Python working set: 420 MB.

This is a strong memory-pressure signal and requires follow-up before treating the earlier severe system slowdown as resolved. Working-set totals alone do not explain total system pressure; capture current Windows memory/commit/pagefile and model placement before further heavy validation.

## Disposition
Gate 2B start behavior: PASS.
Performance/resource acceptance: NOT YET CLOSED.
Keep candidate runtime under controlled validation; do not install desktop shortcuts yet.
