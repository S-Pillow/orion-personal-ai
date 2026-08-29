# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion. The controlling implementation direction is now **native Windows**, centered on a pinned Hermes Agent runtime, the named `companion` profile, a local Ollama model, Discord, a loopback Hermes API, and a native iai memory stack.

## Controlling baseline

The current controlling product requirements document is **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**, approved 2026-08-29.

The previous Docker/s6/Jarvis-oriented implementation remains useful historical evidence, but it is **not the controlling MVP architecture**. New acceptance work must follow the v2.6 native-Windows sequence.

## Current status

- **Phase 0 — PASS / CLOSED**
  - native Hermes installation pinned and verified
  - named `companion` profile created
  - authenticated companion API enabled on loopback
  - local Ollama model selected and verified
  - Discord cut over to the native gateway
  - Windows logon persistence installed
  - real Windows restart acceptance passed
  - post-restart API inference passed
  - post-restart Discord round-trip passed
  - reproducible Phase 0 PowerShell verification passed
- **Phase 1 — IN PROGRESS / PAUSED AT DIAGNOSTIC CHECKPOINT**
  - `iai-pme==3.0.8` installed in a dedicated native Python 3.11 virtual environment
  - package dependency check passed
  - iai crypto initialization passed
  - native Rust embedder passed (`bge-small-en-v1.5`, 384 dimensions, AVX2 available)
  - Windows Scheduled Task registration succeeded after one controlled elevated registration step
  - task is current-user, interactive, least-privilege
  - daemon startup is currently blocked by an upstream Windows bug in iai 3.0.8: startup references `signal.SIGHUP`, which does not exist on Windows
  - `iai-mcp doctor` currently reports 2/33 FAIL, both caused by the daemon not reaching a running state
  - capture hooks, recall acceptance, `idle_timeout_seconds`, independent HIBERNATION tests, and OR-LIFE-007 accept-vs-patch decision are **not yet complete**

HUD, vault-actions, reminders, OpenAI-dependent features, and voice remain downstream work and must not begin until Phase 1 is accepted.

## Accepted native Hermes baseline

Accepted on 2026-08-29:

- Hermes tag: `v2026.8.27`
- Hermes package: `0.20.6`
- Hermes commit: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- Hermes home: `%LOCALAPPDATA%\hermes`
- profile: `companion`
- profile home: `%LOCALAPPDATA%\hermes\profiles\companion`
- Windows persistence task: `Hermes_Gateway_companion`
- task run level: Limited / least privilege
- API listener: `127.0.0.1:8642`
- model provider: `custom`
- model: `qwen3.5-hermes:9b`
- Ollama base URL: `http://localhost:11434/v1`
- API mode: `chat_completions`
- verified Ollama runtime context: `65536`

The Hermes pin is frozen through Phase 0/1. Do **not** run `hermes update` unless a separate dependency-change decision explicitly authorizes it.

## Phase 0 acceptance evidence

The native Windows restart acceptance proved all of the following without a manual Hermes launch:

- `Hermes_Gateway_companion` launched after Windows logon
- gateway process returned
- `127.0.0.1:8642` returned healthy
- authenticated API inference returned `ORION_API_POST_RESTART_OK`
- `qwen3.5-hermes:9b` loaded through Ollama at context `65536`
- Discord initially encountered transient post-boot connection timeouts, then Hermes' reconnect watcher recovered automatically
- a real post-restart Discord round-trip returned `ORION_POST_RESTART_OK`

The observed Discord cold-boot recovery delay was approximately five minutes and is recorded as non-blocking because recovery was automatic.

## Phase 0 reproducibility

A durable PowerShell artifact was created and executed successfully on the Windows host:

`%LOCALAPPDATA%\hermes\profiles\companion\orion\phase0\Orion-Phase0-Hermes-Native-AcceptedBaseline.ps1`

The accepted verification run passed:

- PowerShell parser gate
- exact Hermes tag and commit
- clean Hermes worktree
- package version `0.20.6`
- companion model configuration
- API enablement and secret presence checks without printing secret values
- Discord credential presence checks without printing secret values
- Scheduled Task persistence
- gateway process and loopback listener
- authenticated API inference
- Ollama model/context verification

The script includes `Configure`, `Verify`, and bounded `Rollback` modes and never runs `hermes update`.

## Phase 1 native iai checkpoint

### Installation

Native iai is intentionally isolated from both global Python and Hermes' runtime:

- Python: `3.11.3`
- venv: `%LOCALAPPDATA%\hermes\profiles\companion\iai\venv`
- package: `iai-pme==3.0.8`
- `pip check`: no broken requirements
- commands present: `iai.exe`, `iai-mcp.exe`, `iai-mcp-core.exe`

### Crypto and embedder

- `iai-mcp crypto init`: passed
- key file created under `%USERPROFILE%\.iai-mcp`
- key contents must never be committed or printed
- configured embedder passed using native Rust backend
- dimensions: 384
- model: `bge-small-en-v1.5`
- AVX2: available

### Windows daemon persistence

The stock iai 3.0.8 Windows installer renders a per-user Scheduled Task with:

- task name: `iai-mcp-daemon`
- logon trigger
- `InteractiveToken`
- `LeastPrivilege`
- restart-on-failure
- generated wrapper: `%USERPROFILE%\.iai-mcp\daemon-start.cmd`
- working directory: `%USERPROFILE%\.iai-mcp`

Task creation initially returned `Access is denied` in a normal shell. A controlled one-time elevated install successfully registered the task. The registered task is confirmed as:

- user: current Windows user
- run level: Limited
- logon type: Interactive

### Current Phase 1 blocker

The task launches the correct dedicated Python interpreter, but iai 3.0.8 exits immediately with:

```text
AttributeError: module 'signal' has no attribute 'SIGHUP'
```

The failing path is the daemon boot signal-trace setup, which iterates over `SIGTERM`, `SIGINT`, and `SIGHUP` without guarding for Windows. Because the daemon exits before boot completes:

- no daemon PID state is created
- no daemon port state is created
- `iai-mcp daemon status` reports `daemon not running`
- Scheduled Task `LastTaskResult` is `1`
- `iai-mcp doctor` reports exactly two failures: daemon process absent and socket/port state absent

This is an **upstream iai 3.0.8 Windows compatibility blocker**, not a Hermes failure, not a crypto failure, and not an embedding failure.

The stock behavior has now been observed and documented. Do not run `doctor --apply` or make an unreviewed installed-package edit. On resume, decide on a narrow compatibility patch or an upstream-supported alternative, then re-run daemon/doctor acceptance.

## Known non-blocking Phase 1 observations

- Windows `HIDIdleTime` is unavailable on this machine; iai reports that L6 will fall back to heartbeat-idle only. This must be covered explicitly in later lifecycle/HIBERNATION tests.
- Claude subscription credentials are absent; iai reports fallback to local Tier-0 consolidation. No Claude login is required for the current local-first shakeout.
- `iai` is intentionally not placed on global `PATH`; Orion uses absolute paths into the dedicated venv.
- missing store/HNSW files are expected on the fresh install before successful daemon/store activity.

## Governing architecture

- **Hermes Agent** is the native local agent runtime.
- **Ollama** is the local model server for the current accepted baseline.
- **qwen3.5-hermes:9b** is the currently accepted execution-time model choice, selected from local evidence rather than hard-coded by the PRD.
- **Discord** is the accepted Phase 0 messaging surface.
- **Hermes API** is enabled only for the named companion profile and bound to loopback for the current baseline.
- **iai-pme 3.0.8** is the Phase 1 memory-engine candidate and remains pinned during the native shakeout.
- **Obsidian** remains the intended authoritative human-facing vault in later phases.
- General computer control is outside the MVP.

## Legacy implementation status

Historical Docker/container work is preserved for evidence and recovery context but is superseded as the controlling implementation path.

Legacy artifacts include:

- `orion-iai-m5-c`
- s6/container supervision notes
- old Docker image lineage and rebuild scripts
- the earlier `S-Pillow/jarvis_ai` HUD adaptation work
- previous Phase 2/3/4 acceptance records under the old architecture

These records must not be silently presented as current v2.6 acceptance. They are historical unless revalidated under the native Windows sequence.

The old Docker COMPANION container was deliberately stopped during the native Discord cutover and its restart policy was set to `no` to prevent credential contention. No legacy runtime data was intentionally deleted.

## Repository strategy

### `S-Pillow/orion-personal-ai`

Canonical Orion integration/control repository for current architecture, execution status, acceptance evidence, reproducibility instructions, compatibility notes, and Orion-owned glue.

### `S-Pillow/iai-personal-memory-engine`

Compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine`. A narrow Windows compatibility patch may be carried here only if stock 3.0.8 behavior cannot satisfy the v2.6 Phase 1 acceptance gate and the patch is explicitly approved after stock behavior is documented.

### `S-Pillow/jarvis_ai`

Historical/possible-future HUD application fork. It is **not** the current active phase. HUD work resumes only after native iai Phase 1 acceptance.

Hermes remains an upstream dependency unless sustained source-level changes later justify a fork.

## Security and evidence rules

- Never commit Discord tokens, API keys, `.env` files, iai encryption keys, decrypted memory exports, private vault contents, or runtime data.
- Never print secret values into acceptance evidence; presence/length checks are sufficient.
- Installed-runtime observations must be distinguished from upstream source claims.
- No accepted Windows feature should depend only on an interactive console paste; mutation/setup logic must have durable PowerShell source and rollback targets.
- Do not run `hermes update` during the Phase 0/1 pin freeze.
- Do not enable optional paid/cloud paths without explicit authorization.
- Do not treat historical Docker acceptance as native-Windows acceptance.

## Resume point

The next implementation session should begin from this exact checkpoint:

1. Preserve the stock iai 3.0.8 `signal.SIGHUP` Windows crash as baseline evidence.
2. Decide whether to apply a narrowly scoped Windows compatibility patch or use an upstream-supported fix, without changing memory semantics.
3. Start `iai-mcp-daemon` successfully and rerun `iai-mcp doctor`.
4. Verify capture hooks.
5. Verify recall.
6. Configure and test `idle_timeout_seconds`.
7. Run full independent lifecycle/HIBERNATION tests, including the heartbeat-idle fallback behavior on Windows.
8. Make the OR-LIFE-007 accept-vs-patch decision from observed behavior.
9. Only after Phase 1 acceptance, resume HUD work; vault-actions, reminders, OpenAI-dependent features, and voice remain later work.
