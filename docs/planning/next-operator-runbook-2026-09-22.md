# Orion Next Operator Runbook

Date prepared: 2026-09-21  
Purpose: highest-information next actions; no live vault mutation is authorized by this runbook.

## 1. P5 first: qualify the latest disposable source candidate on Windows

Why first: the P5 candidate contains the most platform-specific and safety-critical code (NTFS path/reparse checks and native ReplaceFileW). A Windows result gives more information than another design review.

From the existing P5 branch checkout:

```powershell
git -C "D:\Orion\orion-personal-ai" pull --ff-only

git -C "D:\Orion\orion-personal-ai" status --short
git -C "D:\Orion\orion-personal-ai" rev-parse --short HEAD

& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  -m unittest discover `
  -s "D:\Orion\orion-personal-ai\hermes_plugins\orion-vault-actions\tests" `
  -p "test_p5*.py" -v
```

Expected current discovery: 37 tests. Record the actual count and HEAD rather than forcing that expectation if the branch fast-forwards again.

Stop/route:

- all pass -> continue to dispatcher;
- one or more skip only for unavailable symlink/junction creation -> record exact skip and evaluate whether Windows junction coverage still ran;
- failure in ReplaceFileW, recovery classification, live-root guard, race test, or approval-attempt isolation -> stop P5 progression and fix that class before any live install discussion.

Then:

```powershell
& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  "D:\Orion\orion-personal-ai\hermes_plugins\orion-vault-actions\tests\probe_hermes_dispatch.py"

& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe" `
  -p companion plugins doctor `
  "D:\Orion\orion-personal-ai\hermes_plugins\orion-vault-actions" --ci
```

The gateway does not need to be started merely for source doctor.

Do **not** install/enable the plugin or point the disposable mutator at the live vault/inbox.

## 2. If P5 passes: record the human visual evidence we actually have

The isolated HUD terminal routing passed DENY and ALLOW ONCE and Ctrl+C shutdown.

Before marking exact-display acceptance complete, answer only from what was actually seen:

- canonical target visible;
- literal `<b>` text visible as text;
- scrolled through `END-OF-DIFF-100`;
- final no-newline marker visible.

If any item was not consciously checked, rerun the isolated fixture later. Do not infer visual evidence from logs.

## 3. Wake: inventory the pinned Sherpa path without changing it

After P5 evidence is captured, use the planning branch in a separate clean checkout/worktree or temporarily switch only if the current tree is clean.

Read-only preflight:

```powershell
& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  "D:\Orion\orion-personal-ai\scripts\phase4\p4-sherpa-readonly-preflight.py"
```

This should only fingerprint installed source, report dependency/model-cache presence, and show the wake-only config subset. It must not install, download, enable wake, open the microphone, or write config.

Interpretation:

- accepted source blob + dependencies/model cache present -> offline/live Sherpa evaluation can proceed without dependency work;
- accepted source but dependency/model missing -> separately decide whether a supported lazy install/model download is authorized; absence is a prerequisite, not a failed goal;
- source mismatch -> investigate installed-runtime provenance before wake tuning.

Do not repeat the old 0.5/0.4 Sherpa screen and expect a new result. The next meaningful experiment is a fixed JLab positive/ambient corpus and an offline threshold/score grid.

## 4. Phase 4 audible acceptance when connectivity is stable

Issue #19 remains a human/audio gate, not a code-writing task.

Sequence:

- direct Edge/provider control;
- direct P4-04A audio smoke;
- PTT -> STT -> same session -> visible reply -> audible TTS;
- Speak Replies OFF -> visible but silent reply;
- speech ON -> start audible reply -> press PTT while speaking;
- confirm audio stops, queued stale speech does not resume, and active Hermes run stops where applicable.

If direct provider control fails at the same time, classify provider path unavailable and do not patch Orion.

If direct provider control passes and Orion fails, investigate the wrapper/browser path.

## 5. Phase 3 display path after P5/voice evidence

The planning branch contains a 7/7-tested pure summon-state prototype and the SSE-native transport contract.

Next implementation branch should:

- integrate the safe controller into the center workspace;
- render text/evidence/link with textContent and explicit links;
- recognize only `orion_display` / `orion_display_dismiss` tool-start events;
- preserve/restore prior workspace and Core gaze/focus;
- add DOM/accessibility + isolated SSE fixture tests.

Do not start with iframe/video/broadcast. Those can be added after the basic visible handoff proves value.

## Evidence to paste back

For the next chat, the most useful single artifact is the complete terminal output from step 1: HEAD, 37-test discovery, dispatcher probe, and doctor.

That output determines whether the next P5 action is hardening, fixing, or progressing to the real no-write Hermes-to-HUD approval gate.
