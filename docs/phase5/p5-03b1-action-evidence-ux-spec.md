# P5-03B1 — Action / Diff / Evidence UX Specification

Status: **IMPLEMENTED WITH P5-03B2 CANDIDATE**

## Intent

P5-03B makes the accepted P5-03A browser-safe projection legible without
moving any consequential authority into the browser. Hermes remains
session/run/tool/approval authority and the vault plugin remains the
protected-action execution/evidence authority.

The HUD may explain projected facts. It may not infer a protected success,
recreate a missing approval, promote historical preview evidence back into an
actionable plan, or use browser-local state as recovery/action truth.

## Layout

The right rail becomes a contextual action/evidence region.

- **Agent Activity** remains descriptive live tool activity.
- **Approval Required** is prioritized ahead of Action Evidence whenever a
  decision is pending, remains a separate amber decision surface, and explicitly
  states that approval is not execution evidence.
- **Action Evidence** appears only when a protected-action projection exists.
- Capabilities and boundary panels remain secondary.

The action panel contains:

1. a semantic state badge and plain-language summary;
2. compact operation, canonical target, execution, and recovery facts;
3. an exact monospace diff area when the projection carries an exact diff;
4. up to five recent projected evidence records for the selected Hermes
   session; and
5. collapsed, expandable technical evidence using only already allowlisted
   projection fields.

Recent evidence is informational only. It is not clickable and cannot change
execution, approval, recovery, or selected authoritative state.

## Semantic state presentation

- `preview_ready`: cyan, exact preview available, mutation not claimed.
- `approval_requested`: amber, decision required.
- `approval_accepted`: amber, decision accepted, execution **UNPROVEN**.
- `approval_denied`: neutral, no protected success claimed.
- `succeeded`: green, only because P5-03A already established authoritative
  success evidence.
- `stale_plan` / `refused`: amber, mutation not performed.
- `failed`: red; recovery-required is displayed only when projected.
- `unknown` / `unavailable`: neutral and explicit.

The visual layer never upgrades one state into another.

## Diff and evidence rules

Exact diff text is rendered with `textContent` in a scrollable monospace
surface. No Markdown/HTML interpretation occurs.

The primary facts use projected operation/action/tool identifiers and projected
target/source paths. Recovery presentation distinguishes `REQUIRED`, a
projected recovery state, a linked recovery identifier whose availability is
still unavailable, and `UNOBSERVED`.

Technical evidence is expandable rather than forced into the conversation. It
is restricted to the browser-safe fields already produced by P5-03A; raw JSON,
provider payloads, stack traces, arbitrary tool arguments, secrets, recovery
directory paths, and proposed file bytes are not rendered.

## Reconnect behavior

P5-03B does not invent a new browser store. On load/session selection the
existing P5-03A hydration endpoint remains the source of completed action
evidence. Empty, failed, stale-session, unavailable hydration, or disappearance
of the selected session clears the presentation rather than retaining another
session's evidence.

## Acceptance

- approval accepted is visually distinct from execution succeeded;
- exact diff remains byte-preserving text;
- technical evidence is collapsed by default and allowlisted;
- cross-session evidence cannot remain visible after clearing/hydration or
  selected-session disappearance;
- pending approval controls precede contextual evidence and are scrolled into
  view when the decision surface opens;
- recent evidence has no action controls;
- no new browser persistence, runtime authority, approval engine, event store,
  recovery executor, or vault access is introduced.
