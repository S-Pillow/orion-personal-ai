// P5-03B pure presentation contract tests.
// Run with: node --test hud/tests/test_action_workspace_semantics.cjs
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const app = fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8");
const start = app.indexOf("const ACTION_TECHNICAL_FIELDS =");
const end = app.indexOf("function appendDefinitionRow", start);
assert.ok(start >= 0 && end > start, "action workspace pure helper block missing");
const source = app.slice(start, end) + `
this.p5 = {
  actionStatePresentation,
  actionOperation,
  actionPrimaryTarget,
  actionRecoveryLabel,
  technicalEvidenceRows,
};`;
const context = vm.createContext({});
vm.runInContext(source, context);
const p5 = context.p5;

test("approval acceptance remains execution-unproven", () => {
  const view = p5.actionStatePresentation({ state: "approval_accepted" });
  assert.equal(view.label, "DECISION ACCEPTED");
  assert.equal(view.execution, "UNPROVEN");
  assert.match(view.summary, /unproven/i);
});

test("authoritative terminal states remain visually distinct", () => {
  assert.equal(
    p5.actionStatePresentation({ state: "succeeded" }).execution,
    "SUCCEEDED",
  );
  assert.equal(
    p5.actionStatePresentation({ state: "failed" }).execution,
    "FAILED",
  );
  assert.equal(
    p5.actionStatePresentation({ state: "stale_plan" }).execution,
    "NOT PERFORMED",
  );
});

test("recovery labeling never invents availability", () => {
  assert.equal(
    p5.actionRecoveryLabel({ recovery_required: true }),
    "REQUIRED",
  );
  assert.equal(
    p5.actionRecoveryLabel({ recovery_id: "a".repeat(64) }),
    "LINKED // STATUS UNAVAILABLE",
  );
  assert.equal(
    p5.actionRecoveryLabel({}),
    "UNOBSERVED",
  );
});

test("technical evidence excludes arbitrary unlisted fields", () => {
  const rows = p5.technicalEvidenceRows({
    schema_version: "orion.action-projection.v1",
    run_id: "run_1",
    target_canonical_path: "C:/vault/note.md",
    api_key: "DO-NOT-LEAK",
    stack: "DO-NOT-LEAK",
    raw_args: { secret: "DO-NOT-LEAK" },
  });
  const serialized = JSON.stringify(rows);
  assert.match(serialized, /run_1/);
  assert.match(serialized, /C:\/vault\/note\.md/);
  assert.doesNotMatch(serialized, /DO-NOT-LEAK/);
  assert.doesNotMatch(serialized, /api_key|stack|raw_args/);
});


test("P5-03B3 visual state matrix preserves truth distinctions", () => {
  const cases = [
    ["preview_ready", "PREVIEW READY", "NOT EXECUTED", "ready"],
    ["approval_requested", "DECISION REQUIRED", "AWAITING DECISION", "attention"],
    ["approval_accepted", "DECISION ACCEPTED", "UNPROVEN", "attention"],
    ["approval_denied", "DENIED", "NOT EXECUTED", "neutral"],
    ["succeeded", "SUCCEEDED", "SUCCEEDED", "success"],
    ["stale_plan", "STALE", "NOT PERFORMED", "attention"],
    ["refused", "REFUSED", "NOT PERFORMED", "attention"],
    ["failed", "FAILED", "FAILED", "failure"],
    ["unavailable", "UNAVAILABLE", "UNAVAILABLE", "neutral"],
    ["unknown", "UNKNOWN", "UNKNOWN", "neutral"],
  ];

  for (const [state, label, execution, tone] of cases) {
    const view = p5.actionStatePresentation({ state });
    assert.equal(view.label, label, state);
    assert.equal(view.execution, execution, state);
    assert.equal(view.tone, tone, state);
  }
});

test("P5-03B3 amber attention states never collapse into success", () => {
  for (const state of ["approval_requested", "approval_accepted", "stale_plan", "refused"]) {
    const view = p5.actionStatePresentation({ state });
    assert.equal(view.tone, "attention", state);
    assert.notEqual(view.execution, "SUCCEEDED", state);
  }
});
