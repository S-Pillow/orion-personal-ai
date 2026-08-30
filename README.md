# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion. The controlling implementation direction is **native Windows**, centered on a pinned Hermes Agent runtime, the named `companion` profile, a local Ollama model, Discord, a loopback Hermes API, and native iai memory.

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
- **Phase 1 — IN PROGRESS / MEMORY ACCEPTED / NEXT GATE OR-LIFE-008**
  - `iai-pme==3.0.8` installed in a dedicated native Python 3.11 virtual environment
  - crypto and native Rust embedder accepted
  - native Windows daemon compatibility characterized and brought to a usable state with narrowly scoped upstream-compatible fixes
  - source-pinned native Windows Hermes recall/capture adapters installed through the supported iai Hermes hook path
  - real Discord ambient capture accepted
  - canonical iai persistence and explicit semantic recall accepted
  - iai `wake_depth` changed from default `minimal` to supported `standard` so Hermes receives rendered session-start memory context
  - real `/new` fresh-session Discord recall returned the exact captured marker without `session_search`
  - Hermes built-in `MEMORY.md` and `USER.md` persistent memory targets disabled for COMPANION so iai remains the sole persistent memory authority
  - next step: configure and verify OR-LIFE-008 `idle_timeout_seconds`, then run independent real-HIBERNATION lifecycle tests and the OR-LIFE-007 accept-vs-patch decision

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

## Phase 1 native iai acceptance checkpoint

### Installation and crypto

Native iai is intentionally isolated from both global Python and Hermes' runtime:

- Python: `3.11.3`
- venv: `%LOCALAPPDATA%\hermes\profiles\companion\iai\venv`
- package: `iai-pme==3.0.8`
- `pip check`: no broken requirements
- canonical store root: `%USERPROFILE%\.iai-mcp`
- `iai-mcp crypto init`: passed
- configured embedder: native Rust, `bge-small-en-v1.5`, 384 dimensions, AVX2 available

### Native Windows daemon compatibility

Stock iai 3.0.8 was characterized before modification. Initial native Windows boot failed on an unguarded `signal.SIGHUP` reference. That behavior remains preserved as baseline evidence.

The Windows path was then corrected with narrowly scoped upstream-compatible compatibility changes rather than a replacement lifecycle system. iai remains responsible for its own daemon state, storage, retrieval, memory semantics, and lifecycle policy.

### Hermes capture and recall integration

Upstream iai 3.0.8 ships POSIX Hermes hook adapters. Orion uses source-pinned native Python equivalents for Windows, installed through the supported iai Hermes hook path.

A stale Hermes gateway initially masked live capture because the gateway had started before the hook files and approvals existed. After the supported COMPANION gateway restart, the live process registered both `pre_llm_call` and `on_session_end` hooks.

A real Discord marker turn:

`ORION_CAPTURE_FRESH_GATEWAY_20260829`

was accepted through the full write path. The live session watermark advanced immediately after turn finalization; adapter source guarantees the deferred capture is flushed and atomically placed before watermark advancement.

A separate explicit iai recall probe returned the exact marker from the canonical store with `_source=daemon`, proving canonical persistence and semantic recall independently of Hermes.

### Session-start recall mode

iai 3.0.8 defaults `wake_depth` to `minimal`. Under that mode, session-start builds compact pointer/handle metadata but renders no actual memory Markdown, so the Hermes pre-LLM hook receives an empty context even though the store and semantic recall are healthy.

Orion now uses the supported iai setting:

`wake_depth = standard`

Verification:

- profile returned `standard`
- `iai-mcp session-start` returned exit `0`
- non-empty stdout
- exact captured marker present in the rendered payload

This is a supported iai configuration change, not an Orion retrieval replacement.

### Fresh-session ambient recall acceptance

Hermes built-in persistent curated memory targets are disabled for COMPANION:

- `memory.memory_enabled = false`
- `memory.user_profile_enabled = false`

This prevents Hermes `MEMORY.md` / `USER.md` from becoming a competing persistent memory authority.

A real Discord `/new` started a fresh session. The first user question asked only for the ORION_CAPTURE marker and explicitly prohibited past-session search/tool use. Hermes returned exactly:

`ORION_CAPTURE_FRESH_GATEWAY_20260829`

No `Searching past sessions` indicator appeared. The same marker had already been independently proven present in iai's rendered `standard` session-start context.

**Hermes <-> iai ambient capture/recall integration is accepted.**

Intent-preservation status: **PRESERVED**.

## Remaining Phase 1 lifecycle gates

The next implementation work is lifecycle-only; the accepted capture path should not be reopened without contradictory evidence.

1. Configure and test OR-LIFE-008 `idle_timeout_seconds` for the COMPANION iai MCP wrapper. Initial target: approximately `600` seconds, meaningfully below iai's 30-minute HIBERNATION threshold.
2. Verify the intended sequence: wrapper recycled -> heartbeat stale -> persisted HIBERNATION -> daemon absent -> next interaction reconnects.
3. Run OR-LIFE-003a direct-store fallback verification and require `_source: "direct-store"`.
4. Run independent real-HIBERNATION Test A and Test B using separate HIBERNATION cycles.
5. Measure OR-LIFE-003b wrapper-start to authenticated daemon-ready latency from a confirmed HIBERNATION + daemon-absent state.
6. Make the OR-LIFE-007 Windows accept-vs-patch decision from observed wake behavior.
7. Complete OR-LIFE-005 Windows restart/logoff/logon lifecycle acceptance.

Do **not** substitute SLEEP for HIBERNATION. Test A and Test B must not reuse one HIBERNATION cycle because launching the wrapper for one test can wake the daemon and invalidate the other's precondition.

## Separate maintenance observations

These are real but do not invalidate memory acceptance:

- Hermes Discord safe slash-command sync has hit its 600-second timeout on multiple starts; treat as a separate Hermes/Discord maintenance defect.
- Hermes reports Python SQLite `3.40.1` and uses `journal_mode=DELETE` instead of WAL because of the WAL-reset corruption risk; handle separately from iai acceptance.
- A Hermes tool-configuration walkthrough unintentionally refreshed `cua-driver` to `0.22.2`; verification showed autostart `not-registered` and telemetry `disabled`.

## Governing architecture

- **Hermes Agent** is the native local agent runtime.
- **Ollama** is the local model server for the current accepted baseline.
- **qwen3.5-hermes:9b** is the currently accepted execution-time model choice.
- **Discord** is the accepted messaging surface.
- **Hermes API** is enabled only for the named companion profile and bound to loopback for the current baseline.
- **iai-pme 3.0.8** is the pinned Phase 1 memory engine.
- **iai** is the sole persistent memory authority for Orion COMPANION; Hermes built-in curated persistent memory is disabled.
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

## Repository strategy

### `S-Pillow/orion-personal-ai`

Canonical Orion integration/control repository for current architecture, execution status, acceptance evidence, reproducibility instructions, compatibility notes, and Orion-owned glue.

### `S-Pillow/iai-personal-memory-engine`

Compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine`. Narrow Windows compatibility fixes may be carried here only when stock behavior cannot satisfy v2.6 and the changes preserve iai semantics rather than replacing them.

### `S-Pillow/jarvis_ai`

Historical/possible-future HUD application fork. It is **not** the current active phase. HUD work resumes only after native iai Phase 1 lifecycle acceptance.

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

Proceed directly to **OR-LIFE-008**. Configure the COMPANION iai MCP wrapper `idle_timeout_seconds` to approximately `600` seconds, verify wrapper recycling behavior, then continue into the independent real-HIBERNATION lifecycle gates and the Windows accept-vs-patch decision.
