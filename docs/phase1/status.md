# Phase 1 Status

Status: **IN PROGRESS / PAUSED AT NATIVE-WINDOWS DIAGNOSTIC CHECKPOINT**

Controlling baseline: **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**, approved 2026-08-29.

> Historical note: the previous contents of this file described a Docker/s6-era Phase 1 that was accepted under an older architecture. That acceptance is retained in Git history but is not the controlling v2.6 Phase 1. The current Phase 1 is the native-Windows iai shakeout defined by v2.6.

## Entry conditions

Phase 0 is fully accepted and closed under the native-Windows architecture.

Accepted Phase 0 baseline:

- Hermes tag `v2026.8.27`
- Hermes package `0.20.6`
- Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- named profile `companion`
- Windows task `Hermes_Gateway_companion`
- loopback API `127.0.0.1:8642`
- model `qwen3.5-hermes:9b`
- provider `custom`
- Ollama base URL `http://localhost:11434/v1`
- API mode `chat_completions`
- verified model context `65536`
- real Windows restart acceptance passed
- post-restart authenticated API inference passed
- post-restart Discord round-trip returned `ORION_POST_RESTART_OK`
- reproducible Phase 0 PowerShell verification passed

The Hermes pin remains frozen through Phase 1. Do not run `hermes update` without explicit dependency-change authorization.

## Phase 1 objective

Prove whether `iai-pme==3.0.8` can satisfy Orion's native-Windows memory/lifecycle requirements before HUD work resumes.

Phase 1 is not complete until all of the following are accepted:

1. native iai installation
2. crypto initialization
3. native daemon persistence and health
4. capture hooks
5. recall
6. `idle_timeout_seconds`
7. independent lifecycle/HIBERNATION testing
8. OR-LIFE-007 accept-vs-patch decision based on observed behavior

## Completed work

### Native Python isolation — PASS

A dedicated Python 3.11 virtual environment was selected instead of global Python or the Hermes runtime:

`%LOCALAPPDATA%\hermes\profiles\companion\iai\venv`

Observed:

- Python `3.11.3`
- `iai-pme==3.0.8`
- `pip check` reports no broken requirements
- `iai.exe`, `iai-mcp.exe`, and `iai-mcp-core.exe` are present
- no global PATH dependency is required

### Crypto initialization — PASS

`iai-mcp crypto init` completed successfully.

The native crypto state exists under `%USERPROFILE%\.iai-mcp` and the key file is valid. Key contents are secret and must never be printed or committed.

### Native embedder — PASS

`iai-mcp doctor` verifies:

- configured embedder encodes successfully
- backend: Rust
- dimensions: 384
- model: `bge-small-en-v1.5`
- AVX2 available

### Windows daemon task registration — PASS WITH CONTROLLED UAC

Stock iai 3.0.8 initially failed to register its Windows task from a normal shell:

```text
schtasks /Create failed (1): ERROR: Access is denied.
```

Installed-source inspection showed that the stock Windows installer intentionally creates a per-user Task Scheduler task rather than a SYSTEM/elevated daemon. The task template specifies:

- task name `iai-mcp-daemon`
- logon trigger
- `InteractiveToken`
- `LeastPrivilege`
- `MultipleInstancesPolicy=IgnoreNew`
- restart-on-failure interval 1 minute, count 3
- no execution-time limit
- wrapper `%USERPROFILE%\.iai-mcp\daemon-start.cmd`
- working directory `%USERPROFILE%\.iai-mcp`

A one-time controlled elevated registration succeeded.

Registered task observations:

- state: Ready after failed launch
- RunLevel: Limited
- user: current Windows user
- LogonType: Interactive
- LastTaskResult: `1`

The task itself does not run elevated; elevation was used only to register it.

## Current blocker: upstream iai 3.0.8 Windows daemon crash

The registered task reaches the generated wrapper and invokes the correct dedicated Python interpreter:

```text
%LOCALAPPDATA%\hermes\profiles\companion\iai\venv\Scripts\python.exe -m iai_mcp.daemon
```

The daemon then exits immediately during boot.

Captured traceback root cause:

```text
AttributeError: module 'signal' has no attribute 'SIGHUP'
```

Failing source behavior:

```python
for _sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
```

On Windows, Python's `signal` module does not expose `SIGHUP`, and iai 3.0.8 does not guard that reference before entering the loop.

### Consequence

Because the daemon crashes before startup completes:

- `iai-mcp daemon status` reports `daemon not running`
- no daemon PID state exists
- no daemon port/socket state exists
- Scheduled Task `LastTaskResult` is `1`
- `iai-mcp doctor` reports 2/33 FAIL

The two failures are:

1. daemon process alive — absent
2. socket/port state fresh — absent

All other current doctor failures are absent. Remaining non-pass items are warnings/fresh-install observations.

## Doctor observations to preserve

Current non-blocking observations:

- crypto key state: PASS
- native embedder: PASS
- AVX2: PASS
- no orphan core processes: PASS
- no corrupt daemon state file: PASS / not yet created
- fresh store/HNSW state: expected before successful daemon/store activity
- `HIDIdleTime`: unavailable on this Windows host; iai reports L6 will fall back to heartbeat-idle only
- Claude credentials: absent; iai reports fallback to local Tier-0 consolidation
- `iai` not on global PATH: intentional Orion isolation choice, not a repair target

Do not run `doctor --apply` at this checkpoint.

## Classification

The current blocker is classified as an **upstream iai 3.0.8 Windows compatibility defect in daemon boot signal handling**.

It is not currently classified as:

- a Hermes problem
- a Task Scheduler registration problem
- a privilege/run-level problem after registration
- a crypto problem
- an embedder problem
- a Python-version support problem

Stock behavior has been observed before any compatibility patch, satisfying the requirement to characterize the native Windows risk surface first.

## Safe stopping point

This is an accepted diagnostic stopping point for the work session.

The system is left in a bounded state:

- Phase 0 native Hermes remains running and accepted
- Hermes pin remains unchanged
- native iai 3.0.8 remains installed and pinned
- crypto initialization remains valid
- iai Scheduled Task remains registered as current-user / Limited / Interactive
- iai daemon is not running because stock 3.0.8 crashes at startup
- no capture hooks have been installed/accepted
- no recall acceptance has been performed
- no lifecycle/HIBERNATION acceptance has been performed
- no HUD work has resumed

## Resume plan

On the next implementation session:

1. preserve the `signal.SIGHUP` crash as baseline evidence
2. decide whether to carry a narrowly scoped Windows compatibility patch in the Orion iai fork or adopt an upstream-supported fix
3. if patching, change only platform-safe signal registration; do not alter memory semantics
4. start the daemon successfully
5. rerun `iai-mcp daemon status` and `iai-mcp doctor`
6. verify capture hooks
7. verify recall
8. configure/test `idle_timeout_seconds`
9. perform independent lifecycle/HIBERNATION tests, explicitly covering heartbeat-idle fallback on this Windows host
10. make OR-LIFE-007 accept-vs-patch decision from observed behavior
11. only after Phase 1 acceptance, proceed to HUD integration

## Explicit non-goals at this checkpoint

Do not:

- run `hermes update`
- run `iai-mcp doctor --apply`
- enable Claude subscription/cloud behavior merely to silence warnings
- add iai globally to PATH solely to satisfy doctor
- start HUD work
- treat historical Docker/s6 Phase 1 evidence as current native-Windows acceptance
