const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function loadModule(filename, names) {
  let source = fs.readFileSync(
    path.join(__dirname, "../static", filename),
    "utf8",
  );
  source = source.replaceAll("export function ", "function ");
  source += "\nmodule.exports = {" + names.join(",") + "};\n";
  const context = vm.createContext({
    module: { exports: {} },
    exports: {},
    URL,
    String,
    Array,
    Set,
    Boolean,
    Error,
  });
  vm.runInContext(source, context);
  return context.module.exports;
}

const summon = loadModule(
  "summon-state.js",
  ["normalizeSummonPayload", "installSummonController"],
);

const workspace = loadModule(
  "workspace-state.js",
  ["installWorkspaceController"],
);

function textNode(initial = "") {
  const node = { textContent: initial, hidden: false };
  Object.defineProperty(node, "innerHTML", {
    set() {
      throw new Error("unsafe HTML rendering");
    },
  });
  return node;
}

function buttonNode() {
  const listeners = new Map();
  return {
    addEventListener(name, callback) {
      listeners.set(name, callback);
    },
    removeEventListener(name, callback) {
      if (listeners.get(name) === callback) listeners.delete(name);
    },
    click() {
      listeners.get("click")?.();
    },
  };
}

function fixture() {
  const workspaceRoot = { dataset: { workspace: "conversation" } };
  const workspaceController = workspace.installWorkspaceController(
    workspaceRoot,
  );
  const panel = {
    dataset: {},
    hidden: true,
    focused: 0,
    focus() {
      this.focused += 1;
    },
  };
  const title = textNode();
  const kind = textNode();
  const source = textNode();
  const body = textNode();
  const link = textNode();
  link.attributes = {};
  link.removeAttribute = function (name) {
    delete this.attributes[name];
    if (name === "href") this.href = "";
  };
  const dismiss = buttonNode();
  const coreStage = { dataset: {} };

  const controller = summon.installSummonController({
    panel,
    titleNode: title,
    kindNode: kind,
    sourceNode: source,
    bodyNode: body,
    linkNode: link,
    dismissButton: dismiss,
    workspaceController,
    coreStage,
  });

  return {
    controller,
    workspaceController,
    workspaceRoot,
    panel,
    title,
    kind,
    source,
    body,
    link,
    dismiss,
    coreStage,
  };
}

test("literal markup stays literal and summon focus preserves selected workspace", () => {
  const f = fixture();
  const payload = f.controller.show({
    kind: "evidence",
    title: "Approval evidence",
    source: "fixture://source",
    content: "<b>literal</b>\n<script>not executable</script>",
  });

  assert.equal(payload.kind, "evidence");
  assert.equal(f.title.textContent, "Approval evidence");
  assert.equal(f.body.textContent, "<b>literal</b>\n<script>not executable</script>");
  assert.equal(f.panel.hidden, false);
  assert.equal(f.panel.dataset.summonKind, "evidence");
  assert.equal(f.workspaceRoot.dataset.workspace, "conversation");
  assert.equal(f.workspaceRoot.dataset.workspaceFocus, "summon");
  assert.equal(f.coreStage.dataset.presentationFocus, "summon");
  assert.equal(f.panel.focused, 1);
});

test("approval focus outranks summon and dismiss restores approval then normal focus", () => {
  const f = fixture();
  f.controller.show({
    kind: "text",
    title: "Temporary panel",
    content: "hello",
  });
  f.workspaceController.setApprovalFocus(true);

  assert.equal(f.workspaceRoot.dataset.workspaceFocus, "approval");

  f.dismiss.click();
  assert.equal(f.panel.hidden, true);
  assert.equal(f.workspaceRoot.dataset.workspaceFocus, "approval");
  assert.equal(f.coreStage.dataset.presentationFocus, "normal");

  f.workspaceController.setApprovalFocus(false);
  assert.equal(f.workspaceRoot.dataset.workspaceFocus, "normal");
});

test("link kind allows only http and https and clears prior content", () => {
  const f = fixture();

  assert.throws(
    () => f.controller.show({
      kind: "link",
      title: "bad",
      href: "javascript:alert(1)",
    }),
    /summon_link_scheme_rejected/,
  );

  const payload = f.controller.show({
    kind: "link",
    title: "Reference",
    source: "operator",
    href: "https://example.com/path?q=1",
  });

  assert.equal(payload.href, "https://example.com/path?q=1");
  assert.equal(f.link.href, payload.href);
  assert.equal(f.link.textContent, payload.href);
  assert.equal(f.link.hidden, false);

  f.controller.show({
    kind: "text",
    title: "Next",
    content: "safe",
  });

  assert.equal(f.link.hidden, true);
  assert.equal(f.link.href, "");
  assert.equal(f.link.textContent, "");
});

test("unsupported and oversized payloads fail before presentation focus", () => {
  const f = fixture();

  assert.throws(
    () => f.controller.show({ kind: "html", title: "bad", content: "x" }),
    /summon_kind_rejected/,
  );
  assert.equal(f.panel.hidden, true);
  assert.equal(f.workspaceRoot.dataset.workspaceFocus, "normal");

  assert.throws(
    () => f.controller.show({
      kind: "text",
      title: "large",
      content: "x".repeat(12001),
    }),
    /summon_text_too_large/,
  );
  assert.equal(f.panel.hidden, true);
});
