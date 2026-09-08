# OR-LIFE-005 v2.7.4 Gate 1D — 2026-09-08

Status: **PARTIAL PASS / PREFLIGHT BLOCKED**

Candidate: `Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip`
Candidate SHA-256: `fd2268aa79883dae2f0fa2b3371de022c3e54be72c85a566be01c893f79d54be`

## Passed

- Hermes runtime Python resolved to `C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe`.
- Python version: 3.11.3.
- Offline candidate safety suite: 27 tests passed.
- Native Windows primitive checks passed:
  - original-handle retention / mismatch refusal / exact-handle termination;
  - cross-process canonical lifecycle-lock exclusion.
- Primitive test explicitly reported no Hermes/Ollama import, start, or stop.
- Exact local candidate config was created in the extracted review directory with expected Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`.

## Block

Read-only `Test-Orion-Preflight.ps1` stopped with:

`HERMES_CHECKOUT_NOT_CLEAN`

No reset, clean, checkout, stash, or other mutation is authorized. The dirty checkout must first be classified read-only because accepted Phase 1 work may include intentional local Windows compatibility modifications.

The trailing interactive `GATE 1D COMPLETE` banner is not treated as authoritative because the pasted PowerShell block continued accepting later commands after the explicit thrown preflight failure. The preflight error is the controlling outcome.

## Next evidence unit

Read-only Git inspection only:
- confirm HEAD;
- list working-tree / index / untracked paths;
- inspect diff stats and names without mutating the checkout;
- compare findings against accepted Windows compatibility fixes before deciding whether candidate clean-checkout policy must be adjusted or the checkout itself is unexpectedly dirty.

Core Intent Preservation: **PRESERVED**.
