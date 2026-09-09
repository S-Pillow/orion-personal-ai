# OR-LIFE-005 v2.7.4 Gate 2H — Stale Process Identity Ownership Validation

Date: 2026-09-09
Branch: `feature/orion-start-v272-lifecycle-safety`
Candidate workspace: `C:\Users\spill\Downloads\Orion-v274-gate1-20260908-053419`
Disposition: **PASS**

## Purpose

Validate that the v2.7.4 Stop Orion candidate does not terminate a process based on PID alone when the stored ownership identity has a mismatched process creation FILETIME.

This directly exercises the candidate safety contract that owned Ollama cleanup is identity-constrained by PID + exact process creation FILETIME + executable image identity.

## Clean-off precondition

Observed before test setup:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

## Synthetic process setup

The harness copied Windows `ping.exe` to a temporary path named `ollama.exe` and started that test-created process only.

Observed synthetic identity:

- PID: 35452
- image path: `C:\Users\spill\AppData\Local\Temp\Orion-Gate2H-6686f3c2298644a4a3113383a03e4177\ollama.exe`
- process running: true

No real Ollama runtime was started.

## Forged ownership session

The harness captured the actual synthetic process identity through the candidate `win_process.Process.identity()` implementation, then created a structurally valid schema-4 launcher session with:

- same PID
- same executable image identity
- deliberately different process creation FILETIME (`created` value changed by one)
- current Windows boot identity

Candidate protocol validation succeeded:

- `Protocol record valid: True`
- PID equal: true
- image equal: true
- creation time equal: false
- `win_process.same(actual, forged)`: false

This was therefore a valid stale ownership record rather than malformed metadata.

## Candidate Stop behavior

Running candidate `Stop-Orion.ps1` produced:

- `Owned Ollama: different`
- `ORION STOPPED; iai remains vendor-managed.`
- exit code: 0

The candidate treated the stored ownership identity as referring to a different process instance and did not terminate the live synthetic process.

## Critical verification

After candidate Stop:

- synthetic process survived: true
- same PID still present: true
- same process start time: true
- launcher session: absent
- active operation: absent

The stale ownership session therefore did not authorize termination.

## Test-only cleanup

After the safety assertion passed, the harness:

1. confirmed the forged launcher session had already been removed by candidate Stop;
2. terminated only the temporary synthetic process created by the harness;
3. removed only the test-created temporary files.

No Hermes source, vendor Scheduled Task, Orion configuration, real Ollama runtime, model state, or unrelated lifecycle evidence was modified.

## Final clean-off verification

Observed after test cleanup:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

Final state: **clean-off**.

## Acceptance result

**GATE 2H PASS**

The v2.7.4 candidate did not authorize process termination from PID alone. Exact process creation identity remained enforced, and a stale ownership record targeting a live same-PID/same-image but different-creation process was classified as `different` and left untouched.

This strengthens OR-LIFE-010 evidence that Stop Orion only stops Ollama when Orion's recorded ownership identity still matches the actual process instance.
