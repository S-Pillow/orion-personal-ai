# OR-LIFE-005 Orion Operator Controls v2.7.4-candidate1 Static Review — 2026-09-08

Status: **ACCEPT FOR NATIVE WINDOWS VALIDATION / NOT YET DEPLOYMENT-ACCEPTED**

Candidate artifact reviewed: `Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip`

Artifact SHA-256:
`fd2268aa79883dae2f0fa2b3371de022c3e54be72c85a566be01c893f79d54be`

## Independent checks completed

- Extracted and reviewed all package source, tests, installer, recovery controls, and validation instructions.
- Verified the package's `SHA256SUMS.txt` against every listed file: all entries matched.
- Re-ran `python -m unittest discover -s tests -v`: **27/27 passed**.
- Ran Python bytecode compilation for controller, protocol, Windows process helper, worker, installer, and tests: passed.
- Confirmed there is no Orion supervisor/service/Scheduled Task creation path in the candidate.
- Confirmed automatic Start failure does not issue profile-wide Hermes rollback or automatic Ollama termination.
- Confirmed lifecycle command uncertainty remains durable via `active-operation.json` with `inFlight:true` and requires a changed Windows boot identity before recovery.
- Confirmed explicit Stop is the only profile-wide Hermes stop authority and owned Ollama cleanup is identity-constrained using PID + exact process creation FILETIME + executable image identity.
- Confirmed malformed/legacy/future active metadata is preserved and blocks mutation rather than being overwritten.
- Confirmed versioned publication is staged before shortcut creation and published source is retained after post-publication installer failure.
- Confirmed raw vendor stdout/stderr and command lines are not persisted into Orion lifecycle records.

## Pinned Hermes contract checked

Pinned Hermes tag/commit remains:
- tag `v2026.8.27`
- package `0.20.6`
- commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

The candidate binds one-shot workers to the pinned Windows lifecycle module, asserts COMPANION home/task identity, and vetoes vendor install during Start. This preserves manual-off intent and avoids adding a second gateway or supervisor.

## Static-review disposition

No static issue found that violates the candidate's mandatory safety boundaries strongly enough to block **native validation**. This is not production acceptance. The candidate itself correctly requires Windows-native gates for PowerShell 5.1, CPython handle semantics, boot identifier behavior, pinned runtime imports, actual Hermes/Ollama lifecycle behavior, migration/install failure injection, and operator smoke.

One explicit trust boundary is retained: `orion-config.json` is operator-authored local configuration and its Python path is used by the thin PowerShell bootstrap before Python performs strict duplicate-key/schema validation. For this single-user local operator tool, the candidate is accepted for validation only when that file is created from read-only discovery and reviewed before use; arbitrary same-user config tampering is outside the stated isolation boundary.

Core Intent Preservation: **PRESERVED**.
