# P3-05B Summonable Presentation Shell

Status: **SOURCE CANDIDATE / NO AGENT TRANSPORT / VERIFICATION PENDING**  
Date: 2026-09-21  
Tracks: issue #24  
Controlling PRD: ORION Master PRD v2.8

## Purpose

P3-01 through P3-05A established the Orion Core, adaptive Conversation/System/Memory workspace, Memory Lens/IAI Brain handoff, provenance/authority indicators, and composition. The remaining presentation acceptance gap is a visible summonable content surface.

P3-05B implements only the **presentation shell**. It does not register a Hermes display tool, add a browser/API route, expose a credential, fetch remote content, or add filesystem/lifecycle authority.

## Design

The summon surface is deliberately **not a fourth workspace**.

The accepted workspace set remains:

- Conversation
- System
- Memory

A summon overlays the currently selected workspace and preserves that selection underneath it. Dismiss returns to the same selected workspace. This matches the PRD requirement that summoned content may take focus without forcing navigation to an unrelated page.

### Supported source-candidate payload kinds

- `text`
- `evidence`
- `link`

The shell bounds title, source, body, and link sizes. Link payloads accept only HTTP/HTTPS. There is no raw HTML kind and no iframe/media embed in this slice.

Text/evidence is rendered through `textContent`. HTML-looking strings remain literal.

## Focus and Orion Core behavior

`workspace-state.js` now distinguishes:

- `normal`
- `summon`
- `approval`

The controller tracks summon and approval independently. **Approval always wins** if both are active. When approval clears, an otherwise-active summon regains summon focus.

The Orion Core receives `data-presentation-focus="summon"` for a presentation-only gaze cue. P3-05B does not change `data-core-state`, call `setCore()`, or fabricate tool/agent activity.

## Security boundary

`summon-state.js` contains no:

- `fetch`
- XMLHttpRequest/WebSocket/EventSource
- local/session storage
- media capture
- cookies
- `innerHTML` / `insertAdjacentHTML`
- eval/dynamic Function
- iframe handling

The panel's external link uses `target="_blank"` with `rel="noopener noreferrer"`.

Remote webpages/video/image embedding are intentionally deferred until the content-origin/privacy/sandbox policy is separately defined. This avoids turning Orion's HUD into a general-purpose privileged browser surface merely to close the summon requirement.

## Source changes

- `hud/static/summon-state.js` — bounded renderer/controller.
- `hud/static/index.html` — accessible summon panel with dismiss control.
- `hud/static/styles.css` — overlay/focus/gaze presentation.
- `hud/static/workspace-state.js` — approval-over-summon focus arbitration.
- `hud/static/app.js` — installs presentation controller only; no transport.
- `hud/orion_hud_bridge.py` — static module allowlist only.
- `hud/tests/test_phase3_summon.py` — architecture/security contracts.
- `hud/tests/test_summon_rendering.cjs` — executable literal-markup, link, bounds, focus, and dismiss behavior.

## Verification gate

This source candidate has not been executed in the ChatGPT environment. Run on Windows after pulling the branch:

```powershell
& "C:\Users\spill\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" `
  -m unittest discover `
  -s "D:\Orion\orion-personal-ai\hud\tests" `
  -p "test_*.py" -v

node --test "D:\Orion\orion-personal-ai\hud\tests\test_summon_rendering.cjs"
```

Also run syntax checks:

```powershell
node --check "D:\Orion\orion-personal-ai\hud\static\summon-state.js"
node --check "D:\Orion\orion-personal-ai\hud\static\workspace-state.js"
node --check "D:\Orion\orion-personal-ai\hud\static\app.js"
```

A browser fixture/manual check should then prove:

1. selected Conversation/System/Memory workspace is preserved;
2. text/evidence shows literal markup safely;
3. link renders only an HTTP/HTTPS destination;
4. panel is keyboard focusable and dismissible;
5. Core gaze/presentation focus changes while operational state remains truthful;
6. approval focus visibly overrides summon focus;
7. reduced-motion behavior remains acceptable.

## P3-05C / Phase 5 display-tool seam

Do **not** mark the entire Phase 3/§16.3 summon acceptance closed from P3-05B alone.

The next slice must create an explicit bounded Hermes display path that carries a validated payload to this shell. That tool/transport must preserve:

- loopback-only HUD boundary;
- browser has no Hermes API key;
- no arbitrary proxy;
- no raw HTML/JS;
- one intended HUD target for MVP;
- no implicit broadcast-to-all semantics;
- display authority separate from vault mutation authority.

The Jarvis `hud_display` plugin is a donor/reference for interaction semantics only.

Once a real Hermes display action visibly summons content through the accepted HUD and negative-path tests pass, Phase 3 can be closed together with the lingering Phase 2 §16.3 summon criterion.

## Rollback

P3-05B is frontend/static-source only plus a static-file allowlist entry. Rollback is reverting this branch/commit set. It changes no COMPANION config, Hermes pin, iai state, scheduled task, credential, or vault data.
