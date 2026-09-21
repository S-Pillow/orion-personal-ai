# P3-05B / Phase 5 Display-Summon Contract

Status: source design / no runtime authority change  
Date: 2026-09-21  
Baseline: current merged Orion HUD + accepted Hermes v0.20.6 pin

## Goal

Close the remaining Phase 3 summonable-panel requirement and give Phase 5 an explicit visible display tool without creating a second privileged browser channel, exposing the Hermes API key, broadcasting to every future HUD, or turning Orion into a general-purpose iframe proxy.

## Key transport finding from the accepted Hermes pin

The accepted Hermes session-stream adapter already forwards tool lifecycle events through the existing authenticated server-side Hermes -> Orion bridge.

On `tool.started`, the pinned API server sends:

- `message_id`;
- `tool_name`;
- a safe display preview;
- the display/redacted tool `args`.

The Orion HUD already consumes `tool.started` for activity presentation.

On this accepted pin, `tool.completed` does **not** carry the tool result to the HUD stream. Therefore a design that waits for a special JSON tool result would require changing Hermes or adding another channel.

For a presentation-only display tool, the narrowest design is:

1. model invokes `orion_display` with a bounded typed payload;
2. Hermes performs its normal tool preflight and emits `tool.started`;
3. the existing Orion bridge forwards the event unchanged;
4. the HUD recognizes only the exact display tool name, independently validates the bounded payload, and summons the panel;
5. the registered display handler itself performs no network, filesystem, or lifecycle mutation and returns a simple acknowledgement to Hermes.

No extra local HTTP POST from the plugin is required.

## Why not copy Jarvis `hud_display` directly

Jarvis is a useful donor, but its display plugin:

- POSTs from the plugin to a separate `/api/summon` endpoint;
- carries a separate HUD token;
- accepts arbitrary HTTP(S) URLs;
- supports generic iframes;
- broadcasts to every open HUD.

Those choices fit Jarvis' architecture but are broader than the Orion MVP. The Orion PRD explicitly defers stable display identity/target routing to a later phase and warns that multiple HUDs must not accidentally receive the wrong summoned content.

Reuse the product pattern, not the authority shape.

## V1 tool set

### `orion_display`

Presentation-only tool. Suggested schema:

```json
{
  "name": "orion_display",
  "parameters": {
    "type": "object",
    "properties": {
      "schema_version": {"type": "integer", "enum": [1]},
      "kind": {"type": "string", "enum": ["text", "evidence", "link"]},
      "title": {"type": "string", "minLength": 1, "maxLength": 120},
      "body": {"type": "string", "maxLength": 12000},
      "source": {"type": "string", "maxLength": 512},
      "url": {"type": "string", "maxLength": 2048}
    },
    "required": ["schema_version", "kind", "title"]
  }
}
```

Contract:

- `text`: body required; plain text only.
- `evidence`: body required; rendered as preformatted/selectable text plus optional source.
- `link`: URL required; only `http:` or `https:`; show metadata and an explicit user-click link rather than auto-navigating or embedding.
- HTML is never accepted.
- JavaScript/data/file URLs are rejected.
- no iframe in V1.
- no auto-play media in V1.
- no browser fetch proxy.
- no vault/file path parameter.
- no target-device parameter until Phase 7 display identity exists.

The tool handler should validate the same contract and return an acknowledgement such as:

```json
{"success": true, "presentation_requested": true, "mutation_performed": false}
```

It does not need to contact the HUD; the already-forwarded `tool.started.args` event is the presentation signal.

### `orion_display_dismiss`

No-argument presentation-only tool. On its `tool.started` event the HUD dismisses the current summoned panel and restores the previous workspace/focus state.

## HUD controller

Implement a small pure state module rather than baking summon semantics into unrelated chat code.

Suggested state:

```text
closed
  -> present(payload)
open(payload, priorWorkspace)
  -> replace(payload)
  -> dismiss()
closed(priorWorkspace restored)
```

Required behavior:

- one active summoned panel in V1;
- later displays replace the current panel deterministically;
- no implicit broadcast/multi-panel behavior;
- capture the previously selected Conversation/System/Memory workspace;
- summon focuses the center panel and gives the Core a deterministic display/focus gaze;
- dismiss restores the previous workspace;
- Escape and a visible Close button dismiss;
- panel is focusable and keyboard navigable;
- reduced-motion path avoids fly-in animation;
- screen readers receive title/body/source and dismiss state.

## Safe rendering

Treat every display payload as untrusted model/tool input even though it arrived over the authenticated Hermes stream.

- use `textContent` for title, body, evidence, and source;
- never assign model content to `innerHTML`;
- parse links with `new URL(...)` and accept only HTTP(S);
- links use `target="_blank"` plus `rel="noopener noreferrer"`;
- do not automatically fetch a link just because the agent wants it displayed;
- preserve the existing restrictive CSP;
- do not add `frame-src *`, `connect-src *`, or broad remote origins for this slice.

If richer media becomes valuable later, add one media kind at a time with an explicit source policy. Do not start with arbitrary iframes. Browser sandboxing reduces risk but is not a substitute for a narrow content contract.

## Event handling

In the existing `handleStreamEvent` path:

```text
tool.started
  if tool_name == "orion_display":
      normalize + validate data.args
      if valid: present
      else: ignore display request and surface a non-blocking HUD error
  if tool_name == "orion_display_dismiss":
      dismiss
  continue normal activity tracking
```

Do not treat generic tool names or arbitrary tool previews as display authority.

Because the pinned SSE omits tool results on `tool.completed`, rendering at `tool.started` is intentional for this non-mutating presentation action. The HUD revalidates the payload independently so malformed input produces no dangerous DOM action. The handler should be simple enough that a schema-valid invocation has no external failure dependency.

If later requirements demand “render only after handler success,” first look for an installed-version-supported event carrying a stable tool-call ID + result. Do not add a custom socket merely to recreate data already available in Hermes.

## Tests before integration

Pure module tests:

- accepts text/evidence/link V1 payloads;
- rejects unknown schema versions/kinds;
- rejects oversize title/body/source/url;
- rejects javascript/data/file URLs;
- preserves literal `<script>` / `<b>` strings as text;
- deterministic replace and dismiss state;
- restores prior workspace;
- no network/storage/filesystem/process APIs in the state module.

HUD integration tests:

- display `tool.started` summons visibly;
- ordinary tool events never summon;
- dismiss event closes;
- Core focus/gaze changes and restores;
- Conversation transcript/composer remains intact;
- System/Memory state remains intact;
- reduced-motion behavior;
- Escape/Close keyboard path;
- no credential is introduced into browser assets.

Isolated browser fixture:

- fake Hermes SSE emits one `orion_display` call with literal HTML-looking text and one safe link;
- operator confirms text remains literal, link is not auto-opened, panel is visible/focusable, and dismiss restores the prior workspace.

## Phase boundary

P3-05B can close the **summonable-panel shell** with a synthetic display event.

Phase 5 closes the **explicit display tool** after the real Hermes plugin/tool call produces that event on the accepted runtime and the panel becomes visible.

This separation lets the UI shell be tested without installing a plugin and lets the plugin remain presentation-only.

## Future media/device routing

After the V1 text/evidence/link path is trusted:

- image can be added with an explicit source/content policy;
- video can be added with a provider-specific safe embed policy;
- arbitrary webpage iframe remains the highest-risk option and should be justified separately;
- stable display/client IDs and targeted routing belong to Phase 7;
- broadcast-to-all must remain explicit, never an accidental default.

## Value test

This feature is valuable if it lets the user say “show me that evidence / link / result” and have the same Hermes turn visibly focus the relevant content without switching to an invisible browser or copying text manually.

It is not valuable if it becomes a miniature general-purpose browser/server that duplicates existing web tooling. The first slice should optimize for visible, trustworthy handoff—not media spectacle.
