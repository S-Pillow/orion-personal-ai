# Orion Final Interface Visual Contract

Status: **OWNER-APPROVED VISUAL NORTH STAR / IMPLEMENTATION INCREMENTAL**

Date: 2026-09-11

Controlling specification: **ORION Master PRD v2.8**

Accepted source baseline at creation: `main` = `8db415a78cf23a99a93c8772cc54a5c357243663`

## Purpose

Capture the visual/product direction approved by Steven on 2026-09-11 so future HUD work converges on one coherent Orion experience instead of accumulating disconnected panels.

This is a **design contract**, not permission to skip PRD phase gates or to fabricate capabilities that do not exist yet. The concept image created during the design session is the visual north star; this document records the durable implementation intent in source control.

## Product feeling

Orion should not feel like a generic AI chat application or a permanently busy monitoring dashboard.

The target experience is a calm, private observatory / command deck:

- dark matte graphite / charcoal base;
- restrained cyan/teal illumination;
- white for primary readable content;
- amber/red only for consequential status, approval, degradation, or stop/error state;
- thin technical geometry rather than ornamental glassmorphism;
- motion only when it communicates state, attention, or change;
- generous negative space when nothing important is happening.

The interface should feel personal, intelligent, composed, and truthful rather than theatrical.

## Persistent identity: Orion Core

The Orion Core is the primary visual identity and persistent anchor.

It should read as a blend of:

- celestial instrument;
- aperture / lens;
- abstract masked presence;
- subtle implied eyes without becoming a literal human or robot face.

The Core may use low-cost local presentation behavior already allowed by PRD v2.8:

- blink;
- micro-saccade;
- subtle gaze/orientation;
- restrained parallax;
- breathing/pulse;
- attention shifts toward active panels or approval state.

Motion semantics:

- `IDLE/READY`: nearly still;
- `LISTENING`: slight inward/open attention treatment once voice exists;
- `THINKING`: internal movement, not decorative spinning;
- `TOOL/ACTING`: restrained outward activity pulse;
- `WAITING/APPROVAL`: attention shifts toward approval surface;
- `DEGRADED`: quieter, constrained, clearly non-healthy presentation;
- `STOPPING/INTERRUPTED`: immediate visible break in activity;
- reduced-motion mode disables generated motion while preserving state meaning.

## Adaptive composition

The Core stays persistent while the center workspace adapts to the task.

### Top edge

Keep a narrow, low-noise status/navigation layer containing only evidence-backed state, for example:

- ORION identity;
- current workspace/mode;
- local/cloud/source provenance when actually known;
- voice/privacy state once Phase 4 exists;
- clock;
- optional current project/context when explicitly available.

Do not display a green `LOCAL` or equivalent merely because the HUD is on loopback or Ollama exists.

### Left rail

The left rail is contextual, not a dumping ground. Likely long-lived categories:

- current Hermes session;
- current project/context when explicitly selected or resolved;
- memory authority / native iai Brain handoff;
- compact navigation/summon affordances when they become real.

The rail should collapse or simplify when information is not useful.

### Right rail

The right rail is the consequential/action side of the interface:

- active tool/run activity;
- approvals;
- bounded action previews;
- evidence/provenance drill-down;
- temporary state that matters now.

It should not become a permanent telemetry wall.

### Bottom command surface

One persistent command surface supports:

- typed input;
- voice entry later through the same conversation;
- SEND;
- STOP whenever a Hermes run is actually active;
- optional add/summon affordance only when implemented.

## Conversation is home

Conversation remains the default workspace and should not look like a consumer chat bubble app.

Target presentation:

- readable centered content column;
- understated user turns;
- stronger Orion response typography;
- tool progress separated from authoritative transcript;
- old conversation may visually recede while remaining accessible;
- persisted Hermes SessionDB remains conversation authority;
- no competing transcript database.

The current P3-02/P3-03 typed path remains the functional baseline while visual composition evolves around it.

## Workspaces are summoned, not multiplied blindly

Avoid turning every capability into another permanent tab.

Primary stable workspaces may include the PRD-defined set:

- Conversation;
- System Status;
- Memory Lens / native IAI Brain;
- Vault / Inbox;
- Tasks / Reminders;
- Approvals.

Other outputs should prefer summonable contextual panels where practical.

Examples:

- memory question -> Memory Lens expands;
- document request -> document/evidence panel appears;
- comparison request -> center workspace becomes comparison layout;
- approval demand -> right action surface expands and Core orients toward it;
- system question -> System view becomes primary without altering runtime authority.

## Memory Lens

Memory should feel present without duplicating iai.

Orion explains:

- what relevant memory/context was used when that can be observed;
- where the context came from;
- whether provenance/health is live, stale, degraded, unavailable, or unobserved;
- why it appears relevant when that explanation is evidence-backed;
- that persistent memory authority belongs to iai.

Detailed memory administration remains in installed-version-supported native iai Brain/CLI surfaces.

Orion does not become a second memory engine, store, ranking system, forgetting system, or administration UI.

## Provenance and authority visual language

Provenance is quiet but inspectable.

Candidate display vocabulary, subject to P3-04 evidence rules:

- `ORIGIN · LOCAL`
- `ORIGIN · CLOUD-ASSISTED`
- `ORIGIN · UNOBSERVED`
- `MEMORY · IAI`
- `SOURCE · GITHUB`
- `SOURCE · OBSIDIAN`
- `AUTHORITY · OBSERVE`
- `AUTHORITY · ACT WITH APPROVAL`

These are examples of presentation vocabulary, not permission to display a state without proof.

Rules:

1. Evidence source controls the label.
2. Unknown/unobserved is a valid state.
3. Loopback transport does not prove local model execution.
4. A running Ollama process does not prove a particular response came from Ollama.
5. A descriptive authority label never grants authority.
6. Browser assets never infer filesystem, shell, cloud, approval, or lifecycle rights from convenience or shared Windows identity.
7. Color is supplementary; every critical state has text/icon semantics as well.

## Approval surface

Consequential action UX should clearly show the boundary being crossed.

Preferred structure:

- `WHAT ORION WANTS TO DO`
- `WHY`
- `TARGET`
- `EFFECT`
- `AUTHORITY REQUESTED`

The actual canonical choices come from the supported Hermes approval contract; presentation must not invent broader authority.

When approval is required:

- nonessential visual noise should recede;
- the Core may orient toward the approval surface;
- the action target/effect should be readable before the decision;
- denial remains a first-class outcome;
- stale/reconciled approval state must be shown truthfully.

## Voice integration later

Voice should make the Core feel more alive rather than add a separate microphone application.

When Phase 4 is reached, map supported Hermes voice/wake state into the same Core/workspace model:

- wake/listening;
- speech recognized;
- thinking;
- speaking;
- interrupted/barge-in;
- muted/privacy-off states;
- typed fallback always available.

No parallel Orion STT/TTS/hotword runtime is implied by this visual contract.

## Visual restraint rules

Avoid:

- decorative hexagon/grid overload;
- constant particle animation;
- large spinning globes with no state meaning;
- meaningless telemetry;
- tiny unreadable pseudo-terminal text;
- permanent panels for inactive capabilities;
- color-only status communication;
- animated motion that does not represent attention, state, or transition.

Every effect should answer a product question:

- glow = activity/state emphasis;
- direction/gaze = attention;
- pulse = transition or active work;
- expansion = current relevance;
- color = status category;
- motion = something actually changed.

Otherwise the interface stays still.

## Current implementation mapping

Already accepted on `main`:

- persistent typed Hermes conversation;
- STOP, approvals, activity, capabilities, degraded/error presentation;
- P3-01 Orion Core state/gaze foundation;
- P3-02 adaptive Conversation/System workspace;
- P3-03 Memory workspace + native iai Brain handoff.

Current implementation slice:

- P3-04 provenance/origin/authority evidence model and truthful indicators.

P3-04 source discovery established an important visual rule for the north star: the top-bar origin indicator must be able to say `UNOBSERVED`. The accepted local Ollama baseline and an observed per-turn inference origin are separate facts and must be presented separately until evidence joins them.

Future slices may progressively reshape composition toward this visual north star, but they must preserve the accepted runtime and authority boundaries. Phase 4 supplies native Hermes voice/wake behavior; Phase 5 supplies vault/actions/approval/display tooling; Phase 6 supplies bounded cloud escalation/reminders; Phase 7 may add target-aware display/device/LAN behavior.

## Build sequencing toward the north star

The image is reached through bounded slices rather than a single visual rewrite.

Recommended sequence:

1. **P3-04 — provenance/origin/authority foundation**: make the future top/status language truthful before amplifying it visually.
2. **P3-05 — composition convergence**: reshape spacing, rails, top edge, conversation hierarchy, and Core prominence using only capabilities already accepted at that point. No fake Research/Create/Vault/Tasks controls.
3. **Phase 4 — voice/wake integration**: let the Core become the voice surface only after the supported Hermes voice/wake path is proven on the machine.
4. **Phase 5 — vault/action/display surfaces**: introduce the richer right-side approval/action composition and summonable document/evidence surfaces when their backend capabilities exist.
5. **Phase 6+ — cloud/reminders/device context**: only then enable cloud-assisted, reminders, device/LAN indicators and related visual states.

This sequence allows the interface to look increasingly like the approved concept without lying about capabilities that have not reached their phase gate.

## Acceptance principles for visual work

A visual change is not accepted merely because it resembles the concept image.

Each slice must prove:

- the underlying displayed state is truthful;
- existing typed/session/STOP/approval behavior still works;
- Core state remains deterministic/testable;
- reduced-motion behavior remains valid;
- no new runtime/lifecycle/data authority was introduced accidentally;
- the full HUD synthetic suite remains green;
- controlled live visual smoke confirms layout and state behavior on the accepted Windows runtime before merge when runtime evidence is required.

## Stop conditions

Stop and re-scope if achieving the visual design would require:

- replacing Hermes as agent/session/run authority;
- duplicating iai memory semantics or administration;
- exposing the Hermes API key to browser assets;
- introducing generic shell/process/filesystem authority merely for presentation;
- fabricating provenance or authority labels;
- adding a parallel voice stack;
- dependency/framework replacement without separate qualification;
- collapsing future phase capabilities into cosmetic placeholders that imply they already exist.

Core Intent Preservation: **PRESERVED**.
