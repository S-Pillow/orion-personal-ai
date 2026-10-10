const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function loadReconnectState() {
  const context = vm.createContext({ module: { exports: {} }, JSON, Set });
  const source = fs
    .readFileSync(path.join(__dirname, "../static/reconnect-state.js"), "utf8")
    .replaceAll("export const ", "const ")
    .replaceAll("export function ", "function ");
  vm.runInContext(
    source
      + "\nmodule.exports = { RUN_LOCATOR_KEY, classifyReconnectRunStatus, encodeRunLocator, parseRunLocator };",
    context,
  );
  return context.module.exports;
}

const {
  RUN_LOCATOR_KEY,
  classifyReconnectRunStatus,
  encodeRunLocator,
  parseRunLocator,
} = loadReconnectState();

test("run locator stores identifiers only", () => {
  assert.equal(RUN_LOCATOR_KEY, "orion.hermesRunLocator");
  const raw = encodeRunLocator("session_1", "run_1");
  assert.deepEqual(JSON.parse(raw), {
    version: 1,
    session_id: "session_1",
    run_id: "run_1",
  });
  assert.equal(raw.includes("success"), false);
  assert.equal(raw.includes("approval"), false);
});

test("poisoned or cross-session locator is rejected or reduced to identifiers", () => {
  for (const raw of [
    "",
    "{bad",
    JSON.stringify({ version: 1, session_id: "session_1", run_id: "" }),
    JSON.stringify({ version: 1, session_id: "session_1", run_id: " run_1 " }),
  ]) {
    assert.equal(parseRunLocator(raw, "session_1"), null);
  }

  const poisoned = parseRunLocator(
    JSON.stringify({
      version: 1,
      session_id: "session_1",
      run_id: "run_1",
      state: "succeeded",
      approval: "always",
      recovery_available: true,
    }),
    "session_1",
  );
  assert.equal(poisoned.sessionId, "session_1");
  assert.equal(poisoned.runId, "run_1");
  assert.equal(poisoned.state, undefined);
  assert.equal(poisoned.approval, undefined);

  assert.equal(
    parseRunLocator(
      encodeRunLocator("session_other", "run_1"),
      "session_1",
    ),
    null,
  );
});

test("authoritative matching nonterminal Hermes statuses can be adopted", () => {
  for (const status of [
    "queued",
    "running",
    "in_progress",
    "waiting_for_approval",
    "stopping",
  ]) {
    const result = classifyReconnectRunStatus(
      {
        object: "orion.run_status",
        run_id: "run_1",
        session_id: "session_1",
        status,
        action_state: "unobserved",
      },
      "session_1",
      "run_1",
    );
    assert.equal(result.kind, "active", status);
    assert.equal(result.runId, "run_1", status);
    assert.equal(result.sessionId, "session_1", status);
    assert.equal(result.status, status);
  }
});

test("terminal run is locator evidence not protected action success", () => {
  const result = classifyReconnectRunStatus(
    {
      object: "orion.run_status",
      run_id: "run_1",
      session_id: "session_1",
      status: "completed",
      action_state: "unobserved",
    },
    "session_1",
    "run_1",
  );
  assert.equal(result.kind, "terminal");
  assert.equal(result.status, "completed");
  assert.equal("actionState" in result, false);
});

test("mismatched and unknown status never become active truth", () => {
  for (const payload of [
    {
      object: "orion.run_status",
      run_id: "run_other",
      session_id: "session_1",
      status: "running",
    },
    {
      object: "orion.run_status",
      run_id: "run_1",
      session_id: "session_other",
      status: "running",
    },
    {
      object: "orion.run_status",
      run_id: "run_1",
      session_id: "session_1",
      status: "mystery",
    },
  ]) {
    assert.equal(
      classifyReconnectRunStatus(
        payload,
        "session_1",
        "run_1",
      ).kind,
      "unavailable",
    );
  }
});
