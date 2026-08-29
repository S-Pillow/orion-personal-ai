# P4-02B1A Disposable s6 Lifecycle Validation Gate

Status: ACTIVE — DISPOSABLE ONLY

Controlling document: Orion Master PRD v1.2 Approved, sections 9.5, 10.3, 10.13, 16.2, and 22.

## Purpose

Validate the installed Hermes/s6 primitives needed to preserve iai lifecycle intent before any further production mutation.

This gate must prove against the pinned Orion core image and its real inherited entrypoint that:

1. s6 is actually the running supervisor path being exercised; no `--entrypoint` bypass is allowed.
2. The installed static-service/user-bundle layout is discovered from the pinned image rather than assumed from newer upstream documentation.
3. An abnormal/nonzero service exit is restarted.
4. A clean exit can park via the installed s6 `finish` semantics rather than being unconditionally respawned.
5. A parked service can be explicitly brought up again.
6. Narrow service-control permission can be granted to the Hermes runtime identity without Docker-socket access or broad root authority.
7. The narrow control behavior is restored after a disposable container restart.
8. Native exit/status text is retained for every failed gate.

## Safety boundary

The validator must not stop, start, restart, rename, recreate, or attach to `orion-iai-m5-c`; it must not mount the production iai volume; it must not mount the Docker socket; it must not publish host ports; and it must not change production lifecycle thresholds. It may create only uniquely named disposable containers/images plus local evidence files and must remove disposable Docker resources in `finally` cleanup.

A final PASS is valid only if every sub-gate passes. On any failure, the next step is diagnosis from that exact disposable evidence, not a production workaround.

## Sequence after this gate

If this s6 semantics gate passes, the next disposable unit will run the actual `iai_mcp.daemon` against an isolated temporary store, preserve the wake-signal-first contract, verify the container-compatible explicit wake seam, and exercise clean park versus abnormal failure using the real iai process. Only after those disposable gates pass is a bounded production recovery deployment authorized.
