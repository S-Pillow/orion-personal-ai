# Phase 1 Status

Status: **IN PROGRESS — MEMORY INTEGRATION ACCEPTED / NEXT GATE OR-LIFE-008**

Controlling baseline: **ORION — Master PRD v2.6 (AI-Optimized Execution Edition)**, approved 2026-08-29.

> Historical note: earlier Phase 1 evidence under Docker/s6 is retained in Git history but is not controlling. This file records the native-Windows Phase 1 defined by v2.6.

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
- post-restart Discord round-trip passed

The Hermes pin remains frozen through Phase 1. Do not run `hermes update` without an explicit dependency-change decision.

## Phase 1 objective

Prove whether pinned `iai-pme==3.0.8` can satisfy Orion's native-Windows memory and lifecycle requirements without replacing iai memory semantics or adding a parallel memory subsystem.

Phase 1 is not complete until all lifecycle gates are accepted. Current remaining work begins with OR-LIFE-008 and then the independent HIBERNATION tests.

## Completed work

### Native iai isolation — PASS

A dedicated Python 3.11 virtual environment is used instead of global Python or the Hermes runtime:

`%LOCALAPPDATA%\hermes\profiles\companion\iai\venv`

Observed baseline:

- Python `3.11.3`
- `iai-pme==3.0.8`
- `pip check` clean
- `iai.exe`, `iai-mcp.exe`, and `iai-mcp-core.exe` present
- canonical iai root `%USERPROFILE%\.iai-mcp`
- no global PATH dependency required

### Crypto and native embedder — PASS

- `iai-mcp crypto init` passed
- key material remains local and must never be printed or committed
- Rust embedder passed
- model `bge-small-en-v1.5`
- dimensions `384`
- AVX2 available

### Windows daemon compatibility — PASS WITH NARROW UPSTREAM-COMPATIBLE FIXES

Stock iai 3.0.8 was first characterized before modification.

Initial blocker:

```text
AttributeError: module 'signal' has no attribute 'SIGHUP'
```

The Windows path required narrowly scoped compatibility corrections rather than a replacement lifecycle system. The fixes preserve iai ownership of daemon state, memory semantics, storage, retrieval, and lifecycle policy.

The native daemon subsequently reached a usable Windows state and the iai memory integration work proceeded. The earlier stock crash remains baseline evidence and must not be erased from history.

### Native Hermes capture/recall hooks — PASS

Upstream iai 3.0.8 ships POSIX Hermes hook adapters. Orion's native-Windows integration uses source-pinned Python equivalents installed through the supported iai Hermes hook path rather than a parallel capture service.

Installed COMPANION hooks:

- `agent-hooks\iai-mcp-hermes-recall.py`
- `agent-hooks\iai-mcp-hermes-capture.py`

Hermes allowlist/consent showed both hooks approved and enabled.

Manual Hermes hook execution against a real Discord session proved:

- correct COMPANION `state.db` discovery
- correct session-row selection
- deferred capture placement
- watermark advancement
- shell-hook subprocess execution with exit `0`

### Live ambient capture — PASS

A real Discord turn used marker:

`ORION_CAPTURE_FRESH_GATEWAY_20260829`

The live session was `20260829_203937_77ab213c`.

A first live attempt exposed a stale-process condition: the persistent Hermes gateway had started hours before the hook files and approvals were installed, so the running gateway had never loaded those callbacks.

Supported recovery:

`hermes -p companion gateway restart`

The fresh gateway then logged registration of both `pre_llm_call` and `on_session_end` hooks.

On the next real Discord turn:

- inbound Discord message reached Hermes
- the conversation finalized normally
- the iai capture watermark for the live session advanced at `22:38:40`, immediately after turn finalization
- adapter source guarantees deferred JSONL placement is flushed and atomically renamed before watermark advancement

Therefore the live `on_session_end` capture path is accepted.

**Permanent procedural rule:** after installing, changing, or approving Hermes hooks, restart the COMPANION gateway before acceptance testing unless a supported live-reload path is separately proven.

### Canonical iai persistence and semantic recall — PASS

A read-only explicit recall probe against the canonical iai installation returned:

- profile RPC reachable
- recall exit code `0`
- recall source `daemon`
- five hits returned
- exact marker found

This independently proves the captured Discord turn reached the canonical iai memory store and is semantically recallable.

### iai session-start mode — ROOT CAUSE FOUND / CONFIGURED / PASS

Initial fresh-session tests produced `0` characters from:

`iai-mcp session-start --session-id ...`

This was not an IPC or retrieval failure. Source review of iai 3.0.8 showed that the default profile knob is:

`wake_depth = minimal`

Under `minimal`, iai creates compact pointer/handle metadata but leaves the Markdown-rendered memory fields empty. That behavior is valid vendor behavior but does not satisfy Orion's requirement for ambient prior-context injection into a fresh Hermes conversation.

The supported iai profile knob was changed to:

`wake_depth = standard`

Verification after the change:

- `profile_get wake_depth` returned `standard`
- `session-start` exit code `0`
- stdout length `551`
- stderr length `0`
- exact marker present in the rendered session-start payload

No custom ranking, retrieval, consolidation, or alternative memory layer was introduced.

### Hermes built-in curated memory — DISABLED FOR COMPANION

Hermes ships its own file-backed `MEMORY.md` / `USER.md` persistent memory surface. This is independent of iai and would create competing persistence authority for Orion.

For COMPANION, both supported Hermes settings are disabled:

- `memory.memory_enabled = false`
- `memory.user_profile_enabled = false`

A pre-existing `USER.md` file may remain on disk, but with the user-profile target disabled it is not an active session-start memory source. It should not be silently deleted because it is useful provenance/evidence.

This preserves the v2.6 architectural rule that iai owns Orion persistent memory semantics.

### Fresh-session live ambient recall — PASS / ACCEPTED

A real Discord `/new` produced a fresh Hermes session. The first user question was deliberately phrased without referring to a prior conversation:

`What is the ORION_CAPTURE marker? Reply with the marker only. Do not search past sessions or use any tools.`

Observed:

- `/new` confirmed `Session reset! Starting fresh.`
- no `Searching past sessions` / `session_search` tool activity appeared
- Hermes returned exactly `ORION_CAPTURE_FRESH_GATEWAY_20260829`
- Hermes built-in `MEMORY.md` and `USER.md` targets were both disabled
- the same exact marker had already been independently proven present in iai's `standard` session-start payload

Accepted end-to-end chain:

`Discord turn -> Hermes on_session_end -> iai canonical store -> fresh Hermes session -> pre_llm recall hook -> iai session-start context -> correct model answer`

## Memory acceptance verdict

**Hermes <-> iai ambient capture/recall integration: ACCEPTED.**

Intent-preservation status: **PRESERVED**.

The accepted solution keeps:

- Hermes as the conversation/gateway owner
- iai as the persistent memory authority
- the supported Hermes hook mechanism
- the canonical iai store
- iai's own supported `wake_depth` profile control

No second embedding/ranking/consolidation stack, capture service, gateway, or lifecycle supervisor was added.

## Separate issues discovered during memory acceptance

These are real but do not invalidate the memory acceptance:

### Discord slash-command synchronization

Hermes safe command synchronization timed out after its 600-second budget on both an older gateway start and the fresh gateway start. The persisted command-sync state showed an attempt with no success record. `/new` later executed successfully after Discord reconciliation recovered enough to expose the command.

Treat this as a separate Hermes/Discord maintenance defect, not an iai memory defect.

### SQLite compatibility warning

Hermes reports Python SQLite `3.40.1` and therefore falls back from WAL to `journal_mode=DELETE` because of the known WAL-reset corruption risk. This did not block the tested gateway or iai integration and should be handled separately from Phase 1 memory acceptance.

### CUA configurator side effect

A Hermes tool-configuration walkthrough unintentionally refreshed `cua-driver` to `0.22.2`. Verification afterward showed:

- `cua-driver 0.22.2`
- autostart `not-registered`
- telemetry `disabled (source: persisted)`

This is not part of the memory architecture and requires no Phase 1 memory rollback.

## Current Phase 1 state

Accepted:

1. native iai installation
2. crypto initialization
3. native daemon compatibility sufficient to proceed
4. Hermes capture-hook integration
5. canonical-store persistence
6. explicit semantic recall
7. iai `standard` session-start context
8. real fresh-session Discord ambient recall
9. competing Hermes built-in curated memory disabled

Still open:

1. OR-LIFE-008 — configure Hermes MCP `idle_timeout_seconds` meaningfully below iai's 30-minute HIBERNATION threshold; initial target `600` seconds
2. independent real-HIBERNATION lifecycle Test A
3. independent real-HIBERNATION lifecycle Test B
4. OR-LIFE-003a direct-store fallback verification as required by the lifecycle gate
5. OR-LIFE-003b measured wrapper-start to authenticated daemon-ready latency from confirmed HIBERNATION + daemon-absent state
6. OR-LIFE-007 Windows accept-vs-patch decision from observed wake behavior
7. OR-LIFE-005 Windows restart/logoff/logon lifecycle acceptance

Tests A and B must use separate confirmed HIBERNATION cycles because launching a fresh wrapper for Test A can itself wake the daemon and invalidate the Test B precondition.

## Next execution step

Proceed to **OR-LIFE-008**.

Configure the COMPANION iai MCP wrapper `idle_timeout_seconds` to approximately `600` seconds so the wrapper can recycle before iai's 30-minute HIBERNATION threshold. Then verify the intended sequence:

`wrapper recycled -> heartbeat stale -> persisted HIBERNATION -> daemon absent -> next interaction reconnects`

Do not substitute SLEEP for HIBERNATION.

After OR-LIFE-008 is verified, run the two independent HIBERNATION acceptance cycles and measure real Windows wake behavior before deciding whether any additional upstream-compatible iai lifecycle patch is justified.

## Explicit non-goals

Do not:

- run `hermes update` during the Phase 0/1 pin freeze
- replace iai memory semantics or add a parallel persistent memory system
- create an Orion lifecycle supervisor
- treat SLEEP as evidence for HIBERNATION
- reopen the accepted capture path without contradictory evidence
- begin HUD integration before Phase 1 lifecycle acceptance
- delete historical evidence solely to make the current state look cleaner
