// Execute the production approval renderer with a small DOM double.
// Run explicitly with: node --test hud/tests/test_approval_rendering.cjs
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const app = fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8");
const start = app.indexOf("function showApproval(data) {");
const end = app.indexOf("async function decideApproval", start);
assert.ok(start >= 0 && end > start);
const source = app.slice(start, end);

function renderer() {
  const clicked = [];
  const detail = { textContent: "", scrollTop: 99 };
  Object.defineProperty(detail, "innerHTML", { set() { throw Error("Unsafe HTML rendering"); } });
  const actions = {
    children: [],
    replaceChildren() { this.children = []; },
    append(child) { this.children.push(child); },
  };
  const context = vm.createContext({
    state: {},
    syncProvenancePresentation() {},
    workspaceController: { setApprovalFocus() {} },
    ui: { approvalPanel: { classList: { remove() {} } }, approvalDetail: detail, approvalActions: actions },
    document: { createElement() { return {
      classList: { add() {} },
      addEventListener(_event, callback) { this.click = callback; },
    }; } },
    decideApproval(choice) { clicked.push(choice); },
  });
  vm.runInContext(source, context);
  return { show: (data) => context.showApproval(data), detail, actions, clicked };
}

test("command does not hide a long exact description, CRLF, Unicode or literal markup", () => {
  const r = renderer();
  const description = "Target: C:\\fixture\\vault\\note.md\r\n" +
    "--- old\r\n+++ new\r\n" + "-old\r\n+雪 <script>literal</script> & text\r\n".repeat(200) +
    "+END-OF-DIFF\r\n\\ No newline at end of file\n";
  assert.ok(description.length > 1000);
  r.show({ command: "orion_vault_apply_plan", description, choices: ["once", "deny"] });
  assert.equal(r.detail.textContent, "Command / tool:\norion_vault_apply_plan\n\nDescription:\n" + description);
  assert.equal(r.detail.scrollTop, 0);
  assert.deepEqual(r.actions.children.map(b => b.textContent), ["ALLOW ONCE", "DENY"]);
  r.actions.children.forEach(b => b.click());
  assert.deepEqual(r.clicked, ["once", "deny"]);
});

test("legacy command-only and description-only requests remain complete", () => {
  const r = renderer();
  for (const key of ["command", "description"]) {
    const value = "a".repeat(18000) + "TAIL";
    r.show({ [key]: value });
    assert.ok(r.detail.textContent.endsWith(value));
  }
  assert.deepEqual(r.actions.children.map(b => b.textContent), ["ALLOW ONCE", "ALLOW SESSION", "ALWAYS ALLOW", "DENY"]);
});

test("unknown choices are not granted and new requests replace old details/actions", () => {
  const r = renderer();
  r.show({ description: "previous", choices: ["once", "deny"] });
  r.show({ description: "current", choices: ["approve_all", "deny"] });
  assert.equal(r.detail.textContent, "Description:\ncurrent");
  assert.deepEqual(r.actions.children.map(b => b.textContent), ["DENY"]);
  r.show({ reason: "fallback reason", choices: [] });
  assert.equal(r.detail.textContent, "fallback reason");
  assert.equal(r.actions.children.length, 0);
});
