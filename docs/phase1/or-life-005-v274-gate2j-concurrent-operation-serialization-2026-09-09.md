# OR-LIFE-005 v2.7.4 Gate 2J — Concurrent Operation Serialization

Date: 2026-09-09
Branch: `feature/orion-start-v272-lifecycle-safety`
Candidate workspace: `C:\Users\spill\Downloads\Orion-v274-gate1-20260908-053419`
Disposition: **PASS WITH HARNESS OBSERVATION NOTE**

## Purpose

Validate that concurrent lifecycle-operation ownership acquisition serializes through the candidate's exclusive `active-operation.json` write primitive, producing exactly one surviving operation record and forcing the competing writer to fail closed.

The test intentionally avoided starting Hermes or Ollama and exercised the candidate protocol/write primitive directly to make the concurrency outcome deterministic.

## Clean-off precondition

Observed before the race:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

## Concurrent acquisition race

Two independent Python worker processes were synchronized to attempt `protocol.write(..., exclusive=True)` against the same `%LOCALAPPDATA%\Orion\operator\active-operation.json` path.

Each worker prepared a valid schema-4 `inspect` operation record with `inFlight:true`, current boot identity, and no Ollama ownership.

Observed race result:

- Worker A: `WINNER`
- Worker A record id: `ae8f6eb0946f78ee3591e4bbd9764bbc`
- Worker B: `LOSER`
- Worker B exception: `FileExistsError`
- exactly one `active-operation.json` existed after the race

This shows the candidate exclusive-write primitive admitted one writer and rejected the competing writer.

## Harness observation defect

The first harness attempted to count winners and losers from `$pA.ExitCode` / `$pB.ExitCode` after `Start-Process`. On this Windows PowerShell invocation those ExitCode properties were blank, so the harness incorrectly computed `Winner count: 0` and `Loser count: 0` and emitted `GATE 2J FAIL`.

That was a harness-observation defect, not a concurrency/serialization failure. The workers' own stdout already showed one winner and one `FileExistsError` loser, and the winning operation record remained available for independent salvage verification.

No rerun of the race was required because the surviving record could be tied exactly to the observed winning worker.

## Salvage verification

A bounded follow-up probe validated the single surviving `active-operation.json` through the candidate protocol and required an exact match to Worker A's printed ID before allowing cleanup.

Observed:

- protocol record valid: true
- ID: `ae8f6eb0946f78ee3591e4bbd9764bbc`
- expected ID: `ae8f6eb0946f78ee3591e4bbd9764bbc`
- ID matches winner: true
- action: `inspect`
- `inFlight`: true
- error: empty string
- Ollama ownership present: false
- boot matches current: true
- validation exit: 0

Therefore the single surviving record was proven to be exactly Worker A's valid winning record rather than unrelated state.

## Runtime side-effect verification

Before removing the test-created winner record:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- launcher session: absent

No runtime or launcher-session side effect occurred.

## Test-only cleanup

After exact winner-record verification, the harness removed only the synthetic Gate 2J `active-operation.json` record.

No real Hermes/Ollama lifecycle operation, vendor Scheduled Task change, configuration change, or unrelated Orion evidence modification was performed.

## Final clean-off verification

Observed after cleanup:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

Final state: **clean-off**.

## Acceptance result

**GATE 2J PASS WITH HARNESS OBSERVATION NOTE**

The candidate's exclusive active-operation acquisition serialized concurrent writers correctly: one worker created the operation record and the competing writer failed closed with `FileExistsError`. The surviving record was independently verified to match the winning worker exactly. No runtime/session side effects occurred and clean-off was restored.

The original harness's blank PowerShell `Start-Process` ExitCode properties are recorded as a test-harness observation defect only; they do not invalidate the underlying serialization evidence.
