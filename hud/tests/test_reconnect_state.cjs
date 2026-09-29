import test from "node:test";
import assert from "node:assert/strict";

import {
  RUN_LOCATOR_KEY,
  classifyReconnectRunStatus,
  encodeRunLocator,
  parseRunLocator,
} from "../static/reconnect-state.js";

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

test("poisoned or cross-session locator is rejected", () => {
  for (const raw of [
    "",
    "{bad",
    JSON.stringify({ version: 1, session_id: "session_1", run_id: "" }),
    JSON.stringify({ version: 1, session_id: "session_1", run_id: " run_1 " }),
    JSON.stringify({ version: 1, session_id: "session_1", run_id: "run_1", state: "succeeded" }),
  ]) {
    if (raw.includes('"state"')) {
      const parsed = parseRunLocator(raw, "session_1");
      assert.deepEqual(parsed, { sessionId: "session_1", runId: "run_1" });
      continue;
    }
    assert.equal(parseRunLocator(raw, "session_1"), null);
  }
  assert.equal(
    parseRunLocator(
      encodeRunLocator("session_other", "run_1"),
      "session_1",
    ),
    null,
  );
});

test("authoritative matching active run can be adopted", () => {
  assert.deepEqual(
    classifyReconnectRunStatus(
      {
        object: "orion.run_status",
        run_id: "run_1",
        session_id: "session_1",
        status: "running",
        action_state: "unobserved",
      },
      "session_1",
      "run_1",
    ),
    {
      kind: "active",
      runId: "run_1",
      sessionId: "session_1",
      status: "running",
    },
  );
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
