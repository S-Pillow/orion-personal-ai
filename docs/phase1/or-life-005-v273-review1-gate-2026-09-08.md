# OR-LIFE-005 v2.7.3-review1 Review Gate — 2026-09-08

Status: **REVIEW ONLY / DO NOT INSTALL**

A new Orion operator-control candidate was prepared after the v2.7.2 adversarial review returned DO NOT ACCEPT.

## Package

- File: `Orion-Operator-Controls-v2.7.3-review1-REVIEW.zip`
- SHA-256: `cc890cb0f8d59f25ae89dba96240e68564299cd1b6b81b92ca3a591a2c647699`
- Contents: `Start-Orion.ps1`, `Stop-Orion.ps1`, `Orion-Lifecycle.Common.ps1`, immutable-version installer, cold-start observer, README, and adversarial review request.

The package is not installed and is not approved for deployment.

## Design disposition after v2.7.2 review

- Automatic Start-failure handling no longer has authority to invoke profile-wide Hermes stop.
- Explicit `Stop Orion` remains the operator-authorized profile-wide stop for Hermes profile `companion`; this is intentionally broader than automatic rollback.
- Hermes start/status/stop lifecycle commands use bounded invocation and fail-closed quarantine semantics when command completion cannot be verified.
- A fail-closed quarantine marker is written before detailed quarantine JSON so a detailed-metadata write failure does not silently permit the next lifecycle run.
- Ollama cleanup is constrained to exact process identity using PID, process name, executable path, and exact process creation FILETIME; no PID/name-only cleanup is permitted.
- Session and Start-failure metadata use exact schema validation; malformed/future ownership state is preserved rather than overwritten.
- Start refuses to proceed while unresolved prior Stop-failure metadata exists.
- Installer uses the canonical lifecycle lock/state root, publishes immutable version directories, temporarily removes old desktop shortcuts and legacy mutable root Start/Stop scripts from invocation paths, repeats overlap/runtime checks, and restores old entry points if installation fails.
- Raw command lines and vendor stdout/stderr are not persisted to lifecycle JSON/JSONL. Command-line inspection is transient only for lifecycle-command classification.
- No supervisor, resident watcher, new service, or new Scheduled Task is introduced.

## Repository safety

The feature branch `feature/orion-start-v272-lifecycle-safety` was reset back to the current accepted main commit before this review package was handed off. This avoids leaving a partial review candidate in GitHub. Candidate source should be committed only after static review is accepted or after the next revision is ready as a complete coherent set.

## Runtime state

The production PC remains in the previously verified manual-off state. OR-LIFE-005 remains paused at post-reboot cold-start recovery. No additional Start Orion attempt should be run until the candidate passes review and an instrumented cold-start test is explicitly prepared.

Core Intent Preservation: **PRESERVED**.
