# OR-LIFE-005 v2.7.4 Gate 2G — Corrupted Control State Fail-Closed Validation

Date: 2026-09-08
Branch: `feature/orion-start-v272-lifecycle-safety`
Candidate workspace: `C:\Users\spill\Downloads\Orion-v274-gate1-20260908-053419`
Disposition: **PASS**

## Purpose

Validate that the v2.7.4 Start Orion candidate fails closed when Orion control-state metadata is corrupted, without starting Hermes, starting Ollama, creating a launcher session, or bypassing the preserved recovery record.

This test was intentionally low-risk and did not perform model inference or mutate the accepted Hermes installation.

## Clean-off precondition

Observed before fault injection:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

## Fault injection

The test created only:

`%LOCALAPPDATA%\Orion\operator\active-operation.json`

with deliberately invalid JSON content.

## Candidate behavior

Running candidate `Start-Orion.ps1` produced:

- `ORION ACTION FAILED. Recovery records were preserved.`
- `Code: UNEXPECTED_ERROR`
- `Do not delete active-operation.json or ownership files to bypass a block.`
- process exit code: 1

The injected corrupted operation record remained present after the refusal.

## Fail-closed verification

After candidate refusal:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- launcher session: absent
- injected operation record: still present

Therefore the candidate did not start a runtime, did not create a new ownership/session record, and did not silently discard the corrupted recovery/control record.

## Test-only cleanup

The harness removed only the fault file it created.

No vendor runtime, Scheduled Task, Hermes source, profile configuration, model state, or unrelated Orion evidence was changed.

## Final clean-off verification

Observed after removal of the test-created fault file:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

Final state: **clean-off**.

## Acceptance result

**GATE 2G PASS**

The v2.7.4 candidate fails closed on corrupted active-operation state, preserves the recovery record rather than bypassing it, creates no launcher session, starts neither Hermes nor Ollama, and returns to the Gate 2F clean-off baseline after removal of only the test-injected file.

This strengthens OR-LIFE-005 / OR-LIFE-010 evidence for bounded one-shot lifecycle control and recovery-state integrity.
