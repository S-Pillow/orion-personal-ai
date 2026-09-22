# Orion Personal AI

Orion is a privacy-first, local-first personal AI companion for **native Windows 11**. The accepted foundation uses a pinned Hermes Agent runtime, the named `companion` profile, a local Ollama model, Discord, a loopback Hermes API, native iai persistent memory, and an Orion-owned local HUD/presentation layer.

## Controlling baseline

The controlling product requirements document is **ORION — Master PRD v2.8**, approved 2026-09-10.

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

### Phase 5 — P5-01 native vault contract accepted (source only)

Phase 5 work has started without installing or enabling a new live plugin and without performing any protected vault mutation.

P5-01 source-only work is recorded in issue #20 and PR #21. Owner/operator acceptance was confirmed on 2026-09-21 after Windows verification and review-thread closure.

P5-01 currently establishes:

- a native Hermes plugin shape under `hermes_plugins/orion-vault-actions/`;
- read-only edit and inbox-to-vault move previews;
- canonical Windows path containment after normalization / real-path resolution;
- rejection of traversal, absolute-path escape, symlink/junction/reparse escape, non-Markdown targets, and invalid state;
- immutable SHA-256 preview-plan tokens;
- plan-scoped Hermes `pre_tool_call` approval interception;
- a fail-closed apply placeholder that performs no protected mutation even after approval;
- explicit separation between preview and any future mutation implementation;
- source-only install/rollback boundaries for a later owner-approved P5-02.

Local Windows verification on 2026-09-21 passed:

- P5-01 fixture suite: **13/13 tests passed in 0.133 s**;
- Hermes `plugins doctor ... --ci`: runtime discovery, manifest parsing, import, and registration passed with **4 tools / 1 hook and no warnings**;
- COMPANION user-plugin baseline: `[]` before any Orion plugin install;
- COMPANION MCP inventory shows `iai-mcp` **enabled**;
- a fourth source-only tool, `orion_vault_recommend_destination`, now uses native iai `memory_recall` ordering and `memory_temporal_recall` document tags to derive advisory destination candidates;
- because iai's `doc:` tag is intentionally lossy, Orion accepts a candidate only when that tag maps to exactly one current contained Markdown file; missing or ambiguous mappings are omitted rather than guessed;
- no direct iai store access or second semantic ranker is introduced.

The 13/13 Windows test and earlier Hermes-doctor results above apply to commit `835509f`. Review feedback after PR #21 became ready identified three preview issues: NTFS alternate data stream paths, significant leading whitespace in filenames, and diffs for text without a final newline. Source fixes and three new regression tests are on the PR branch. On Windows at `574c2a3`, Hermes doctor passed with 4 tools / 1 hook; 15/16 tests passed, with one failure caused by the new test fixture leaving a trailing CR from Windows CRLF. The fixture now uses explicit cross-platform CRLF bytes without a terminal newline, and 16/16 tests pass in a disposable non-Windows checkout. The corrected suite passed 16/16 on Windows in 0.139 s at `25cb56b`. Hermes doctor had already passed on the unchanged plugin source at `574c2a3`. P5-01 is accepted at the source-only boundary. P5-02 remains a separate authorization gate.

Important boundary: P5-01 is still **source-only**. No live COMPANION plugin install/enable, Hermes restart for this plugin, vault write, inbox write, move, edit, restore, or delete has been authorized or performed.

Current Phase 5 contract:

`docs/phase5/p5-01-native-vault-contract.md`

### P5-02 approval/mutation safety — source baseline accepted; production activation not yet ready

[Issue #22](https://github.com/S-Pillow/orion-personal-ai/issues/22) and [draft PR #23](https://github.com/S-Pillow/orion-personal-ai/pull/23) now contain the broader P5-02 source/disposable qualification work.

Accepted Windows evidence through P5-02E:

- full `test_p5*.py`: **86/86 passed**;
- installed-Hermes dispatcher probe: **2/2 passed**;
- plugin doctor: **PASS**, 4 tools / 2 hooks;
- exact HUD approval-card visual gate accepted;
- real Hermes fresh human DENY / ALLOW ONCE no-write gate accepted;
- Windows move-path file-ID / held-handle hardening accepted;
- recovery reconciliation and historical restore preview/stale revalidation accepted;
- restart-safe non-authorizing approval/recovery receipts accepted;
- private disposable edit/move/restore transaction behavior, crash classification, and replay refusal accepted.

The registered `orion_vault_apply_plan` handler still refuses all protected mutation. The private disposable executors are not registered, and no live COMPANION plugin install/enable, service restart for this plugin, production recovery-root creation, vault write, inbox write, move, edit, restore, or delete has been authorized or performed.

Production activation readiness is documented in:

`docs/phase5/p5-02f-production-activation-readiness-review.md`

Current readiness decision:

- preview-only COMPANION install may enter a **separate explicit authorization gate**;
- live edit/move/restore activation is **NO-GO** until production recovery-root/ACL validation, mutation-mode/startup gating, dedicated handler-side approval ownership, normal-edit Windows file-ID parity, bounded restart recovery enumeration, production schema/rollback freeze, and installed-runtime disposable qualification are completed.

Do not interpret source/disposable acceptance as live mutation authorization.

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

Continue **Phase 5 / P5-02A source-only work** on draft PR #23, starting with the isolated HUD approval-display check above. Keep final Phase 4 live voice acceptance on issue #19. Live plugin installation and real mutation still require separate authorization.

Immediate sequence:

1. keep PR #16 unmerged until stable-connectivity voice acceptance is completed;
2. treat P5-01 as accepted source-only: Windows source tests passed 16/16 at `25cb56b`, Hermes doctor passed on the unchanged plugin code at `574c2a3`, and owner/operator review is complete;
3. keep destination recommendation advisory and preserve native iai recall ordering rather than introducing a second semantic ranker;
4. preserve the P5-01 source-only boundary — no plugin install/enablement or protected vault mutation is authorized by this acceptance;
5. require a separately approved P5-02 before live plugin installation or any real move/edit/delete/restore behavior;
6. preserve Hermes as the generic approval authority, iai as memory authority, Obsidian as the durable human-authored vault, and Orion as presentation/control.

The safe project-status shorthand is:

> Phase 3 presentation slices P3-01 through P3-05A merged/accepted; Phase 4 voice work partially accepted with final live TTS/barge-in acceptance deferred; Phase 5 P5-01 source-only vault contract accepted; P5-02A source-only approval qualification in progress on draft PR #23; live P5-02 work requires separate authorization.

