# OR-LIFE-005 v2.7.4 Gate 2I — Interrupted Start Same-Boot Recovery Barrier

Date: 2026-09-09
Branch: `feature/orion-start-v272-lifecycle-safety`
Candidate workspace: `C:\Users\spill\Downloads\Orion-v274-gate1-20260908-053419`
Disposition: **PASS**

## Purpose

Validate that the v2.7.4 lifecycle candidate fails closed when a structurally valid same-boot `start` operation is left `inFlight:true`, preserving the recovery record and blocking both new Start and Stop mutation until recovery can be resolved across a Windows boot boundary.

This gate intentionally used a synthetic control record only. It did not start Hermes, start Ollama, perform inference, or alter the accepted Hermes installation.

## Clean-off precondition

Observed before injection:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

## Injected interrupted Start state

The harness created a schema-4 operation record accepted by the candidate protocol with:

- `action: start`
- `inFlight: true`
- `ollama: null`
- current Windows boot identity
- no error marker

Validation output:

- `Protocol record valid: True`
- `Action: start`
- `InFlight: True`
- `Ollama ownership present: False`
- `Boot matches current: True`

## Candidate Start behavior

Attempting candidate Start while the same-boot operation remained unresolved produced:

- `ORION ACTION FAILED. Recovery records were preserved.`
- `Code: USE_STOP_OR_RECOVERY_FIRST`
- exit code: 1

Post-Start verification:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- launcher session: absent
- recovery record: preserved

The candidate therefore refused new Start mutation without runtime/session side effects.

## Candidate Stop behavior

Attempting candidate Stop against the same unresolved same-boot record produced:

- `ORION ACTION FAILED. Recovery records were preserved.`
- `Code: COMMAND_COMPLETION_UNRESOLVED_RESTART_REQUIRED`
- exit code: 1

Post-Stop verification:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- launcher session: absent
- recovery record: preserved

The candidate therefore did not silently clear uncertain command-completion evidence or reinterpret the unresolved operation as safe on the same boot.

## Test-only cleanup

After both fail-closed assertions passed, the harness removed only the synthetic `active-operation.json` record that the test itself had injected.

No real runtime process, vendor task, Hermes source, Orion configuration, model state, or unrelated lifecycle evidence was modified.

## Final clean-off verification

Observed after removal of the test-created recovery record:

- Hermes health: false
- Ollama health: false
- Ollama process count: 0
- `launcher-session.json`: absent
- `active-operation.json`: absent

Final state: **clean-off**.

## Acceptance result

**GATE 2I PASS**

The v2.7.4 candidate enforces a durable same-boot interrupted-Start recovery barrier. New Start was refused with `USE_STOP_OR_RECOVERY_FIRST`; Stop was refused with `COMMAND_COMPLETION_UNRESOLVED_RESTART_REQUIRED`; the active-operation evidence remained durable through both attempts; no runtime or ownership/session state was created; and the machine returned to clean-off after removal of only the test-injected recovery record.

This strengthens OR-LIFE-005 / OR-LIFE-010 evidence for bounded recovery semantics and prevents an uncertain in-flight lifecycle command from being silently bypassed on the same Windows boot.
