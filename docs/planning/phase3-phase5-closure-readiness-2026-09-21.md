# Orion Phase 3–5 Closure Readiness Plan

Status: planning / source-only readiness package  
Date: 2026-09-21  
Controlling product baseline: ORION Master PRD v2.8  
Runtime baseline: Hermes v2026.8.27 / package 0.20.6 / accepted commit 5fc308a70719a83cccdbba4c0e39c23f5a8239d5; iai-pme 3.0.8; manual-off lifecycle

This plan is intentionally conservative. It does not authorize a Hermes/iai/Ollama upgrade, a live COMPANION plugin install, a gateway/profile mutation, a real vault/inbox mutation, or a merge. It defines the shortest path that can actually satisfy the accepted requirements, including negative-path and rollback evidence.

## Executive disposition

Three workstreams remain materially open:

1. **Phase 3 closure:** P3-01 through P3-05A are merged/accepted, but the explicit visible summon/display path is still missing. The Phase 3 presentation foundation is real; the phase should not be declared fully closed until a bounded summon surface is implemented and exercised.
2. **Phase 4 closure:** the accepted P4-04A audio compatibility layer works and Push-to-Talk/STT/session routing are substantially proven, but live audible TTS, Speak Replies OFF, interruption of audible playback, and final wake disposition remain open. Custom `Hey Orion` v1/v2 are rejected; do not train v3 under the same approach merely to chase the gate.
3. **Phase 5 closure:** P5-01 is merged at `33c39d4`. P5-02A has materially improved approval integrity, but the real apply tool remains intentionally non-mutating. Source-only approval concurrency, exact-display, disposable mutation, recovery, then progressively more realistic installation/mutation gates are still required.

The recommended execution order is **finish P5-02A approval integrity -> source-only P5 mutation engine -> Phase 3 summon shell/display tool -> stable-connectivity Phase 4 live acceptance -> live preview-only P5 install -> disposable live mutation -> one bounded real-vault mutation -> remaining draft/delete/display closure**. This ordering prevents us from installing a write-capable plugin before its authorization and recovery path is independently proven.

## Phase 5 work breakdown

### P5-02A — approval integrity, source only

Current evidence already includes fresh nonce-bound plans, exact cached bytes/diffs, a private per-attempt approval key, a `post_approval_response` observer, real pinned-Hermes dispatcher probes, warning-free plugin doctor, full HUD approval-description rendering, simulated DENY/ALLOW ONCE routing, and clean Ctrl+C fixture shutdown. The registered `orion_vault_apply_plan` handler must remain the refusing placeholder through this gate.

Closure evidence still required:

- run the expanded disposable-root suite after the new concurrent-attempt and late-callback tests;
- rerun the installed-Hermes dispatcher probe after those tests are merged forward;
- explicitly record that the operator visually saw the canonical target, literal markup, end-of-diff marker, and final no-newline marker on the isolated HUD card;
- prove two simultaneous approval attempts for the same public plan cannot authorize each other;
- prove a late observer callback cannot resurrect a removed attempt;
- prove attempt-cache saturation fails before calling the approval gate;
- keep session/always, yolo, cached grants, cron/single-query auto-approval, missing observer, callback exception, redaction change, timeout, and pre-dispatch exception fail-closed.

If any case produces a protected-write authorization without a fresh matching human `once`, stop. The fallback is a separately qualified Hermes-core protected-tool contract, not a weaker plugin convention.

### P5-02B — disposable mutation engine, still unregistered

Implement the mutator as a private/source-only candidate first. Do not wire it to the registered apply tool.

**Edit protocol**

- re-resolve the canonical target immediately before write;
- reject changed canonical identity, reparse point, missing target, hash drift, expired/consumed plan, or changed diff/proposed bytes;
- materialize the proposed bytes into a same-directory temporary file with exclusive creation;
- flush and `fsync` the temporary file;
- create recovery evidence before replacement;
- on Windows, prefer `ReplaceFileW` for the final replacement because it is a single Windows replacement operation and preserves original metadata/ACL-related attributes better than a naïve unlink/rename sequence;
- verify the resulting target hash;
- never silently overwrite after a post-write mismatch; preserve recovery evidence and return a failed/recovery-required result.

**Move-draft protocol**

The source and target are separate policy roots, so a move must not assume POSIX rename behavior. The accepted donor semantics already favored exclusive target creation + verification.

- revalidate source containment, draft markers, source hash, target containment, target absence, and target-parent identity;
- first slice should require an existing target directory; directory creation is a distinct approved side effect and should not be silently added;
- create the target exclusively so an intervening file wins and Orion fails closed rather than overwriting it;
- flush + `fsync`, then verify the target hash;
- re-read the source hash immediately before source removal;
- remove the source only if both source and target still match the approved bytes;
- record a small recovery journal before target creation and mark completion only after source removal;
- if a crash occurs after target creation but before source removal, recovery should identify a safe duplicate state rather than guessing which copy to delete;
- if the configured roots ever move to different Windows volumes, fail closed until cross-volume behavior receives a separate acceptance design.

### Windows final-identity hardening after the first candidate passes

The current source candidate re-reads the draft hash immediately before `unlink`, which is a good stale-state guard but still leaves a small path-based TOCTOU window between final read and deletion.

Before enabling a production move handler, qualify a Windows handle-held variant:

- open the approved source with `CreateFileW` using read + delete access and a sharing mode that does not permit conflicting write/delete/rename while the operation is in flight;
- record the file identity from the open handle (volume serial + file ID) and compare it to the preview/final path identity where appropriate;
- read/verify the approved bytes through that held identity;
- create and verify the target;
- request source deletion through the same held handle using `SetFileInformationByHandle(FileDispositionInfo)`, then close;
- classify sharing violations as a safe stale/busy failure, not an instruction to fall back to path-based deletion.

Microsoft documents that omitted `FILE_SHARE_DELETE` prevents later delete/rename opens while the handle is held, and that volume serial + file ID identify a file on the local computer. This materially narrows the accidental editor/sync race without pretending same-user processes are sandboxed.

Do not merge this mechanism into the active source candidate until its existing Windows baseline passes; otherwise a new Win32 layer would make a basic logic failure harder to isolate.

Required fixture failure injection:

- before temp/exclusive create;
- after recovery snapshot/journal creation;
- after target/replacement write but before verification;
- after target verification but before source deletion;
- simulated sharing violation / permission error;
- target appears between validation and create;
- source changes between target creation and delete;
- post-write hash mismatch;
- recovery-artifact write failure;
- cleanup failure.

A failed operation must be classifiable as **no mutation**, **safe committed state**, or **recovery required**. Do not return a generic success/failure that hides ambiguous disk state.

### P5-02C — exact preview + mutation contract completion

Before activation, add/close the remaining product-contract surfaces:

- read exact contained Markdown notes through a bounded deterministic tool;
- use iai for semantic retrieval/ranking; do not add Orion embeddings or a second semantic search engine;
- create new drafts only inside the dedicated Orion inbox using exclusive creation;
- edit and move use the approved plan token only;
- deletion is a separate tool/plan/approval class and must not inherit edit/move authority;
- recovery/restore is explicit and must bind the artifact/hash it restores;
- every mutation result reports canonical target, before/after hashes, recovery evidence, and whether a mutation actually occurred;
- no browser filesystem authority.

### P5-03 — preview-only COMPANION installation

This is the first live-plugin gate and requires explicit owner authorization.

Install the exact reviewed plugin commit into the COMPANION profile, grant only `mcp_allowlist: ["iai-mcp"]`, restart through the supported Orion/Hermes lifecycle, run doctor/health, and exercise only read/recommend/preview behavior while the registered apply handler still refuses mutation.

Rollback boundary:

1. stop/disable the plugin through supported configuration;
2. restore the previous COMPANION config/plugin directory from named backup;
3. restart through the supported lifecycle;
4. verify Hermes health, typed HUD, iai, and manual-off behavior.

If profile config, plugin discovery, credential ownership, MCP allowlist, or typed HUD behavior changes unexpectedly, rollback before proceeding.

### P5-04 — real Hermes approval, no write

With the live plugin still non-mutating:

- trigger one real edit preview on a disposable Windows tree;
- inspect the real Hermes -> HUD approval request end to end;
- DENY: no write;
- new preview -> ALLOW ONCE: handler still reports no mutation;
- try stale preview/replay;
- verify session/always are not accepted by the handler-side fresh-once contract;
- verify no approval detail leaks to unintended configured surfaces before enabling private-vault diffs.

This gate exists because the simulated HUD fixture and the installed-Hermes dispatcher probe validate different halves of the path.

### P5-05 — first approval-bound mutation on disposable Windows roots

Only after P5-02B/C and P5-04 pass should the registered handler call the mutation engine.

Use dedicated disposable directories, not `C:\Personal\Me` or `C:\Personal\Orion-Inbox`.

Run:

- approved edit;
- denied edit;
- stale edit;
- replay;
- approved move;
- target-race move;
- source-race move;
- forced failure/recovery;
- process interruption at documented failpoints where practical.

One human `once` must authorize one attempt only. Every other path must be no-write or explicitly recoverable.

### P5-06 — bounded real-vault acceptance

Requires a new exact authorization unit naming the file/draft and maximum mutations.

Preconditions:

- current backup known good;
- exact plugin/commit installed;
- no unresolved disposable-root defect;
- manual-off lifecycle stable;
- chosen test file/draft has a separately captured original hash/content.

Perform one small operation, verify target bytes/hash, verify Obsidian visibility, verify recovery/rollback, and return to clean manual-off. Do not bundle edit + move + delete into one first live smoke.

### P5-07 — deletion/restore, draft creation, and display tools

Deletion remains separately approval-gated. Prefer recoverable quarantine/backup semantics over irreversible deletion where compatible with the PRD, but do not call that “delete” unless the user-facing contract is explicit.

Inbox draft creation may be automatic only under the dedicated inbox root and must use exclusive creation to avoid overwriting an existing draft.

The display tool should be capability-bounded. Pinned-Hermes source review found that the existing session SSE already forwards `tool.started` with redacted/display-safe tool arguments to the HUD; the accepted pin's `tool.completed` event does not forward the result. Therefore Orion can use the bounded `orion_display` arguments themselves as the summon payload over the existing Hermes -> bridge -> HUD stream, with no second callback server/token. The donor Jarvis `hud_display` proves the UX value but POSTs to its own summon endpoint, accepts arbitrary iframe/media URLs, and broadcasts to every open HUD. Orion V1 should instead begin with one local panel and typed `text` / `evidence` / `link` payloads, no arbitrary HTML/iframe, and no implicit broadcast. Future rich media and device routing remain explicit later gates.

## Phase 3 closure plan

P3-01 through P3-05A already establish the Core, adaptive workspace, Memory Lens/Brain handoff, provenance/authority, and composition. The remaining closure item is the **summon/display surface**.

### P3-05B — summonable panel shell

Implement the rendering shell before agent authority:

- a dedicated center-workspace summoned panel with explicit title, kind, source/provenance, dismiss control, and focus/gaze state;
- deterministic state: summon -> active workspace focus -> Core gaze/focus cue -> dismiss -> prior/default workspace;
- no camera or vision implication;
- no lifecycle or filesystem authority;
- no arbitrary HTML injection.

Content security policy:

- render plain text/evidence with `textContent`;
- images/media use validated URL/data types and existing CSP extensions only when needed;
- arbitrary remote webpages should default to link/open behavior rather than privileged embedding;
- if iframe embedding is later allowed, use a sandbox with the minimum permissions and never combine same-origin + script privileges casually;
- keep remote embed origins allowlisted; do not convert the HUD into a general-purpose browser proxy.

Acceptance:

- synthetic fixture summons and dismisses content;
- panel is visible and keyboard accessible;
- Core gaze/state follows active summoned content;
- normal Conversation/System/Memory state survives summon/dismiss;
- reduced-motion path works;
- no credential, shell, filesystem, or lifecycle authority is introduced.

### P3-05C / Phase-5 integration — explicit display tool

A Hermes display tool then produces only the bounded display payload consumed by the P3-05B shell. Keep this tool separate from vault mutation authority. If transport requires a local Orion endpoint, authenticate it through the existing loopback/UI/server boundary rather than putting a secret in browser assets.

Once a real tool call visibly summons content and the acceptance criteria pass, update the Phase 2 administrative status and Phase 3 status together. Until then, call Phase 3 “presentation foundation merged/accepted,” not fully closed.

## Phase 4 closure plan

### P4-04B — stable-connectivity audible voice acceptance

Current direct recovery evidence already shows Edge TTS and the P4-04A TTS->STT round trip can work without an Orion/Hermes code change. Final acceptance should distinguish provider/network failure from Orion failure.

Preflight sequence:

1. direct `edge_tts` control call;
2. direct P4-04A audio smoke;
3. Phase 4 wrapper status with `audio_api=true`;
4. JLab microphone permission/capture;
5. PTT -> Hermes STT -> same persisted session -> visible streamed reply;
6. audible TTS from that reply;
7. turn Speak Replies OFF and prove the next PTT reply stays visible but silent;
8. turn speech back on, start an audible response, press PTT during playback, and prove audio stops and the active run is stopped/cancelled without stale speech resuming.

Record timestamps for PTT press -> audible stop where practical. If Edge/provider fails while direct control also fails, classify it as provider-path unavailable and do not patch Orion. If direct control passes but Orion fails, investigate wrapper/gateway/client path.

The existing design already uses sentence-sized TTS chunks and bounded extended STT/TTS timeouts. Keep those protections; current Hermes upstream has reported long-text TTS failures around short hardcoded client timeouts, so reverting to one giant TTS request would be a regression.

### P4-07 — visible privacy-state acceptance

Verify states from actual events, not labels alone:

- VOICE OFF;
- PUSH TO TALK / idle;
- CONVERSATION / listening;
- transcribing;
- speaking;
- WAKE OFF while wake is disabled;
- mic denied / STT failure / TTS failure -> typed fallback remains usable.

Confirm the MediaStream tracks stop after each recording, after the 20-second cap, on failure, and on page unload.

### P4-08 — bounded follow-up

For the accepted PTT interim mode, the safest automatic follow-up limit is **zero**: every additional spoken turn requires another button press. This is inherently bounded and avoids an ambient-noise self-conversation loop.

If hands-free wake mode is later accepted, it needs its own finite no-speech/VAD timeout and automatic-turn cap before enabling continuous follow-up.

### P4-09 — interruption semantics

A click/PTT that merely mutes playback is insufficient. Acceptance should prove:

- active `Audio` playback is stopped;
- any in-flight TTS fetch is aborted;
- queued speech from the interrupted response cannot resume;
- active Hermes generation is stopped when applicable;
- the next turn does not behave as though the unheard remainder was spoken.

If Hermes session state already records cancellation adequately, use it. Do not invent hidden conversational text unless testing shows the runtime otherwise loses interruption state.

### Wake disposition

Do not launch a third custom openWakeWord training run under the same design.

The rejected v1/v2 results are far below the working live-detection gate, and openWakeWord’s own guidance emphasizes realistic positive data, large negative/adversarial sets, deployment-environment false-positive measurement, and threshold/verifier tuning. More training without a materially changed experiment is not evidence-based.

Evaluate in this order:

1. inspect the **accepted v0.20.6 installed source** for a supported stock/open-vocabulary path that can satisfy “Hey Orion” without a dependency change;
2. if a supported stock phrase is technically strong but not “Hey Orion,” treat phrase change as an explicit owner/product decision rather than silently weakening OR-VOICE-006;
3. current upstream Hermes documents a Sherpa open-vocabulary “any phrase” engine, but that is a candidate capability until the accepted pin is checked. If it requires a Hermes upgrade, open a dependency-qualification ticket and price the regression cost before changing the pin;
4. retaining PTT and deferring wake is valid operationally, but closing PRD Phase 4 without wake would require an explicit scope/PRD disposition, not an administrative shortcut.

Any wake candidate must pass realistic JLab/room testing for intended detections and extended ambient false positives, including background speech/media. Community reports reinforce that media speech is a common custom-wake failure mode; treat that as a test condition, not proof of a specific Orion defect.

## Negative-path matrix

| Area | Failure | Required behavior |
| --- | --- | --- |
| Approval | yolo/auto/cached/session/always | no fresh-once marker -> no write |
| Approval | observer/dispatcher exception | no positive receipt -> no write |
| Approval | concurrent/late callback | isolated private attempt key; late event inert |
| Approval UI | diff changed/truncated/redacted | refuse protected write |
| Edit | stale hash/path/reparse | fail before temp/replace |
| Edit | replace/verify failure | preserve recovery evidence; never claim success |
| Move | target race | exclusive create fails; source preserved |
| Move | source changes after target create | do not delete source; clean target only if still provably ours |
| Move | crash between target-create/source-delete | journal identifies duplicate/recovery state |
| TTS | Edge/network unavailable | typed fallback; direct control distinguishes provider path |
| TTS | long response | chunked speech + bounded extended timeout |
| Barge-in | abort during fetch/playback | abort fetch, stop audio, invalidate queue epoch, stop active run |
| Wake | false positives from speech/media | threshold/engine/data decision; do not lower gate to pass |
| Display | malicious/untrusted content | text-safe rendering or sandbox/allowlist; no arbitrary privileged embed |
| Display | multiple HUDs later | target one stable client; broadcast explicit |
| Lifecycle | any new feature tries to start/supervise runtime | reject; preserve manual-off/vendor ownership |

## Research notes informing the plan

Primary/upstream references reviewed on 2026-09-21:

- Hermes current wake-word docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/wake-word
- Hermes Windows long-text TTS timeout report: https://github.com/NousResearch/hermes-agent/issues/53161
- openWakeWord training configuration: https://github.com/dscripka/openWakeWord/blob/main/examples/custom_model.yml
- openWakeWord custom verifier guidance: https://github.com/dscripka/openWakeWord/blob/main/docs/custom_verifier_models.md
- openWakeWord evaluation principles: https://github.com/dscripka/openWakeWord
- Microsoft ReplaceFileW: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew
- Microsoft MoveFileEx: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexa
- MDN iframe sandbox guidance: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe
- OWASP HTML5 sandbox guidance: https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
- Jarvis donor display pattern: https://github.com/eadmin2/jarvis_ai

Community evidence was used only as test-idea input, not as authority. Recent and historical Home Assistant/openWakeWord threads repeatedly report background speech/media as a false-wake stressor; Orion should therefore include TV/conversation/ambient audio in wake acceptance.

## Tomorrow’s shortest productive sequence

1. Pull the current P5-02A branch and run the expanded source tests plus dispatcher probe and doctor.
2. If they pass, record P5-02A concurrency/late-callback acceptance and explicitly confirm the prior human visual diff markers.
3. Implement/review P5-02B disposable mutation engine with failure injection; keep the registered handler disabled.
4. In parallel source work, open P3-05B for the safe summonable-panel shell so Phase 3’s last presentation gap has a home.
5. When connectivity is stable and Steven is at the machine, run issue #19’s final live PTT/TTS/Speak-Off/audible-interruption gate.
6. Only after source mutation + real approval/no-write gates pass, request the separate live P5 install authorization.

No phase should be closed merely because the remaining work is inconvenient. The closure standard is that the named requirement has observable evidence, a failure path, and a rollback/recovery path.
