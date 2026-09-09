# OR-LIFE-005 — v2.7.4 candidate Gate 2E candidate Stop validation

Date: 2026-09-08
Branch: feature/orion-start-v272-lifecycle-safety
Candidate: Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip

## Result
PASS.

The candidate Stop was run against the same successful Gate 2B/2D session.

Observed preconditions:
- Hermes API healthy: true
- Ollama API healthy: true
- candidate launcher-session.json present
- active-operation.json absent

Candidate Stop output:
- `Owned Ollama: stopped`
- `ORION STOPPED; iai remains vendor-managed.`
- exit code 0
- elapsed time 7.8 seconds

Post-stop verification:
- Hermes API healthy: false
- Ollama API healthy: false
- Ollama process count: 0
- launcher-session.json absent
- active-operation.json absent
- Hermes task state Ready
- Hermes enabled LogonTriggers: 0
- iai task state Running
- iai enabled LogonTriggers: 0
- iai wrapper-like node count after 5 seconds: 0
- Hermes source dirty entry count: 0

Interpretation:
- profile-wide Hermes shutdown completed and was verified before provider cleanup
- exact candidate-owned Ollama cleanup completed
- lifecycle records were archived/removed from the active paths
- manual-off task configuration remained preserved
- iai remained vendor-managed; daemon state was observational and not commandeered by Orion
- no Hermes source mutation occurred

Core Intent Preservation: PRESERVED.

This completes the clean-off Start -> inference/Discord/memory -> Stop lifecycle path for the candidate, but does not by itself complete all remaining Gate 2 failure/independent-runtime scenarios or Gate 3 installation/restart workflow acceptance.
