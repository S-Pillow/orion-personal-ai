# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion for **native Windows 11**. The accepted foundation uses a pinned Hermes Agent runtime, the named `companion` profile, a local Ollama model, Discord, a loopback Hermes API, native iai persistent memory, and an Orion-owned local HUD/presentation layer.

## Controlling baseline

The controlling product requirements document is **ORION — Master PRD v2.9**, approved 2026-09-24.

Canonical artifact and approval record:

- `docs/prd/orion-master-prd-v2.9-ai-optimized-approved.docx`
- `docs/prd/orion-master-prd-v2.9-approval-record-2026-09-24.md`

PRD v2.9 supersedes v2.8. It preserves the accepted native-Windows/manual-off authority model while adding explicit contracts for truthful runtime-to-HUD projection, reconnect durability, richer Phase 5 action/evidence presentation, bounded voice-recorder hardening, durable reminder recovery semantics, and deferred Persistent Goal Mode boundaries.

The accepted **manual-off** lifecycle model remains unchanged:

- Orion/Hermes do not start automatically at Windows login.
- Start Orion / Stop Orion are explicit operator actions.
- Hermes and iai Scheduled Tasks remain registered for vendor-supported behavior, but their LogonTriggers are disabled.
- Ollama login startup is disabled.
- iai remains its own lifecycle and persistent-memory authority.
- Orion must not add a parallel gateway, memory system, embedding/ranking stack, voice runtime, hotword service, or lifecycle supervisor without a separately approved demonstrated gap.

Historical Docker/s6/JARVIS implementation records remain useful provenance but are not the controlling native-Windows path.

## Current status

### Phase 0 — PASS / CLOSED

Accepted native baseline:

- Hermes tag `v2026.8.27`
- Hermes package `0.20.6`
- Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- profile `companion`
- COMPANION home `%LOCALAPPDATA%\hermes\profiles\companion`
- API `127.0.0.1:8642`
- model `qwen3.5-hermes:9b`
- Ollama provider `http://localhost:11434/v1`
- context `65536`
- Discord native gateway accepted

### Phase 1 — PASS / CLOSED

Phase 1 lifecycle and memory acceptance is complete. Closure was merged in PR #6 at:

`7c55493e0401f1003b3f0f2438e684a5fb144227`

Accepted Phase 1 results include:

- iai-pme `3.0.8`
- canonical store `%USERPROFILE%\.iai-mcp`
- supported Hermes recall/capture hooks on Windows
- real ambient Discord capture into iai
- semantic recall from the canonical iai store
- `wake_depth=standard`
- Hermes built-in persistent memory/user-profile targets disabled for COMPANION
- Hermes-managed iai MCP wrapper with accepted idle recycling at `idle_timeout_seconds=600`
- daemon-independent recall with `_source: "daemon-down-full"`
- authenticated HIBERNATION wake at **5.887 s** wrapper-start -> daemon-ready
- OR-LIFE-007 **ACCEPT / no further wake patch**
- manual-off Start/Stop controls accepted through restart and pure logoff/logon
- changed-boot recovery accepted with the BootTime identity correction

Final Phase 1 evidence includes:

- `docs/evidence/or-life-005-final-acceptance-2026-09-09.md`
- `docs/evidence/or-life-007-owner-disposition-2026-09-09.md`
- `evidence/or-life-005/recovery-gate-d-2026-09-09.md`
- `docs/phase1/status.md`

### Phase 2 — typed HUD compatibility/control slice accepted

The internal Phase 2A typed-control bridge slice was accepted and merged through PR #9. It established the loopback-only Orion HUD bridge, persistent COMPANION typed-session continuity, progressive streaming, STOP, browser credential isolation, profile-specific credential separation, Hermes-routed iai recall, truthful degraded-state presentation, and persisted-session transcript reload.

The accepted bridge remains a narrow presentation/control adapter. It does not own lifecycle, voice, memory semantics, model routing, or arbitrary Hermes proxy authority.

Current Phase 2 record:

`docs/phase2/status.md`

That status file is retained as the Phase 2 closure/handoff record; the repository resume point is no longer Phase 2 discovery.

### Phase 3 — visual companion foundation merged

The current `main` source now includes the major Orion visual/presentation foundation built after the Phase 2 typed bridge:

- PR #10 / P3-01 — deterministic Orion Core state + gaze foundation
- PR #11 / P3-02 — adaptive Conversation/System workspace foundation
- PR #12 / P3-03 — read-only Memory Lens + native iai Brain handoff
- PR #13 / P3-04 — provenance/origin + descriptive authority foundation
- PR #14 / P3-05A — composition convergence toward the approved Orion interface

The merged HUD keeps Conversation as the default workspace, makes the Orion Core a truthful state-driven presentation surface, retains native iai ownership for detailed memory administration, and preserves the server-side credential and manual-off boundaries.

Latest merged Phase 3 composition commit:

`ef1ae1156c32c4f5afdd0a6d6568577f1498eb6a`

### Phase 4 — native Hermes voice foundation partially accepted; final live voice acceptance deferred

Phase 4 remains open, but its current state is narrower than the earlier wake-training experiment.

Accepted / merged:

- P4-04A Hermes audio gateway compatibility bridge merged in PR #18;
- authenticated loopback `POST /api/audio/transcribe` and `POST /api/audio/speak` compatibility endpoints are available on the accepted Hermes gateway;
- `audio_api=true` is accepted while `realtime_voice=false` remains truthful;
- direct TTS -> STT transport round-trip passed against the accepted runtime.

Deferred / not yet merge-ready:

- draft PR #16 contains the Orion push-to-talk voice foundation and remains unmerged;
- live PTT already proved microphone -> Hermes STT -> same persisted conversation session -> visible reply;
- active-run interruption by PTT was observed;
- final audible spoken-reply / Speak Replies OFF / audible-barge-in acceptance is deferred under issue #19 because Edge TTS was intermittently unavailable during an ISP/provider-path outage;
- direct Edge TTS and direct P4-04A audio round-trip later recovered without an Orion/Hermes code change, so the remaining gate is runtime acceptance under stable connectivity rather than another speculative code patch.

Wake status:

- custom `Hey Orion` v1 and v2 remain rejected experimental artifacts at 48.7% and 35% live detection respectively;
- the working acceptance gate remains `>=95%`;
- no v3 is authorized under the current training approach;
- push-to-talk/manual activation is the accepted interim activation path;
- wake does not imply login auto-start.

Tracking:

- draft PR #16 — Phase 4 P4-04 push-to-talk voice foundation
- issue #19 — P4-04B resume native TTS/live voice acceptance after Edge connectivity stabilizes

### Phase 5 - source/runtime qualification accepted through P5-02T first production move

Phase 5 has advanced through source qualification, preview-only COMPANION installation, installed-runtime disposable mutation qualification, production recovery-root acceptance, recovery-root persistence, and live runtime-ingestion verification.

Accepted checkpoints:

- P5-01: native plugin contract, canonical containment, side-effect-free edit/move previews, iai-backed destination recommendation, and a fail-closed public apply placeholder;
- P5-02A through P5-02G: exact approval payloads, fresh handler-side `ALLOW ONCE` evidence, disposable edit/move/restore execution, restart-safe non-authorizing receipts, recovery classification, Windows file-identity hardening, and source-qualified production guardrails;
- P5-02H: exact plugin installed and enabled in COMPANION with `mcp_allowlist: ["iai-mcp"]`, while public apply remained fail-closed;
- P5-02I: installed plugin qualified against disposable roots for edit, move, stale-state refusal, replay refusal, restart classification, historical restore, and controlled failure classification;
- P5-02J: production recovery root created and ACL-qualified with production mutation still disabled;
- P5-02K: accepted recovery-root path persisted append-only in COMPANION `.env`, with rollback captured and no mutation-mode setting persisted;
- P5-02L: live COMPANION runtime ingested the persisted recovery root, exposed the expected four-tool `orion_vault` toolset, retained `mutation_allowed=false`, and returned to manual-off;
- P5-02M: repository integration and guarded production-registration design freeze accepted with no runtime change;
- P5-02N: guarded registered apply wrapper accepted in source at qualified code head `faf8b4787d8e6fb668eb5e9d754104910b4b401a`, with 129/129 Phase 5 tests, Hermes approval 3/3, Hermes dispatcher 2/2, HUD Python 78/78, HUD rendering 3/3, and compile checks passing on Windows;
- P5-02O: exact P5-02N-qualified plugin `0.2.0` installed into COMPANION with rollback captured, live guarded-wrapper registration verified, production mutation still disabled, recovery inventory still empty, config/`.env` unchanged, and Hermes restored to manual-off;
- P5-02P: deterministic registered-dispatch approval proof passed, controlled canary fixture created, and read-only readiness froze the exact target, pre-edit Windows file identity, before/after hashes, and exact diff while mutation remained disabled;
- P5-02Q: first real Orion production mutation accepted — exactly one guarded `edit_note` on the controlled canary, fresh human `once` approval, committed schema-v2 recovery/receipt, zero recovery attention state, mutation mode returned to disabled, and Hermes remained manual-off;
- P5-02R: production restore qualification accepted — the exact P5-02Q canary edit was restored from its committed recovery record through the guarded registered apply path and a fresh human `once`; a new committed restore recovery/receipt was created, the origin record remains valid as `committed_then_changed`, total recovery count is 2 with zero attention, mutation mode is disabled, and Hermes remains manual-off;
- P5-02T: first production move accepted — the frozen P5-02S controlled draft moved through the guarded registered apply path with a fresh human `once`; source is absent, target is present at the frozen SHA-256, new move recovery `8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6` is valid/committed, total recovery count is 3 with zero attention, mutation mode is disabled, and Hermes remains manual-off.

Current installed/runtime boundary:

- installed plugin source exactly matches P5-02N-qualified code head `faf8b4787d8e6fb668eb5e9d754104910b4b401a`;
- installed plugin manifest version is `0.2.0`;
- `ORION_P5_PRODUCTION_RECOVERY_ROOT` is persisted and runtime-qualified;
- `ORION_P5_MUTATION_MODE` is not persisted and resolves to `disabled`;
- registered `orion_vault_apply_plan` points to `apply_plan_production_guarded`;
- disabled public apply refuses with `production_mutation_not_enabled` before human approval or private-executor delegation;
- `_execute_production_plan_candidate()` remains private and unregistered;
- production recovery inventory now contains exactly three valid records with zero attention state;
- controlled canary `C:\Personal\Me\_Orion-P5-Canary.md` is restored to the original `state: before` form with SHA-256 `ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c`;
- current canary Windows file identity is `5e1aeb8a1aeb5d91:428a0300000031000000000000000000`;
- origin P5-02Q recovery ID `33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f` remains valid and reads `committed_then_changed`;
- P5-02R restore recovery ID `1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27` is valid and `committed`;
- P5-02T move recovery ID `8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6` is valid and `committed`;
- controlled move source `C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md` is absent after the accepted move;
- controlled move target `C:\Personal\Me\_Orion-P5-Move-Canary.md` is present with SHA-256 `132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132`;
- COMPANION `config.yaml` and `.env` remain unchanged;
- Hermes is restored to manual-off;
- `ORION_P5_MUTATION_MODE` remains unpersisted and resolves to disabled outside the bounded child process.

P5-02O rollback capture:

`C:\Users\spill\AppData\Local\hermes\profiles\companion\orion\backups\p5-02o-installed-disabled-20260923-040536`

The P5-02Q edit, P5-02R restore, and P5-02T first production move are accepted. P5-02U move-source restore, target deletion, any further edit/move/restore, or recovery-record cleanup remains a separate authorization boundary.

## Accepted manual-off lifecycle

Default behavior is intentionally quiet:

- Windows boot/login -> Hermes off
- Ollama off
- iai wrapper absent unless vendor on-demand behavior needs it
- iai daemon not login-started
- `Hermes_Gateway_companion` remains registered with LogonTrigger disabled
- `iai-mcp-daemon` remains registered with LogonTrigger disabled
- `Orion Host Idle Bridge` absent
- Ollama Startup shortcut absent
- Start Orion / Stop Orion remain explicit owner actions

iai remains vendor-managed and is intentionally not force-killed by Orion Stop.

## Operator controls and recovery note

The accepted installed operator version is `2.7.4-candidate1`.

During final recovery acceptance, the original `win_process.boot_id()` implementation was proven unsuitable because `NtQuerySystemInformation(90)` returned an identifier that remained unchanged across a real Windows Restart. The accepted correction uses kernel `SystemTimeOfDayInformation` (class 3) `BootTime`. It was proven stable within a boot and different after Restart; supported recovery then archived the prior-boot journal without acting on old PIDs.

Source-controlled correction:

`scripts/operator/patches/or-life-recovery-boottime.patch`

**Do not reinstall an original unpatched v2.7.4 candidate package and assume recovery is accepted.** Any repackaged/rebuilt operator controls must include the accepted BootTime correction and pass the relevant recovery preflight.

## Governing architecture

- **Hermes owns the agent runtime and preferred native voice/wake path.**
- **iai owns persistent memory.**
- **Orion owns the living visual companion, presentation, and authorized control surface.**
- **Obsidian remains the durable human-authored document vault.**
- **S-Pillow/jarvis_ai is a selective reference/code donor, not the Orion runtime architecture.**

Do not duplicate these authorities for convenience.

## Dependency posture

The last dedicated dependency-watch record was captured on 2026-09-09. It is historical evidence, not automatic authorization to upgrade anything.

Accepted pins remain:

- Hermes `v2026.8.27` / package `0.20.6`
- iai `3.0.8`
- installed Ollama observed during Phase 2A: `0.32.15`

Any newer Hermes, iai, Ollama, model, or presentation dependency is a **candidate** until separately qualified under PRD v2.9. Do not replace an accepted dependency merely because a newer release exists.

Dependency-watch record:

`docs/phase2/dependency-watch-2026-09-09.md`

## Architecture guardrails

- No Orion lifecycle supervisor.
- No second memory semantics, embedding, ranking, or consolidation system.
- No parallel agent gateway/service.
- No duplicate STT/TTS/wake orchestration when Hermes satisfies the requirement.
- No Docker/WSL requirement for the running Orion product. WSL may be used only as isolated development/training tooling when explicitly bounded.
- Browser assets never receive the Hermes API key.
- HUD/adapter listeners remain loopback-only during MVP.
- Authority/provenance/voice indicators describe observed state; they do not grant permission.
- Browser presentation state is not durable authority. Consequential reconnect state must come from supported persisted Hermes/plugin evidence, and unknown state must remain explicit when it cannot be reconstructed.
- Presentation projection must be allowlisted and may normalize observed facts, but it must not become a second event, approval, persistence, or runtime authority.
- Narrow dependency patches are allowed only when necessary, evidence-backed, source-controlled, reversible, and consistent with the Intent Preservation Check.

Core Intent Preservation Gate:

> Are we solving the requirement in a way that preserves the reason this architecture, dependency, behavior, or design was chosen in the first place?

A CONFLICT or UNCERTAIN result blocks implementation until resolved.

## Repository strategy

### `S-Pillow/orion-personal-ai`

Canonical Orion integration/control repository for the current architecture, HUD, Orion-owned glue, acceptance evidence, reproducibility instructions, lifecycle controls, and dependency qualification records.

### `S-Pillow/iai-personal-memory-engine`

Compatibility/tracking fork of `CodeAbra/iai-personal-memory-engine`. Narrow Windows compatibility fixes may be carried only when stock behavior cannot satisfy Orion while preserving iai semantics.

### `S-Pillow/jarvis_ai`

Reference/code-donor fork. Reuse only proven patterns that still close a current Orion requirement without duplicating Hermes/iai functionality.

## Security and evidence rules

- Never commit Discord tokens, API keys, `.env` files, iai encryption keys, decrypted memory exports, private vault contents, runtime data, generated training corpora, or large model-training feature arrays.
- Never print secret values into acceptance evidence; presence/length checks are sufficient.
- Distinguish observed runtime evidence, source-confirmed behavior, documentation claims, and hypotheses.
- Preserve/hash consequential artifacts before evaluation or mutation.
- Do not treat historical Docker acceptance as native-Windows acceptance.
- Do not update Hermes, Ollama, or iai merely because a newer release exists; qualify dependency changes separately.
- Keep consequential actions behind explicit operator authority and visible approval boundaries.
- Keep GitHub documentation aligned at meaningful accepted checkpoints so the repository resume point does not drift behind actual work.

## Resume point

P5-02M remains the integration/design-freeze review surface in PR #27. P5-02N source wiring is accepted at qualified code head `faf8b4787d8e6fb668eb5e9d754104910b4b401a`, and P5-02O installed-but-disabled qualification is accepted on `feature/orion-phase5-p5-02o-installed-disabled-qualification`.

The installed COMPANION runtime now carries the P5-02N-qualified `0.2.0` guarded wrapper while production mutation remains disabled and Hermes remains manual-off.

P5-02P production-canary readiness is accepted. The deterministic registered-dispatch proof passed with a real fresh human `once` approval and no production executor call; the controlled canary `C:\Personal\Me\_Orion-P5-Canary.md` was created under separate authorization; and read-only readiness froze pre-edit Windows file identity `5e1aeb8a1aeb5d91:cba20a00000012000000000000000000`, before SHA-256 `ddb08a8ca9ab5d06185a692182a742210817cba1d5523c841d6a371dfdb57b4c`, after SHA-256 `86e94184ef6ff2a80f5cdfa04749c42328079e029d153d3a23d42eab05059e19`, and exact diff SHA-256 `6642d44372449d01e1ec3f5d325bd2b372f52cc58610293bcccf0e4e4ec996e8`.

P5-02Q is accepted as the first real Orion production mutation. Exactly one `edit_note` changed the controlled canary to the frozen after-hash through the registered guarded wrapper and a fresh human `once` approval. Recovery ID `33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f` remains valid historical evidence.

P5-02R is accepted as the first production restore qualification. The exact P5-02Q canary edit was restored to the original before-hash through the registered guarded wrapper and a fresh human `once`. New restore recovery ID `1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27` is valid/committed; the origin P5-02Q record reads `committed_then_changed`; recovery count is 2 with zero attention. Mutation mode is disabled and Hermes is manual-off.

P5-02S production-move readiness is accepted. P5-02T then completed the first bounded production `move_draft` through the registered guarded apply path and a fresh human `once` approval: inbox source `C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md` is absent, vault target `C:\Personal\Me\_Orion-P5-Move-Canary.md` is present at SHA-256 `132ff51d62fd7fd8827d7222e233617e92c55dc21d40ff68164f2238ba0fd132`, new recovery ID `8f79ba8396c2c5877bc9c28c8a5cdbfa55dda850c70ce18c324524d8a5e461a6` is valid/committed, recovery is 3 records / 0 attention, mutation mode is disabled, and Hermes is manual-off. P5-02U remains separately authorization-gated.

Any fixture creation, production move, move-source restore, delete, or recovery cleanup requires a new explicit authorization.

The safe project-status shorthand is:

> Phase 3 presentation foundation accepted; Phase 4 voice work partially accepted with final live TTS/barge-in and wake disposition deferred; Phase 5 source/runtime safety is accepted through P5-02T, including the first bounded production edit, first production restore qualification, and first bounded production move; mutation mode is disabled, P5-02U remains separately authorization-gated, and Hermes remains manual-off.
