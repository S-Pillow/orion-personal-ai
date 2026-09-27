# Orion UI Convergence Visual Contract

Status: **FOUNDATION ACCEPTED / FINAL VISUAL PASS PENDING**

Date: 2026-09-27  
Foundation merge: `d32137066a6ef20b57e1045fb8a827779cc47440`

## 1. Product intent

Orion is a persistent personal companion surface, not a generic AI web app and not a gimmicky sci-fi dashboard.

The UI should feel like a place Steven returns to: calm, legible, low-clutter, companion-first, and stateful.

The visual hierarchy must communicate:

1. Orion's current presence/state;
2. the active conversation or focused task;
3. consequential approvals/actions when they exist;
4. contextual evidence or summoned content;
5. diagnostics and system detail as secondary information.

## 2. Visual direction

### Overall tone

- matte graphite / charcoal foundation;
- restrained cyan / teal accents;
- broad desktop composition;
- readable typography;
- thin outlined structure;
- quiet depth rather than glassmorphism;
- no unnecessary glow, particle fields, spinning globes, permanent telemetry walls, or Iron-Man-style visual noise.

### Orion Core

The Core is the companion's central visual presence.

Direction:

- celestial / masked aperture rather than helmet or photoreal avatar;
- 2D / 2.5D treatment;
- ambient ring / aperture / star-like geometry;
- subtle blink and micro-saccade behavior;
- restrained parallax/head-motion cue;
- deterministic gaze toward active approval/focused surface;
- state-linked breathing/pulse, not decorative constant animation;
- degraded/error states become quieter/dimmer rather than theatrical;
- reduced-motion mode remains first-class.

### Center workspace

Conversation is the default and dominant workspace.

The center should carry:

- conversation;
- approval focus;
- protected action evidence;
- memory context;
- system detail;
- summoned media/tool/evidence content.

The user should not feel forced into unrelated page navigation to inspect a focused surface.

### Rails and diagnostics

The existing left/right rails remain useful but must be visually demoted.

They should read as quiet context, not as the main product.

Permanent diagnostic framing should be reduced.

Secondary panels include:

- system link;
- session controls;
- memory authority;
- agent activity;
- capabilities;
- inventory;
- boundaries.

Consequential approval controls remain visually stronger than contextual evidence.

## 3. Interaction rules

- Approval focus outranks summon/evidence focus.
- Action Evidence never outranks a pending human decision.
- Conversation selection remains underneath temporary focus surfaces.
- Summoned content returns to the prior workspace when dismissed.
- Core gaze/presentation focus may move toward the active surface but must not imply camera/vision capability.
- STOP/error/offline/degraded states remain explicit and understandable.

## 4. Truth boundaries

UI convergence changes presentation only.

It must not:

- create session authority;
- create approval authority;
- create action truth;
- create a durable browser action ledger;
- infer protected execution from generic tool/run completion;
- turn approval acknowledgement into success;
- recreate missing approvals from browser state;
- claim recovery availability without authoritative evidence.

P5-03A/P5-03B semantics remain controlling.

## 5. Typography and density

- prioritize readable body text;
- avoid tiny terminal-font overload;
- mono typography is reserved for code, diff, identifiers, and compact technical labels;
- reduce all-caps where it harms readability;
- retain compact technical labels only where they improve scanning;
- whitespace should create hierarchy rather than empty decoration.

## 6. Responsive behavior

Desktop:

- Core + center workspace dominate;
- rails are narrower and quieter;
- approval/action surfaces remain clearly ordered.

Narrow/tablet:

- conversation remains primary;
- approval controls stay reachable;
- exact diff remains scrollable;
- secondary diagnostics may stack below the primary workspace;
- no horizontal layout should force the user to pass contextual evidence before reaching an approval.

## 7. Explicit dislikes / exclusions

Do not converge toward:

- heavy helmet imagery;
- photoreal avatar;
- full 3D character;
- spinning globe;
- dense permanent grids;
- decorative telemetry;
- meaningless particles;
- glassmorphism-heavy cards;
- large numbers of glowing boxes;
- tiny terminal-font dashboards;
- theatrical motion unsupported by system state.

## 8. Acceptance standard

The UI is not considered converged merely because colors, borders, or spacing changed.

Acceptance requires a material hierarchy shift:

- Orion Core visibly reads as the companion presence;
- conversation/focused work reads as the main product;
- diagnostics are secondary;
- approvals remain primary when active;
- the experience feels like one coherent personal system rather than a collection of diagnostic panels.


## 9. Foundation status

The structural foundation implementing this contract merged through PR #49.

That foundation is not the final visual destination. The remaining visual pass must materially improve:

- Orion Core presence and identity;
- center-workspace composition;
- typography and reading comfort;
- spacing and rhythm;
- relationship between conversation and contextual surfaces;
- reduction of residual diagnostic-dashboard feel;
- final companion-first polish across desktop and narrow layouts.

Final visual acceptance should occur after that broader design pass rather than treating the structural foundation as the finished UI.
