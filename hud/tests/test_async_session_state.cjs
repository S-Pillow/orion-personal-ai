// Exercise the real async HUD functions with controlled response ordering.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const app = fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8")
  .replace(/\r\n/g, "\n");
function functionSource(name) {
  const start = app.search(new RegExp(`^(?:async )?function ${name}\\(`, "m"));
  assert.ok(start >= 0, `missing ${name}`);
  const rest = app.slice(start);
  const end = rest.indexOf("\n}\n");
  assert.ok(end >= 0, `missing closing brace for ${name}`);
  return rest.slice(0, end + 3);
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function harness(names, overrides = {}) {
  const calls = [];
  const state = {
    sessionId: "session_1", activeRunId: "", streaming: false,
    approvalEvent: null, actionProjection: null, actionEvidence: [],
    historyRequestId: 0, evidenceRequestId: 0, reconnectRequestId: 0,
  };
  let locator = { sessionId: "session_1", runId: "run_1" };
  const context = vm.createContext({
    state, calls,
    ui: {
      composer: { dataset: {} }, stopButton: {}, sendButton: {},
      newSession: {}, sessionSelect: {}, messageInput: { value: "hello" },
    },
    readRunLocator: () => locator,
    clearRunLocator: () => { locator = null; calls.push("clearLocator"); },
    renderMessages: (payload) => calls.push(payload),
    showTranscriptEmpty: (text) => calls.push(text),
    refreshActionEvidence: async () => {},
    clearActionProjection: () => { state.actionProjection = null; calls.push("clearEvidence"); },
    renderReconnectUnavailable: (reason) => calls.push(reason),
    updateRunControls: () => calls.push("controls"),
    setCore: (...args) => calls.push(args),
    hideApproval: () => { state.approvalEvent = null; calls.push("hideApproval"); },
    presentActionProjection: (projection) => { state.actionProjection = projection; calls.push(projection); },
    arrayFrom: (payload) => payload.items || [],
    syncProvenancePresentation: () => {},
    appendMessage: () => calls.push("appendMessage"),
    corePresence: { lookAt: () => {} },
    streamTurn: async () => calls.push("streamTurn"),
    loadMessages: async () => {},
    reconcileReconnectState: async () => {},
    ...overrides,
  });
  const reconnect = fs.readFileSync(path.join(__dirname, "../static/reconnect-state.js"), "utf8")
    .replaceAll("export const ", "const ").replaceAll("export function ", "function ");
  vm.runInContext(reconnect + "\n" + names.map(functionSource).join("\n"), context);
  return { context, state, calls };
}

for (const fails of [false, true]) {
  test(`late history ${fails ? "failure" : "success"} cannot replace another session`, async () => {
    const response = deferred();
    const { context, state, calls } = harness(["loadMessages"], { api: () => response.promise });
    const pending = context.loadMessages();
    state.sessionId = "session_2";
    if (fails) response.reject(new Error("old session failed"));
    else response.resolve({ messages: ["old history"] });
    await pending;
    assert.deepEqual(calls, []);
  });
}

test("newest history request wins even when selection returns to the same session", async () => {
  const old = deferred(), latest = deferred();
  let count = 0;
  const { context, calls } = harness(["loadMessages"], { api: () => (++count === 1 ? old : latest).promise });
  const first = context.loadMessages(), second = context.loadMessages();
  latest.resolve({ messages: ["new history"] });
  await second;
  old.resolve({ messages: ["old history"] });
  await first;
  assert.equal(calls.length, 1);
  assert.equal(calls[0].messages[0], "new history");
});

test("history requested before a turn cannot erase the live transcript", async () => {
  const response = deferred();
  const { context, state, calls } = harness(["loadMessages"], { api: () => response.promise });
  const pending = context.loadMessages();
  state.streaming = true;
  response.resolve({ messages: ["pre-turn history"] });
  await pending;
  assert.deepEqual(calls, []);
});

test("late empty action evidence cannot clear a live approval projection", async () => {
  const response = deferred();
  const { context, state, calls } = harness(["refreshActionEvidence"], { api: () => response.promise });
  const pending = context.refreshActionEvidence();
  state.streaming = true;
  state.approvalEvent = { run_id: "run_1" };
  state.actionProjection = { state: "approval_requested" };
  response.resolve({ items: [] });
  await pending;
  assert.equal(state.actionProjection?.state, "approval_requested");
  assert.deepEqual(calls, []);
});

for (const fails of [false, true]) {
  test(`stale reconnect ${fails ? "failure" : "success"} cannot overwrite a new streamed run`, async () => {
    const response = deferred();
    const { context, state, calls } = harness(["reconcileReconnectState"], { api: () => response.promise });
    const pending = context.reconcileReconnectState();
    state.streaming = true;
    state.activeRunId = "run_new";
    state.approvalEvent = { run_id: "run_new" };
    if (fails) response.reject(new Error("old request failed"));
    else response.resolve({ object: "orion.run_status", session_id: "session_1", run_id: "run_1", status: "running" });
    await pending;
    assert.equal(state.activeRunId, "run_new");
    assert.equal(state.approvalEvent?.run_id, "run_new");
    assert.deepEqual(calls, []);
  });
}

test("expired run clears previously adopted STOP target", async () => {
  const { context, state } = harness(["reconcileReconnectState"], {
    api: async () => { throw Object.assign(new Error("expired"), { status: 404 }); },
  });
  state.activeRunId = "run_1";
  await context.reconcileReconnectState();
  assert.equal(state.activeRunId, "");
});

test("transient reconnect failure retains the last active target for STOP", async () => {
  const { context, state } = harness(["reconcileReconnectState"], {
    api: async () => { throw Object.assign(new Error("offline"), { status: 502 }); },
  });
  state.activeRunId = "run_1";
  await context.reconcileReconnectState();
  assert.equal(state.activeRunId, "run_1");
});

test("older reconnect response cannot replace a newer terminal observation", async () => {
  const old = deferred(), latest = deferred();
  let count = 0;
  const { context, state } = harness(["reconcileReconnectState"], {
    api: () => (++count === 1 ? old : latest).promise,
  });
  const first = context.reconcileReconnectState(), second = context.reconcileReconnectState();
  const payload = { object: "orion.run_status", session_id: "session_1", run_id: "run_1" };
  latest.resolve({ ...payload, status: "completed" });
  await second;
  old.resolve({ ...payload, status: "running" });
  await first;
  assert.equal(state.activeRunId, "");
});

test("reconnect rechecks session after waiting for evidence hydration", async () => {
  const evidence = deferred(), entered = deferred();
  const { context, state, calls } = harness(["reconcileReconnectState"], {
    api: async () => ({ object: "orion.run_status", session_id: "session_1", run_id: "run_1", status: "completed" }),
    refreshActionEvidence: () => { entered.resolve(); return evidence.promise; },
  });
  const pending = context.reconcileReconnectState();
  await entered.promise;
  state.sessionId = "session_2";
  calls.length = 0;
  evidence.resolve();
  await pending;
  assert.deepEqual(calls, []);
});

test("fresh active reconnect still adopts the matching run", async () => {
  const { context, state } = harness(["reconcileReconnectState"], {
    api: async () => ({ object: "orion.run_status", session_id: "session_1", run_id: "run_1", status: "running" }),
  });
  assert.equal(await context.reconcileReconnectState(), true);
  assert.equal(state.activeRunId, "run_1");
});

test("newest evidence request wins for the same session", async () => {
  const old = deferred(), latest = deferred();
  let count = 0;
  const { context, state } = harness(["refreshActionEvidence"], {
    api: () => (++count === 1 ? old : latest).promise,
  });
  const first = context.refreshActionEvidence(), second = context.refreshActionEvidence();
  latest.resolve({ items: [{ state: "failed", message_id: "latest" }] });
  await second;
  old.resolve({ items: [{ state: "succeeded", message_id: "old" }] });
  await first;
  assert.equal(state.actionProjection.message_id, "latest");
});

test("recovered active run blocks new-session and send controls", () => {
  const { context, state } = harness(["updateRunControls"]);
  state.activeRunId = "run_1";
  context.updateRunControls();
  assert.equal(context.ui.sendButton.disabled, true);
  assert.equal(context.ui.newSession.disabled, true);
  assert.equal(context.ui.sessionSelect.disabled, true);
  assert.equal(context.ui.stopButton.disabled, false);
});

test("Enter submission cannot start a second turn during a recovered active run", async () => {
  const { context, state } = harness(["sendMessage"]);
  state.activeRunId = "run_1";
  await context.sendMessage({ preventDefault() {} });
  assert.equal(state.activeRunId, "run_1");
  assert.equal(state.streaming, false);
});

test("status refresh cannot set READY after a streamed turn starts during reconciliation", async () => {
  const response = deferred(), entered = deferred();
  const { context, state, calls } = harness(["refreshStatus"], {
    api: async () => ({ hermes: { online: true, detailed: { status: "ok" } } }),
    refreshDiscovery: async () => {}, refreshSessions: async () => {},
    setHermesOnline: () => {}, syncSystemWorkspace: () => {},
    reconcileReconnectState: () => { entered.resolve(); return response.promise; },
  });
  Object.assign(context.ui, { workspaceReadiness: {}, bridgeValue: {}, credentialValue: {} });
  const pending = context.refreshStatus();
  await entered.promise;
  state.streaming = true;
  response.resolve(false);
  await pending;
  assert.deepEqual(calls, []);
});

test("session disappearance clears transcript and the old STOP target", async () => {
  const { context, state, calls } = harness(["refreshSessions"], {
    api: async () => ({ items: [] }),
    document: { createElement: () => ({}) },
    localStorage: { removeItem: () => {} },
    createProvenanceState: () => ({}), syncSessionLabels: () => {},
  });
  Object.assign(context.ui.sessionSelect, { replaceChildren: () => {}, append: () => {}, options: [] });
  context.ui.sessionMeta = {};
  state.activeRunId = "run_1";
  await context.refreshSessions();
  assert.equal(state.sessionId, "");
  assert.equal(state.activeRunId, "");
  assert.ok(calls.some((value) => typeof value === "string" && value.startsWith("Choose a conversation")));
});
