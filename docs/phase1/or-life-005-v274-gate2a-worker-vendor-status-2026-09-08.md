# OR-LIFE-005 — Orion operator controls v2.7.4 candidate1 Gate 2A

Date: 2026-09-08
Package: Orion-Operator-Controls-v2.7.4-candidate1-REVIEW.zip
Package SHA-256: fd2268aa79883dae2f0fa2b3371de022c3e54be72c85a566be01c893f79d54be
Hermes pin: 5fc308a70719a83cccdbba4c0e39c23f5a8239d5

## Gate 2A result

PASS — real worker handshake and pinned Hermes Windows status binding validated without starting or stopping Hermes, Ollama, iai, or Orion.

Observed preconditions:
- Hermes API healthy: False
- Ollama API healthy: False
- Hermes_Gateway_companion task: Ready, LogonTrigger disabled
- iai-mcp-daemon task: Ready, LogonTrigger disabled
- Hermes HEAD matched approved pin
- Hermes checkout dirty entry count: 0

Real worker / pinned vendor status probe:
- workerHandshake: PASS
- vendorStatusBinding: PASS
- presence: absent
- inFlight: false
- command files: go.json, ready.json, result.json
- missing-task local install/start veto: PASS
- vendor start was not called while registration was locally simulated absent

Observed postconditions:
- Hermes API healthy: False
- Ollama API healthy: False
- Hermes_Gateway_companion task remained Ready with LogonTrigger disabled
- iai-mcp-daemon task remained Ready with LogonTrigger disabled
- Hermes checkout dirty entry count remained 0

No runtime lifecycle start/stop was issued and no source/task persistence was changed.

## Interpretation

Gate 2A establishes that candidate1 binds successfully to the actual installed Hermes Python/runtime and exact pinned vendor Windows status implementation, including the ready/go/result worker protocol and local veto against Hermes install fallback if task registration disappears.

This does not yet accept deployment or desktop installation. The next gate is a controlled candidate lifecycle start from the extracted package with resource telemetry, followed by post-start verification before any installation transition.
