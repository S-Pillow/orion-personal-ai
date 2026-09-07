# iai-pme 3.0.8 Windows Demand-Wake Patch

Status: **IMPLEMENTATION PREPARED — NOT YET INSTALLED OR ACCEPTED**

## Scope

This patch is a narrow compatibility correction for the pinned `iai-pme==3.0.8` MCP wrapper on native Windows 11.

It does not replace iai lifecycle policy, storage, ranking, consolidation, or memory semantics. It does not add an Orion supervisor. Hermes remains the MCP child-process owner and iai remains the daemon/store/lifecycle owner.

Core Intent Preservation Gate: **PRESERVED**.

## Runtime evidence

Independent Test B reached a genuine parked state:

- observed `2026-09-07T02:06:27.7271092-04:00`
- lifecycle `HIBERNATION`
- iai daemon absent
- iai MCP wrapper absent

A fresh stock wrapper then produced:

- MCP initialize: `233 ms`
- authenticated daemon IPC ready: `False`
- measurement timeout: `60327 ms`
- lifecycle remained `HIBERNATION`
- daemon remained absent
- wrapper-created `wake.signal` remained present

The wrapper-launched `iai-mcp doctor --auto` was independently confirmed by the `.doctor-auto-last` timestamp, but the Windows Task Scheduler task was not started during that failed demand-wake attempt.

A controlled vendor-path wake from the same failed parked state then produced:

- `iai-mcp daemon start` exit code `0`
- vendor start command: `467 ms`
- authenticated Windows IPC ready: `True`
- start-to-authenticated-ready: `1733 ms`
- lifecycle transitioned to `WAKE`
- `wake.signal` was consumed
- Task Scheduler task `iai-mcp-daemon` entered `Running`

This isolates the defect to wrapper lifecycle orchestration rather than the iai daemon, Windows Task Scheduler registration, canonical store, or authenticated IPC transport.

## Source findings

Pinned iai 3.0.8 wrapper behavior is POSIX-centric in three places relevant to demand wake:

1. wrapper reachability uses a Node path-socket probe even though iai Windows IPC is authenticated loopback TCP via `.daemon.port` and `.daemon.token`;
2. wrapper process identity probing uses `/bin/ps`, which is not a Windows process-liveness mechanism;
3. `ensureDaemonAlive()` directly invokes its platform start helper only for Darwin.

The vendor Python CLI already provides the required Windows activation abstraction: `iai-mcp daemon start`, which calls the installed per-user Task Scheduler task.

## Patch behavior

The guarded patcher at `scripts/phase1/patch-iai-windows-demand-wake.py` changes only the installed wrapper `lifecycle.js` for pinned iai 3.0.8.

It adds:

- Windows authenticated readiness through `127.0.0.1:<.daemon.port>` plus `.daemon.token`, requiring a real `status` response;
- Windows daemon PID identity probing through native CIM/PowerShell instead of `/bin/ps`;
- Windows direct activation through iai's own `iai-mcp daemon start` abstraction;
- `win32` eligibility in the existing direct activation branch.

POSIX and Darwin code paths remain intact.

## Guardrails

The patcher:

- refuses to run off Windows;
- refuses any iai version other than `3.0.8`;
- validates known source anchors before modification;
- defaults to read-only preflight mode;
- creates a timestamped backup before write;
- writes atomically;
- runs Hermes Node `--check` after modification;
- automatically restores the backup if syntax validation fails;
- supports `--rollback-latest`;
- does not read or print memory contents, transcripts, auth tokens, or secrets.

## Acceptance plan

1. Run patcher preflight using the COMPANION iai venv Python.
2. Review the exact installed-wrapper SHA and source-shape result.
3. Apply patch.
4. With daemon already live, start a fresh wrapper and prove authenticated liveness does not spuriously restart the Task Scheduler task.
5. Allow a new independent real HIBERNATION cycle.
6. Rerun OR-LIFE-003b measuring fresh-wrapper start to authenticated daemon-ready.
7. Accept OR-LIFE-007 only if the patched wrapper wakes through the vendor Task Scheduler path with bounded latency and no parallel supervisor.
8. Continue to OR-LIFE-005 restart/logoff/logon acceptance.

No upgrade to iai 3.1.0 or Hermes 0.21.0 is part of this patch ticket; dependency changes remain separate decisions after Phase 1 lifecycle acceptance.
