# OR-LIFE-005 v2.7.4 Candidate Gate 2F — Independent Runtime Ownership

Date: 2026-09-08
Candidate: `Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip`
Hermes pin: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

## Result

PASS.

## Evidence

- Clean-off precondition: Hermes API false, Ollama API false, zero Ollama processes, no launcher session, no active operation.
- Test started an independent Ollama `serve` process (PID 26840) and verified its exact start FILETIME.
- Existing vendor Scheduled Task started Hermes independently and Hermes became healthy.
- Candidate Start over already-healthy Hermes/Ollama returned `ORION READY`.
- Strict candidate session check reported schema 4, same boot true, `ollamaOwnershipRecorded: false`.
- Candidate Stop reported `Ollama ownership not recorded; independent processes left alone.` and `ORION STOPPED; iai remains vendor-managed.`
- After candidate Stop: Hermes unhealthy/off; independent Ollama remained healthy.
- Exact independent Ollama PID, image path, and start FILETIME were unchanged.
- Test cleanup terminated only that exact test-owned independent Ollama process.
- Final state: Ollama API false, zero Ollama processes, no launcher session, no active operation.

## Acceptance meaning

This validates the native ownership boundary that earlier rejected launcher revisions did not adequately prove: Orion does not claim or stop a healthy Ollama process it did not launch, while explicit operator Stop retains authority to stop the COMPANION Hermes profile.

## Remaining Gate 2 work

Gate 2 is not yet fully complete. Remaining candidate acceptance items include unhealthy/contradictory Hermes refusal, race/failure-path behavior, durable in-flight blocking, failed shutdown preservation, stored-identity refusal cases, and real-Restart recovery behavior. These should be covered with isolated/native fault harnesses or tightly controlled recovery tests rather than by destabilizing the accepted production Hermes installation unnecessarily.

Core Intent Preservation: PRESERVED.
