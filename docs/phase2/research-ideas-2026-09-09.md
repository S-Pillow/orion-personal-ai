# Phase 2 Research Ideas — GitHub / Reddit / Community Forums

Date: 2026-09-09

Purpose: look beyond Jarvis for patterns that could make Orion more useful, more alive, or simpler to maintain.

This is a research backlog, not an authorization to add dependencies or features.

## Highest-value findings

### 1. Let Hermes own voice; let Orion own presence and presentation

The strongest finding did not come from another assistant project: it came from the **already-accepted Hermes v0.20.6 source/docs**.

That pin already contains streaming TTS, local Whisper support, full-duplex barge-in, interruption-aware conversation state, voice stop phrases, and local wake-word support including an open-vocabulary `sherpa` provider.

This changes the architecture recommendation substantially.

Instead of:

`Orion HUD -> Orion voice server -> STT -> Hermes -> TTS -> HUD`

prefer to validate:

`Orion HUD/presentation -> accepted Hermes voice/session surfaces -> existing agent + iai`

and only add Orion-owned audio code for gaps proven by tests.

Benefit: fewer daemons, fewer credentials, less latency, less duplicated state, and better preservation of the accepted Phase 1 ownership model.

### 2. Give every screen/device an identity

Home Assistant's 2026 **Voice Satellite** work is a useful model. A browser/tablet is registered as a real voice satellite rather than treated as an anonymous page. That enables timers, announcements, media playback, multi-turn conversations, and visual results to target the device that initiated the interaction.

References:

- https://community.home-assistant.io/t/voice-satellite-turn-any-tablet-phone-or-browser-into-a-private-alexa-google-home-siri-for-home-assistant/1008350
- https://www.reddit.com/r/homeassistant/comments/1rr7d4n/my_tablet_finally_feels_like_a_real_smart_display/

Orion implication: do not copy Jarvis' “broadcast summoned panel to every open HUD” as the final design. Introduce a small display registry early:

- display ID
- friendly name
- current connection/last seen
- capabilities (screen, audio, mic)
- optional room/location label supplied by owner
- active/focused display

Then commands such as “show that here,” “put this on the office monitor,” or “send this to my phone” have a clean architecture later.

### 3. Make Orion's eyes useful, not merely decorative

The owner's desired blink / small head turn / uncanny-human idle behavior can become functional with very little extra complexity.

Recommended **gaze-aware presentation** behavior:

- blink at randomized natural intervals
- tiny eye saccades in idle
- subtle head/parallax drift rather than full 3D rotation
- when Orion summons a left-side panel, eyes/head glance slightly left
- when a right-side panel appears, glance right
- when waiting for approval, focus toward the approval card
- while listening, gaze returns toward center/user
- while thinking, lower-frequency micro-movement and slower particle drift

This creates a sense that Orion is aware of its own workspace without needing a heavyweight avatar rig.

A lightweight state-machine animation system is a good fit. Rive is one candidate because its web runtime supports programmatically controlled boolean/number/trigger state-machine inputs:

- https://github.com/rive-app/help-center/blob/master/runtimes/state-machines.md

For V1, Rive/SVG/Canvas should be evaluated before Three.js/VRM.

### 4. Keep a future VRM path, but do not start there

Community projects prove that local avatars with blinking, breathing, expressions, gestures, and live lip sync are feasible.

Examples:

- Hanami: https://github.com/Undi95/Hanami
- three-vrm-lip-sync: https://github.com/vlapky/three-vrm-lip-sync
- Reddit local companion discussion: https://www.reddit.com/r/LocalLLM/comments/1tbx527/how_a_75yearold_retiree_built_a_local_ai_with_a/

`three-vrm-lip-sync` can drive VRM mouth visemes directly from live audio in-browser without server-side phoneme timing.

Orion implication: if the owner later wants a true 3D masked head, there is a plausible migration path. But a full VRM stack should be a **post-V1 visual spike**, not a Phase 2 prerequisite. The current 2D/2.5D masked-core concept can deliver most of the “alive” feeling at much lower cost.

### 5. Build a Memory Lens, not a second memory system

Several modern agent UIs emphasize making persistent memory inspectable. Open WebUI exposes memory review/control; Letta exposes memory blocks/files and desktop viewers; iai itself is now moving toward explicit health/degraded/staleness indicators.

References:

- https://github.com/open-webui/docs/blob/main/docs/features/chat-conversations/memory.mdx
- https://github.com/letta-ai/letta-docs-md/blob/main/configuration/memory/index.md

Orion should use that idea without copying their memory semantics.

Recommended **Memory Lens** in the HUD:

- iai status: healthy / unavailable / degraded / stale where the installed/qualified version supports it
- latest capture timestamp/watermark
- small list of memories actually relevant to the active turn, with provenance
- explicit “Open IAI Brain” button for full supported memory inspection/editing
- no autonomous editing controls in the HUD unless iai exposes a supported and authorized operation

This gives the user confidence about *why Orion remembers something*.

### 6. Add a visible authority / execution mode

Leon 2.0 separates smart, controlled, and agent-style execution and emphasizes deterministic tools for controlled work:

- https://github.com/leon-ai/leon

Orion should not copy Leon's runtime, but the UI idea is useful. A small visible **authority state** can make consequential behavior legible.

Possible Orion presentation:

- `OBSERVE` — read/status/chat only
- `ASSIST` — tools can prepare work; consequential actions require approval
- `ACTING` — currently executing an explicitly authorized action

This is a **display of current authorization**, not a magic global permission switch. The HUD must never broaden authority merely because a visual mode was selected.

### 7. Add an “ears off” privacy state

OpenVoiceOS has a simple “Naptime” concept: stop speech-to-text activity and retain only the minimum local wake behavior needed to wake again.

Reference:

- https://github.com/OpenVoiceOS/ovos-skill-naptime

Orion already has a stronger manual-off lifecycle at the system level. Within an active HUD session, it can still benefit from a clear microphone privacy control:

- Voice OFF — no microphone capture
- Push-to-talk — mic only during explicit press
- Wake mode — local wake detector armed
- Conversation mode — temporary continuous/full-duplex voice

The current mode should always be obvious next to the Orion Core.

### 8. Borrow voice robustness ideas, not another voice framework

LiveKit Agents has sophisticated concepts around false interruptions, acoustic echo warmup, turn detection, and resuming speech after false barge-ins:

- https://github.com/livekit/agents

This is useful as a **test-design reference**. It is not a recommendation to add LiveKit to Orion while Hermes already owns voice.

Test ideas worth borrowing:

- distinguish real barge-in from a brief noise hit
- avoid immediate echo-triggered interruption when TTS begins
- preserve interrupted conversation history
- ensure stop/cancel works during tool preambles and generation
- expose timing metrics for STT finalization, first token, first audio, and total turn

### 9. Use a short follow-up window carefully

Home Assistant community users repeatedly want continuous conversation, but forum reports also show the failure mode: in a noisy room, an assistant can repeatedly hear background audio and enter a nonsense response loop.

References:

- https://community.home-assistant.io/t/continue-conversation-automatically-on-home-assistant-voice-pe/829487
- https://community.home-assistant.io/t/continuous-conversation-workaround-with-code/892139

Orion implication: “keep listening after a reply” should be bounded and observable, not infinite.

Potential later design:

- after Orion finishes speaking, remain in follow-up listening for 5–8 seconds
- visible countdown/ring state
- exit immediately on silence/no meaningful transcript
- hard cap consecutive auto-follow-ups
- user can say a strict stop phrase at any time

Hermes' accepted native continuous voice behavior should be evaluated before Orion adds custom logic.

### 10. Treat workspaces as first-class UI objects

Open WebUI and modern agent UIs increasingly separate chat from persistent artifacts/notes/tools rather than forcing everything into one transcript.

Reference:

- https://github.com/open-webui/open-webui

Orion's adaptive center should therefore support first-class workspace objects rather than only iframes:

- research result
- document
- image/video
- chart
- memory
- task/plan
- comparison
- diagnostics
- approval

The Orion Core can shrink to a smaller “presence” while the workspace is active, then reclaim the center when the workspace is dismissed.

## Recommended feature priority

### V1 / high return

- modular HUD shell
- Orion Core with blink, saccades, subtle parallax/head drift
- gaze toward summoned UI elements
- typed chat + live run/tool activity
- STOP and approvals
- adaptive workspace
- IAI Brain button
- read-only Memory Lens status
- system/model telemetry
- display identity even if only one display exists initially
- reduced-motion switch

### V1.5 / after typed foundation

- Hermes-native push-to-talk
- voice-reactive core amplitude/particle animation
- full-duplex barge-in
- optional `hey Orion` wake phrase using accepted Hermes open-vocabulary wake support
- bounded follow-up conversation window
- screen targeting

### Later / experimental

- VRM/Three.js true 3D Orion head
- audio-driven viseme lip sync
- richer gestures/expressions
- room-aware multi-device presence
- proactive ambient cards/announcements
- mobile/PWA kiosk mode

## Ideas explicitly not recommended for the first build

- replacing Hermes with another agent framework simply because its UI is attractive
- adding LiveKit/OpenVoiceOS as another voice runtime when Hermes already satisfies the core requirement
- always-on cloud audio
- photorealistic MetaHuman/Unreal rendering on the same GPU as the local LLM
- voice biometrics / speaker identification as an authorization mechanism
- unrestricted autonomous HUD actions
- a second Orion-owned memory database

## Updated design thesis

The strongest version of Orion is not “Jarvis but prettier.”

It is:

> **Hermes as the accepted agent/voice runtime, iai as the accepted memory brain, and Orion as the living visual control-and-presentation layer that makes those systems understandable, interruptible, and personal.**

The masked celestial Core can provide the identity; adaptive workspaces provide usefulness; visible memory/authority/agent state provides trust.
