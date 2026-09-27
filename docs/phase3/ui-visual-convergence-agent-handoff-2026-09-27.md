# Orion UI Visual Convergence — Agent Handoff

Date: 2026-09-27
Owner: Steven
Repository: `S-Pillow/orion-personal-ai`
Active PR: #51 — `UI visual convergence: companion presence and calm workspace`
Active branch: `feature/orion-ui-visual-convergence-pass`
Implementation head at start of handoff: `b05adb4d88e07af7b1972c4d98df36514220d3b1`
Live PR head: **query PR #51 before any work; handoff/document commits advance the branch**
PR base: `ee03c567280026069c403bcfbdce2da5da2e3c28`
PR state: **OPEN / DRAFT / NOT ACCEPTED / NOT MERGE-READY**
Observed GitHub mergeability at handoff: **false**
Do not merge PR #51 until the visual architecture is materially closer to the owner target and all relevant source/visual checks are rerun on the final exact head.

---

## 1. Why this handoff exists

This document is intentionally written so a new agent with **zero prior conversation context** can continue the Orion UI convergence work without reconstructing project history from chat.

The active task is not a small CSS polish. It is a significant visual-architecture rewrite intended to make the Orion HUD feel like a cinematic, local, authority-aware **personal AI thinking companion**, rather than a telemetry console or generic chatbot.

The owner supplied a concrete visual north-star screenshot and explicitly stated:

> "This is the goal."

The controlling visual direction is already recorded in:

- `docs/phase3/ui-convergence-visual-contract.md`

That source-controlled contract should be read before making additional UI changes.

The current PR has moved substantially toward that target but is still visually incomplete. The most recent owner feedback remains critical and should be treated as the active implementation backlog, not as optional polish.

---

## 2. Project history that matters

### 2.1 Approved project/authority baseline

The project is governed by Orion Master PRD v2.9.

Key accepted runtime baseline:

- Hermes v2026.8.27
- package 0.20.6
- Hermes commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- installed API source SHA `7a206396aac7abe7e50fd5d346733fea85bb57160cb0a5d8a2e7feda29167c84`
- rollback backup SHA `ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888`

Do not upgrade Hermes as part of this UI work.

### 2.2 Accepted Phase 5 foundation

The browser-safe projection/action-evidence work predates this visual pass and remains authoritative.

Relevant constraints:

- Hermes remains runtime/session/run/tool/approval authority.
- Browser projection is presentation only.
- Browser must never invent protected execution success.
- Approval acknowledgment is not execution evidence.
- Existing approval/action/recovery truth semantics must remain intact.
- Exact diff/approval content must not be silently truncated or semantically altered.
- No browser-local second database, approval record, recovery authority, or action ledger.
- No credentials, secrets, raw private payloads, arbitrary tool args, stack traces, binaries, or protected file bytes in the browser projection.

### 2.3 P5-03B accepted/merged checkpoint before hardware change

P5-03B source and visual/truth acceptance completed at candidate:

`557ff4e382176bd7060bf0f378d34b38c4b23bd5`

The local hardware checkpoint after merge was:

`e55517bfc33b93a0983026a3a494d6df86c9532f`

### 2.4 Hardware change

The user replaced RTX 3070 with AMD Radeon RX 9070 XT successfully.

Post-swap verification:

- GPU: AMD Radeon RX 9070 XT
- Windows reported status: OK
- Orion source remained clean
- Orion/Hermes restarted through accepted operator path
- Hermes health returned HTTP 200

The hardware change is complete and is not part of current UI work.

### 2.5 Structural UI convergence foundation

A structural convergence foundation was completed and merged before this visual-design PR.

PR #49 merged at:

`d32137066a6ef20b57e1045fb8a827779cc47440`

This foundation established:

- companion-first structural shell
- stronger Core/center hierarchy
- quieter diagnostic rails
- approval/action ordering
- bounded summon presentation shell
- approval-over-summon focus arbitration
- literal text rendering
- responsive baseline
- no new runtime authority

It was explicitly **not** considered the finished visual UI.

Old P3-05B draft PR #26 was closed as superseded.

Docs closure PR #50 merged at:

`ee03c567280026069c403bcfbdce2da5da2e3c28`

This is the base of active PR #51.

---

## 3. Current task

Active work unit:

**Actual visual-design convergence**

The goal is to make Orion resemble the supplied owner reference in:

- composition
- hierarchy
- depth
- density
- visual language
- interaction emphasis
- typography
- rail integration
- hero identity
- conversation presentation

while preserving only functionality Orion actually supports.

Do **not** add fake features merely to resemble the screenshot.

Specifically:

- keep supported tabs: Conversation / System / Memory
- do not invent Research/Create tabs unless separately implemented
- do not fabricate active projects
- do not invent provenance/confidence values
- do not fabricate memory usage
- do not fabricate local/source claims
- do not turn decorative UI into implied runtime authority

---

## 4. Owner visual target

The target design is a cinematic cosmic Orion workspace characterized by:

1. a full-width dark graphite/cosmic environment
2. large luminous central Orion identity integrated into the scene
3. strong environmental depth: sky, horizon, architecture, reflection, foreground
4. an integrated top chrome/navigation system
5. left contextual rail
6. central hero + foreground conversation region
7. right operational rail for current activity / approvals / memory context
8. readable application-scale typography
9. cyan brand light used selectively
10. amber for approval/warning
11. red for stop/deny/error
12. white/neutral hierarchy for primary content
13. selective cards, not a wall of outlined telemetry boxes
14. conversation as the main work surface
15. approvals as first-class consequential controls
16. memory authority visibly distinct and trustworthy

The target should feel:

- cinematic
- deliberate
- premium
- quiet
- intelligent
- spatial
- companion-like
- operationally truthful

It should **not** feel like:

- a SOC dashboard
- a debug HUD
- a wireframe
- an instrumentation console
- a generic chatbot
- a collection of unrelated dark cards

---

## 5. Current branch architecture

### 5.1 Static shell

Current branch significantly rewrote:

- `hud/static/index.html`
- `hud/static/app.js`
- `hud/static/styles.css`
- new `hud/static/target-layout.css`
- new `hud/static/orion-hero.svg`

### 5.2 Bridge changes

`hud/orion_hud_bridge.py` serves:

- `/target-layout.css`
- `/orion-hero.svg`

No new runtime API endpoint was intentionally added for visual convergence.

### 5.3 Hero implementation

The hero is now a dedicated SVG asset:

`hud/static/orion-hero.svg`

This was chosen intentionally instead of trying to reconstruct the entire visual target using CSS rings.

Current SVG contains:

- radial sky gradient
- star field
- planetary/lunar edge
- luminous orb/rim
- vertical cyan axis
- orbital geometry
- horizon/floor
- perspective structure
- foreground architecture/posts
- reflection path
- environmental lines

Live Orion state elements remain DOM/CSS, not baked into the image:

- live eyes
- current Core state
- state color
- motion/state hooks

This preserves state-driven semantics while allowing richer scene artwork.

### 5.4 Top chrome

Workspace navigation was moved into the top bar.

Current supported tabs remain:

- Conversation
- System
- Memory

Tagline currently:

**YOUR THINKING PARTNER**

Top telemetry still exists and is one of the remaining design problems; see backlog below.

### 5.5 Left rail

The left rail was rebuilt around contextual/editorial sections rather than old diagnostic panels.

Current sections:

- Session
- Memory Authority
- Companion Context
- collapsed System Status
- atmospheric footer/quote

Companion Context currently uses only supported facts:

- Conversation: Hermes
- Memory: iai
- Transport: loopback
- Action authority: human approval

### 5.6 Right rail

Current right rail includes:

- Current Activity
- Pending Approval
- Action Evidence
- Memory Lens
- collapsed System Details

Memory Lens remains a handoff/explanation surface; native IAI Brain remains memory administration authority.

### 5.7 Conversation renderer

`hud/static/app.js` was modified so messages now support:

- avatar/identity marker
- speaker name
- timestamp when present in authoritative message payload
- structured message header
- body region

Timestamp lookup currently accepts:

- `created_at`
- `createdAt`
- `timestamp`
- `time`

If absent, timestamp is hidden rather than invented.

### 5.8 Approval renderer

Approval rendering was recently restructured.

Old behavior:

- command + exact description concatenated into one large text block

Current behavior:

- command/action rendered in `#approvalCommand`
- exact description rendered separately in `#approvalDetail`
- exact description remains literal text
- no HTML rendering
- no intentional truncation
- exact approval detail remains scrollable
- allowed choice filtering unchanged

Associated Node test was updated:

`hud/tests/test_approval_rendering.cjs`

The acceptance invariant remains:

**presentation may improve; approval content must remain complete and semantically unmodified.**

---

## 6. Current exact Git state

At handoff:

Branch:

`feature/orion-ui-visual-convergence-pass`

PR:

#51

Implementation head before handoff documentation commits:

`b05adb4d88e07af7b1972c4d98df36514220d3b1`

The branch advances when this handoff file/PR metadata are updated. Always query PR #51 for the live head before making writes.

Base:

`ee03c567280026069c403bcfbdce2da5da2e3c28`

State:

- OPEN
- DRAFT
- NOT ACCEPTED
- NOT READY TO MERGE

GitHub reported mergeability:

`false`

Do not assume this indicates a source conflict without re-querying GitHub; mergeability can be transient/stale while GitHub recalculates. Re-check before acting.

---

## 7. Current changed-file scope in PR #51

At handoff the PR changes include:

- `docs/phase3/ui-convergence-visual-contract.md`
- `hud/orion_hud_bridge.py`
- `hud/static/app.js`
- `hud/static/index.html`
- `hud/static/orion-hero.svg` (new)
- `hud/static/styles.css`
- `hud/static/target-layout.css` (new)
- `hud/tests/probe_approval_surface.py`
- `hud/tests/probe_ui_convergence.py`
- `hud/tests/test_approval_rendering.cjs`
- `hud/tests/test_ui_convergence_contract.py`
- `hud/tests/test_ui_convergence_fixture.py`
- `hud/tests/test_ui_visual_convergence.py` (new)

No reconnect/hydration production implementation belongs in this PR.

---

## 8. Review fixture architecture

### 8.1 Purpose

The review fixture is deliberately isolated.

It uses:

- temporary copied HUD static source
- in-memory fake Hermes API
- loopback-only temporary servers
- no real Hermes credentials
- no model calls
- no vault access
- no production mutation

Relevant files:

- `hud/tests/probe_approval_surface.py`
- `hud/tests/probe_ui_convergence.py`

### 8.2 Seeded review conversation

The fake session now seeds a realistic multi-turn conversation with timestamps so visual review can judge the real conversation composition rather than an empty state.

### 8.3 Seeded activity

`?fixture=review` also seeds simulated review activity via the production `addActivity()` presentation path.

This is test-only and does not represent authoritative runtime activity.

### 8.4 Summon fixture

`?fixture=summon`

Shows bounded summon presentation while conversation remains selected.

### 8.5 Summon + approval fixture

`?fixture=summon-approval`

Should:

1. load fake session
2. submit simulated `probe`
3. receive run.started
4. receive approval.request
5. show approval while summon remains open
6. preserve approval priority over summon
7. expose simulated choices only
8. report `mutation_performed=false`

### 8.6 IMPORTANT unresolved visual-review issue

In the owner's most recent review, the third image did **not** show the approval panel.

This must not be ignored.

Immediately before this handoff, a fixture-only race was identified:

- `summon-approval` was invoking session bootstrap in the shared mode bootstrap **and**
- invoking session bootstrap again inside the approval-submit async flow

This could race session/message initialization.

Fix committed:

`3209eed9ca16a4c567742fa36bd7f5fd3579a43c`

Regression-test commit:

`b05adb4d88e07af7b1972c4d98df36514220d3b1`

The fixture now:

- auto-bootstraps review/summon in the shared path
- bootstraps summon-approval only once in its own async path
- waits 75ms after session/message load before programmatic submit

This fix is **not yet visually revalidated by the owner**.

Next agent must verify the third review state before claiming approval-over-summon is still visually working on current head.

Do not classify the missing approval as a production regression unless isolated review proves the fixture fix insufficient.

---

## 9. Most recent owner critique — treat as active backlog

The owner supplied a detailed critique of the latest implementation. The important point is that the remaining issue is **layout discipline**, not merely decorative polish.

### 9.1 Center architecture

Current problems:

- hero and conversation still feel vertically disconnected
- central axis terminates ambiguously
- conversation feels like a card dropped beneath a scene
- dead vertical regions remain
- hero/conversation/composer do not yet read as one continuous workspace

Required direction:

- establish a deliberate vertical composition
- hero should visually feed into conversation
- conversation should overlap/fade/connect to hero
- central axis should terminate intentionally
- remove accidental dead space
- use formal layout variables/tokens rather than viewport-specific offsets

### 9.2 Hero scale/depth

Current problems:

- focal object can still feel undersized or visually empty relative to allocated hero area
- interior details remain weak at ordinary brightness
- platform geometry can disappear
- scene risks looking vector-clean in the ring but under-rendered elsewhere
- eyes/status placement remains awkward

Required direction:

- continue improving filled volume and depth
- raise platform/environment midtones slightly
- increase useful interior detail
- refine eye scale/position/luminance
- reconsider READY label placement
- ensure the focal object earns its screen area
- use atmosphere and perspective geometry to guide the eye

### 9.3 Conversation region

Current problems:

- still potentially too wide relative to text measure
- message content width and panel width can disagree
- vertical rhythm not fully tokenized
- avatars still may need larger/stronger identity treatment
- user/Orion alignment may need modest asymmetry
- composer separation can still feel arbitrary
- internal scroll strategy must remain explicit

Required direction:

- formal center maximum width
- readable 65–80 character measure
- explicit message-gap / paragraph-gap / speaker-gap / thread-gap tokens
- slightly larger speaker avatars
- stronger speaker labels
- sticky composer through grid structure
- independent transcript scroll
- no extreme consumer chat bubbles

### 9.4 Composer — high priority

The owner specifically circled the Send/Stop area.

Problems:

- button cluster feels bolted onto text input
- nested border/radius relationships look messy
- Send/Stop hierarchy weak
- Stop state ambiguous
- controls too close to composer edge
- composer has excessive empty horizontal space
- focus state needs deliberate treatment

Required architecture:

```css
.composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: stretch;
}
```

Prefer:

- Send as primary idle action
- Stop hidden or clearly disabled while idle
- Stop active/prominent only during generation
- explicit disabled styling
- inset action region
- consistent composer radius
- visible but restrained `:focus-visible`
- avoid nested arbitrary segmented borders

Potential implementation choice:

**Hide Stop while idle** if existing behavior/tests allow it safely.

If both remain visible:

- Stop must be unambiguously disabled when unavailable
- Send/Stop should share a clear action-container geometry

### 9.5 Shell width/grid

Current problems:

- center and rail systems still feel like separate coordinate systems
- large external gutters can make rails float inside the viewport
- header alignment does not fully correspond with body columns
- desktop design remains vulnerable to ultrawide stretching

Required direction:

Define shared shell variables:

- `--header-height`
- `--rail-left-width`
- `--rail-right-width`
- `--workspace-max-width`
- `--hero-height`
- `--content-gutter`
- `--panel-radius`
- spacing scale
- text neutral scale
- surface elevation scale
- semantic colors

Then force header + rails + center to align to the same shell system.

Recommended conceptual desktop shell:

```css
.orionShell {
  display: grid;
  grid-template-columns:
    minmax(220px, 260px)
    minmax(0, 1fr)
    minmax(280px, 320px);
  grid-template-rows:
    var(--header-height)
    minmax(0, 1fr);
  height: 100dvh;
}
```

Center workspace:

```css
.workspace {
  display: grid;
  grid-template-rows:
    minmax(260px, 38vh)
    minmax(0, 1fr);
  min-height: 0;
}
```

Conversation region:

```css
.conversationRegion {
  width: min(100% - 48px, 1120px);
  margin-inline: auto;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  min-height: 0;
}
```

The exact values may change, but the architecture should become systematic.

### 9.6 Left rail

Current problems:

- weak vertical density distribution
- footer/mountain scene can still feel clipped or detached
- quote alignment/contrast needs refinement
- values remain too small
- native select can look generic
- memory authority is underweighted

Required direction:

- either add supported context or use deliberate atmospheric space
- do not fabricate projects
- strengthen Memory Authority presentation
- improve select styling without breaking native accessibility
- align quote to rail content grid
- make atmospheric footer an intentional full-width rail ending, not a clipped decoration

### 9.7 Right rail

Current problems:

- empty Current Activity can waste area
- Memory Lens hierarchy can improve
- handoff link should read as meaningful navigation
- System Details disclosure is visually weak
- approval panel can become dense with exact text
- Action Evidence + Approval + Memory Lens can overstack

Required direction:

- collapse empty activity more intelligently
- preserve exact approval detail but improve scan hierarchy
- keep consequential approval visually first
- consider progressive disclosure for lower-priority action evidence when approval is active
- make Memory Lens: heading → explanation → provenance/state → handoff
- strengthen disclosure affordance

### 9.8 Top navigation/telemetry

Current problems:

- primary nav still too small
- telemetry ribbon too dense
- clock seconds too prominent
- status fields compete
- active underline can dominate label
- many labels use same micro-uppercase style

Required direction:

- group status semantically
- reduce telemetry noise
- consider hiding seconds
- distinguish nav typography from machine metadata
- define at least:
  - section heading
  - field label
  - machine metadata
  - primary body
  - secondary body

### 9.9 Color/elevation

Current problems:

- overly monochromatic cyan/blue-gray
- cyan performs too many semantic jobs
- important borders can be too low contrast
- too much hierarchy still depends on 1px lines
- z-depth is weak

Required direction:

Use at least three elevation/surface layers:

1. environment/background
2. operational surfaces
3. active/interactive surfaces

Use semantic color separation:

- cyan = Orion brand/active
- amber = approval/warning
- red = stop/deny/error
- neutral white/gray = text and structure
- green only for actual online/success where appropriate

Important boundaries should not rely exclusively on low-alpha 1px strokes.

### 9.10 Responsiveness

Do not optimize only for current high-resolution screenshot.

Must work at minimum across:

- 1366×768
- 1440×900
- 1920×1080
- current high-resolution desktop
- browser zoom >100%

Side rails need independent responsive behavior; do not simply squeeze all columns until text becomes microtype.

At narrow widths, one or both rails should collapse/reflow deliberately.

---

## 10. Current implementation improvements already made after that critique

Before handoff, these changes were already implemented:

### 10.1 Conversation hierarchy

- message avatar DOM
- message header DOM
- speaker name
- optional authoritative timestamp
- message body
- narrower message measure
- stronger body typography

### 10.2 Center max-width

Current target CSS adds a centered shell/workspace maximum rather than unrestricted center stretch.

### 10.3 Richer hero asset

The SVG was rebuilt with:

- filled orb volume
- radial internal shading
- rim lighting
- atmospheric glow
- horizon/floor
- foreground architecture
- reflections
- perspective lines
- environmental stars

### 10.4 Left rail real context

Companion Context added using actual supported architecture facts.

### 10.5 Approval hierarchy

Command promoted to its own block.

Exact description remains literal and complete.

### 10.6 Review fixture

Seeded review conversation now includes timestamps.

Review activity now includes simulated presentation-only work items.

---

## 11. Known technical debt in active PR

### 11.1 CSS layering is too large

Current PR has both:

- legacy `styles.css`
- new `target-layout.css`
- many accumulated convergence overrides still appended to `styles.css`

This is acceptable as an intermediate branch state but should **not** be the final architecture.

Before final acceptance, rationalize styling.

Recommended direction:

- keep generic/base tokens/reset/layout primitives in `styles.css`
- keep final product composition in `target-layout.css`
- delete superseded visual-convergence override blocks from `styles.css`
- reduce contradictory cascade layers
- introduce shared design tokens at root

Do not keep stacking new override blocks indefinitely.

### 11.2 Review fixture should not drive product architecture

Fixture-only data and presentation seeds must remain clearly test-only.

Never move fake activity/project/context facts into production markup merely because the reference looks populated.

### 11.3 Mergeability false

At handoff, GitHub reports PR #51 mergeable=false.

Re-query after branch settles.

If actual conflicts exist, reconcile against current main before visual acceptance.

Do not resolve conflicts by discarding accepted Phase 5 truth logic.

### 11.4 No final source gate yet

PR #51 has not received final acceptance.

Do not infer acceptance from prior foundation gates.

Any final source gate must run on the final exact candidate head after the visual work stabilizes.

### 11.5 No final visual acceptance yet

The user explicitly does **not** want repeated formal visual gates during intermediate design iteration.

Workflow expectation:

1. iterate visually in meaningful chunks
2. compare screenshots to target
3. only when genuinely close:
   - source gate
   - bounded visual acceptance
   - exact-head record
   - PR readiness
   - merge

Do not recreate the earlier pattern of forcing long pass/fail questionnaires while major UI changes are still obviously pending.

---

## 12. Suggested next implementation sequence

The next agent should proceed in this order.

### Step 1 — Verify current branch

Check:

- PR #51 head = `b05adb4d88e07af7b1972c4d98df36514220d3b1`
- branch = `feature/orion-ui-visual-convergence-pass`
- base = `ee03c567280026069c403bcfbdce2da5da2e3c28`
- re-query mergeability
- working tree/user local state before giving commands

### Step 2 — Revalidate summon-approval fixture after race fix

Use isolated UI review fixture.

Verify:

- third tab actually displays approval
- approval appears while summon remains open
- decision buttons are reachable
- exact approval text is complete
- no protected success claim
- no real mutation
- fixture logs `mutation_performed=false`

If approval is still absent:

- inspect browser console/runtime errors
- inspect `showApproval()`
- inspect `ui.approvalCommand` existence
- inspect SSE event processing
- inspect `state.activeRunId`
- inspect fixture pending state
- inspect submit timing
- do **not** assume production regression until isolated fixture behavior is understood

### Step 3 — Build design tokens/layout system before more micro-polish

Refactor target layout around shared variables.

Do this before another dozen ad hoc offsets.

### Step 4 — Fix composer

Highest visible interaction defect.

Goal:

- one coherent composer shell
- action inset
- explicit idle/generating semantics
- meaningful Send/Stop hierarchy
- robust focus state
- no nested border collision

### Step 5 — Finish center vertical architecture

Make hero + conversation + composer read as one system.

### Step 6 — Improve hero/readability

Lift environmental midtones and refine face/state position.

### Step 7 — Normalize rails and header

Fix density, label hierarchy, telemetry grouping, and responsive behavior.

### Step 8 — Clean CSS architecture

Remove superseded overrides.

### Step 9 — Run focused source tests

At minimum:

- visual convergence contract test
- fixture tests
- approval rendering Node test
- action workspace semantics
- summon rendering
- frontend hardening / bridge tests relevant to changed files

Then full HUD suite when candidate stabilizes.

### Step 10 — One final visual review

Compare directly against owner target.

Only after owner says the visual direction is genuinely close should formal acceptance begin.

---

## 13. Critical tests/invariants that must not regress

### Approval

- exact command/action remains complete
- exact description remains complete
- literal markup remains literal
- no unsafe `innerHTML`
- unknown approval choices not granted
- new approval replaces old controls/details correctly
- decision acknowledgment never equals execution success

### Action evidence

- approval accepted = execution unproven unless authoritative action result exists
- stale/refused/failed/succeeded remain distinct
- recovery not invented
- technical evidence allowlist only

### Summon

- summon presentation does not alter workspace authority
- approval focus outranks summon focus
- dismiss restores correct focus
- unsupported/oversized payloads fail safely
- link kind only allows http/https
- literal content stays literal

### Session/projection

- disappearance clears contextual evidence/approval presentation as previously accepted
- no second browser authority
- no reconnect truth invented

### Security

Never expose:

- API keys
- provider credentials
- raw secrets
- arbitrary hidden tool args
- private raw provider payloads
- protected file bytes
- stack traces
- internal routing details not already allowlisted

---

## 14. Reconnect/hydration work

Do **not** start reconnect/hydration inside PR #51.

Separate plan exists:

`docs/phase5/p5-03c-reconnect-hydration-qualification-plan.md`

Accepted sequencing:

1. finish visual convergence
2. accept/merge UI work
3. then qualify reconnect/hydration separately

Reconnect requirements include:

- consequential state reconstructed only from supported persisted authoritative evidence
- browser cache/DOM/JS cannot fabricate approval/success/recovery
- absence of authoritative reconnect evidence => unknown/unobserved
- no second DB/approval record

---

## 15. Operator/user interaction expectations

The owner is technically capable and is working in advanced implementation mode.

Important interaction lessons:

- do not ask the user to repeat work already evidenced
- do not bury required manual steps in a noisy scrolling terminal
- visual-review launchers should be simple and explicit
- during active design iteration, do not force formal Y/N acceptance gates
- perform GitHub work proactively under standing approval
- only require user involvement for things genuinely requiring their local machine or visual observation
- when a visual issue is obvious from screenshots, treat it as design feedback and work on it directly

The owner explicitly became frustrated when the process over-gated intermediate visual states while major design changes were still pending.

Do not repeat that workflow mistake.

---

## 16. Local operator context

User repo path:

`D:\Orion\orion-personal-ai`

Accepted Hermes Python path used in review tooling:

`$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\python.exe`

Review launchers have been generated externally during chat. They are not production repo artifacts unless explicitly committed.

Do not assume a particular launcher file still exists on the user's machine; regenerate from current exact head as needed.

---

## 17. Current review state at handoff

Owner's latest assessment:

- improved relative to earlier attempts
- still many issues
- not close enough for acceptance
- third review image missing approval
- composer remains visibly problematic
- biggest remaining problem is compositional system/layout discipline

The owner is going to bed and asked for GitHub handoff so another agent can continue.

Therefore:

**Stop here as a handoff checkpoint.**

Do not mark PR #51 ready.
Do not merge PR #51.
Do not start reconnect/hydration.
Do not claim the visual goal is met.

---

## 18. Definition of done for PR #51

PR #51 can only become merge-ready when all of the following are true:

1. owner says overall visual direction is genuinely close to the target
2. hero/conversation/composer form one coherent central experience
3. conversation readability/structure is strong
4. composer interaction states are unambiguous
5. right rail approval/activity/memory hierarchy is strong
6. left rail is compositionally intentional and readable
7. header/nav/telemetry hierarchy is coherent
8. responsive behavior works across common desktop widths and zoom
9. approval-over-summon fixture is reliable
10. exact approval/diff truth semantics remain intact
11. focused source tests pass
12. full relevant HUD suite passes
13. final bounded visual acceptance passes on exact head
14. Hermes installed source/rollback evidence unchanged
15. worktree clean
16. PR exact accepted head recorded
17. PR no longer draft
18. mergeability clean
19. final merge commit recorded in docs

---

## 19. First commands/actions for the next agent

The next agent should start by reading:

1. `docs/phase3/ui-convergence-visual-contract.md`
2. this handoff file
3. PR #51 body/comments
4. `hud/static/index.html`
5. `hud/static/target-layout.css`
6. `hud/static/app.js`
7. `hud/static/orion-hero.svg`
8. `hud/tests/probe_ui_convergence.py`
9. `hud/tests/probe_approval_surface.py`
10. `hud/tests/test_approval_rendering.cjs`
11. `hud/tests/test_ui_visual_convergence.py`

Then re-query PR #51 exact head and mergeability before making any writes.

---

## 20. Final handoff summary

The structural foundation is accepted and merged.

The active visual PR is a substantial but unfinished rewrite.

The implementation is now conceptually pointed at the correct target, but the visual system still needs disciplined architectural refinement.

The next agent should **not** restart from the old Observatory/HUD design and should **not** return to incremental decorative tweaking.

The correct continuation is:

**formalize the layout system → fix composer → unify hero/conversation → normalize rails/header → stabilize fixture → clean CSS → review visually → only then run final acceptance.**
