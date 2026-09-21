import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  SUMMON_LIMITS,
  createSummonState,
  normalizeSummonPayload,
} from "./summon-state.mjs";

test("text payload preserves literal markup as inert text", () => {
  const body = "<script>alert(1)</script><b>literal</b>";
  const value = normalizeSummonPayload({
    schema_version: 1,
    kind: "text",
    title: "Evidence",
    body,
    source: "fixture",
  });
  assert.equal(value.body, body);
});

test("link accepts only http and https", () => {
  for (const url of ["javascript:alert(1)", "data:text/html,x", "file:///c:/x"]) {
    assert.equal(normalizeSummonPayload({
      schema_version: 1,
      kind: "link",
      title: "bad",
      url,
    }), null);
  }
  assert.equal(normalizeSummonPayload({
    schema_version: 1,
    kind: "link",
    title: "good",
    url: "https://example.com/a?b=1",
  }).url, "https://example.com/a?b=1");
});

test("schema, kind, and bounds fail closed", () => {
  assert.equal(normalizeSummonPayload({}), null);
  assert.equal(normalizeSummonPayload({
    schema_version: 2, kind: "text", title: "x", body: "y",
  }), null);
  assert.equal(normalizeSummonPayload({
    schema_version: 1, kind: "iframe", title: "x",
  }), null);
  assert.equal(normalizeSummonPayload({
    schema_version: 1,
    kind: "text",
    title: "x".repeat(SUMMON_LIMITS.title + 1),
    body: "y",
  }), null);
});

test("text and evidence cannot carry a hidden remote URL", () => {
  assert.equal(normalizeSummonPayload({
    schema_version: 1,
    kind: "evidence",
    title: "x",
    body: "y",
    url: "https://example.com/",
  }), null);
});

test("present captures prior workspace once and replacement keeps it", () => {
  const controller = createSummonState("conversation");
  const one = controller.present({
    schema_version: 1, kind: "text", title: "one", body: "1",
  }, "memory");
  assert.equal(one.accepted, true);
  assert.equal(one.state.priorWorkspace, "memory");
  const two = controller.present({
    schema_version: 1, kind: "text", title: "two", body: "2",
  }, "system");
  assert.equal(two.state.payload.title, "two");
  assert.equal(two.state.priorWorkspace, "memory");
  const dismissed = controller.dismiss();
  assert.equal(dismissed.restoreWorkspace, "memory");
  assert.equal(dismissed.state.open, false);
});

test("invalid present leaves existing state unchanged", () => {
  const controller = createSummonState();
  controller.present({
    schema_version: 1, kind: "text", title: "one", body: "safe",
  }, "system");
  const before = controller.snapshot();
  const result = controller.present({
    schema_version: 1, kind: "iframe", title: "bad",
  }, "memory");
  assert.equal(result.accepted, false);
  assert.equal(result.state, before);
});

test("prototype has no network, storage, process, or HTML-injection authority", () => {
  const source = readFileSync(new URL("./summon-state.mjs", import.meta.url), "utf8");
  for (const token of [
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "localStorage",
    "sessionStorage",
    "innerHTML",
    "document.cookie",
    "child_process",
  ]) {
    assert.equal(source.includes(token), false, token);
  }
});
