# Phase 2 Status — HUD / Companion Interface

Status: **READY FOR DESIGN / COMPATIBILITY DISCOVERY**

Date: 2026-09-09

Controlling baseline: **ORION — Master PRD v2.7**, approved 2026-09-08.

A **v2.8 HUD & Companion Interface** PRD draft has been prepared for owner review. It is not controlling until explicitly approved.

## Entry condition

Phase 1 is **PASS / CLOSED**. Closure was merged to `main` in PR #6 at commit:

`7c55493e0401f1003b3f0f2438e684a5fb144227`

The accepted lifecycle/memory foundation must not be reopened without contradictory evidence.

## Product direction

Orion's HUD should be a distinct companion interface, not a reskinned Jarvis clone.

The current design direction is:

- a central **Orion Core** that acts as the visual face/presence of the assistant
- subtle celestial/masked-face identity rather than a literal Iron-Man reactor
- voice-reactive particles/rings and state-driven eye/core behavior
- lightweight human-like idle motion: blink, eye saccades, small head/parallax drift, breathing/pulse
- adaptive center workspace that expands when Orion needs to present useful content
- compact side rails for runtime, memory, activity, approvals, system status, skills, and automations
- an explicit **IAI Brain** action/workspace
- first-class visible agent activity, STOP/cancel, and approval boundaries
- summonable media/content panels driven by an explicit Hermes tool
- reduced-motion/performance modes from the start

Full 3D facial rigging, photorealistic lip sync, or heavyweight Unreal/MetaHuman rendering is not required for V1.

## Key architecture discovery

The Jarvis reference repo contains a custom Python voice pipeline that performs browser audio capture, partial/final Whisper transcription, Hermes session streaming, TTS, barge-in, approvals, usage tracking, machine telemetry, and media-panel broadcast.

However, the **accepted Orion Hermes pin itself (`v2026.8.27` / package `0.20.6`) already documents native:**

- streaming TTS
- local `faster-whisper` STT
- full-duplex barge-in while thinking or speaking
- interruption awareness in the next model turn
- voice stop phrases
- local wake-word detection
- openWakeWord, sherpa open-vocabulary, and Porcupine wake providers
- custom wake phrases such as a future `hey Orion`
- desktop/client voice surfaces and authenticated profile-scoped voice configuration

Therefore Phase 2 should **validate reuse of Hermes-native voice before adopting Jarvis' separate STT/TTS stack**. Duplicating voice ownership would increase latency, configuration drift, security surface, and lifecycle complexity.

Reference:

`docs/phase2/jarvis-reference-study-2026-09-09.md`

## Proposed implementation sequence

### Phase 2A — Compatibility and typed-control proof

Goal: establish the smallest Orion HUD backend/client without voice duplication.

Acceptance targets:

- document exact Hermes v0.20.6 endpoints/events needed for typed sessions, run IDs, tool events, approvals, STOP, health, sessions, skills, jobs, and voice configuration
- keep Hermes API on loopback and keep bearer credentials out of browser code
- prove typed chat uses the intended persistent Hermes session
- prove live tool/activity events can drive UI state
- prove STOP/cancel fails safely when there is no active run
- prove approval events remain explicit and visible
- prove starting/stopping the HUD does not start/stop Hermes, Ollama, or iai
- record exact installed Ollama version
- no dependency upgrades in this gate

### Phase 2B — Modular Orion HUD shell

Goal: build the real interface structure before cosmetic complexity.

Acceptance targets:

- modular frontend rather than a single monolithic HTML file
- left/right status rails plus adaptive center workspace
- typed chat and live activity feed
- lifecycle/status indicators sourced from observed state only
- STOP and approval UI
- system telemetry
- skills/automations visibility
- responsive 1440p/ultrawide behavior
- reduced-motion mode

### Phase 2C — Orion Core V1

Goal: establish Orion's visual identity with low-cost animation.

V1 behaviors:

- idle breathing/pulse
- randomized blink timing
- small eye saccades
- subtle head/parallax drift left/right
- state-specific eye/core color/intensity
- listening/thinking/tool/speaking/error states
- voice-energy ring/particle response
- motion pauses/reduces when workspace takes priority
- no requirement for full skeletal 3D rig or phoneme-perfect lip sync

Implementation preference: use a lightweight state-machine animation approach (for example Rive/SVG/Canvas layers) before considering Three.js/VRM. A later spike may evaluate VRM if the owner wants more realistic head movement/lip sync.

### Phase 2D — Adaptive workspace + IAI Brain

Goal: make the center useful, not just decorative.

Acceptance targets:

- Orion Core can contract to a smaller presence while content takes center stage
- explicit workspaces for media, documents, memory, tasks, comparisons, and diagnostics
- **IAI Brain** button/action opens the actual supported iai Brain surface when available rather than inventing a second memory editor
- memory status is transparent: source/provenance, availability, stale/degraded state where supported
- agent-summoned content uses an explicit tool contract
- display actions never grant new execution authority by themselves

### Phase 2E — Voice integration

Goal: add voice only after typed/control paths are stable.

Preferred order:

1. validate Hermes-native voice on the accepted pin
2. expose its state/events cleanly to Orion HUD
3. add push-to-talk
4. add continuous conversation/barge-in
5. evaluate wake phrase `hey Orion` with Hermes sherpa/open-vocabulary path
6. only add custom voice-server code where Hermes-native behavior demonstrably cannot satisfy the requirement

### Phase 2F — Hardening and polish

Acceptance targets:

- browser security/origin/auth review
- no secret-bearing browser state beyond the minimum authorized session mechanism
- reconnect/reload behavior
- interrupted-turn recovery
- offline/degraded indicators
- animation CPU/GPU budget
- accessibility/reduced-motion
- multi-display identity and target selection before broadcast-style summon behavior
- documented rollback and smoke tests
- Windows-focused start/stop/runbook integration that preserves manual-off lifecycle

## Reuse policy for `S-Pillow/jarvis_ai`

Jarvis is an active reference implementation and selective code donor.

Prefer to adapt:

- explicit `hud_display`-style tool concept
- STOP/approval UX patterns
- Hermes credential isolation / allowlisted proxy concept
- session/tool event handling patterns
- holographic/summonable panel interactions
- machine/usage/status ideas

Do not inherit blindly:

- macOS launchd lifecycle
- the single-file 45 KB HUD architecture
- a second always-on lifecycle authority
- custom STT/TTS orchestration if Hermes-native voice meets the requirement
- broadcast-to-every-screen semantics without device targeting
- old Hermes v0.16 assumptions

## Dependency posture

No upstream dependency upgrade is authorized by this planning record.

Current watch:

- Hermes accepted: `0.20.6`; upstream stable `0.21.1`
- iai accepted: `3.0.8`; upstream stable `3.2.0`
- Ollama latest stable observed: `0.33.3`; exact local binary version still needs capture

Details:

`docs/phase2/dependency-watch-2026-09-09.md`

## Immediate next decision

Owner review should approve or revise the v2.8 HUD PRD draft. After that, Phase 2A should begin as a **read-only/API-contract discovery ticket first**, followed by one bounded implementation ticket. No HUD code should be allowed to mutate accepted lifecycle policy as part of convenience setup.

Core Intent Preservation: **PRESERVED**.
