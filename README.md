# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion for **native Windows 11**. The accepted foundation uses a pinned Hermes Agent runtime, the named `companion` profile, a local Ollama model, Discord, a loopback Hermes API, native iai persistent memory, and an Orion-owned local HUD/presentation layer.

## Controlling baseline

The controlling product requirements document is **ORION — Master PRD v2.8**, approved 2026-09-10.

Canonical artifact and approval record:

- `docs/prd/orion-master-prd-v2.8-ai-optimized-approved.docx`
- `docs/prd/orion-master-prd-v2.8-approval-record-2026-09-10.md`

PRD v2.8 supersedes v2.7. It preserves the accepted native-Windows/manual-off foundation while defining Hermes as the runtime and preferred native voice/wake authority, iai as the persistent-memory authority, and Orion as the living visual control-and-presentation layer.

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

### Phase 5 - vault safety chain accepted through P5-02L

Phase 5 has advanced through source qualification, preview-only COMPANION installation, installed-runtime disposable mutation qualification, production recovery-root acceptance, recovery-root persistence, and live runtime-ingestion verification.

Accepted checkpoints:

- P5-01: native plugin contract, canonical containment, side-effect-free edit/move previews, iai-backed destination recommendation, and a fail-closed public apply placeholder;
- P5-02A through P5-02G: exact approval payloads, fresh handler-side `ALLOW ONCE` evidence, disposable edit/move/restore execution, restart-safe non-authorizing receipts, recovery classification, Windows file-identity hardening, and source-qualified production guardrails;
- P5-02H: exact plugin installed and enabled in COMPANION with `mcp_allowlist: ["iai-mcp"]`, while public apply remained fail-closed;
- P5-02I: installed plugin qualified against disposable roots for edit, move, stale-state refusal, replay refusal, restart classification, historical restore, and controlled failure classification;
- P5-02J: production recovery root created and ACL-qualified with production mutation still disabled;
- P5-02K: accepted recovery-root path persisted append-only in COMPANION `.env`, with rollback captured and no mutation-mode setting persisted;
- P5-02L: live COMPANION runtime ingested the persisted recovery root, exposed the expected four-tool `orion_vault` toolset, retained `mutation_allowed=false`, and returned to manual-off.

Current installed/runtime boundary:

- installed plugin source is the P5-02I-qualified source at `ce676a263f3dd2c18a7d7700b17a6023c6845904`;
- installed `__init__.py` SHA-256 is `FCFA3DDC4A86B99691FB003CF4421027C5CC3CA22AC99ADBCCEEE8D3B3C7B5DA`;
- `ORION_P5_PRODUCTION_RECOVERY_ROOT` is persisted and runtime-qualified;
- `ORION_P5_MUTATION_MODE` is not persisted and resolves to `disabled`;
- registered `orion_vault_apply_plan` still points to `apply_plan_placeholder` and returns `p5_01_mutation_not_authorized`;
- `_execute_production_plan_candidate()` exists only as a private, unregistered candidate;
- production recovery inventory was empty at P5-02L closure;
- no production vault/inbox mutation has been authorized or performed.

P5-02L closure commit:

`243f778a2a09a4a9f2c603c437e8b94149d52e2b`

The next boundary is not routine activation. P5-02M froze the repository and registration design without a live runtime change. P5-02N is the separately authorized source-only wiring unit: it may register the guarded wrapper in repository source and add regressions, but installation, mutation enablement, and the first real vault/inbox action remain separate authorization units.

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

Any newer Hermes, iai, Ollama, model, or presentation dependency is a **candidate** until separately qualified under PRD v2.8. Do not replace an accepted dependency merely because a newer release exists.

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

P5-02M is prepared as the complete integration/design-freeze review surface in draft PR #27. **P5-02N source wiring is the current authorized work unit** on `feature/orion-phase5-p5-02n-registered-wrapper`.

P5-02N is source-only:

1. register the named `apply_plan_production_guarded` wrapper in repository source while keeping `_execute_production_plan_candidate()` private;
2. keep the public apply schema `plan_token`-only;
3. block missing/disabled/preview-only/invalid mutation modes before approval or executor delegation;
4. permit delegation only under explicit `mutation_enabled`, with the private executor retaining the one fresh Hermes human `ALLOW ONCE` gate and existing recovery/staleness controls;
5. bump the plugin manifest to `0.2.0` and add/refresh the required regressions;
6. make no installed-plugin, COMPANION config, `.env`, Hermes lifecycle, vault, inbox, or production-recovery change.

The accepted installed/runtime state remains P5-02L until a separately authorized P5-02O installed-but-disabled qualification replaces it. P5-02N source wiring does not enable production mutation.

The safe project-status shorthand is:

> Phase 3 presentation foundation accepted; Phase 4 voice work partially accepted with final live TTS/barge-in and wake disposition deferred; Phase 5 installed/runtime safety qualification accepted through P5-02L; P5-02M freezes the production registration design; P5-02N source wiring is in progress; production mutation remains disabled.
