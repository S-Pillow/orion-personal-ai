"use strict";

export const RUN_LOCATOR_KEY = "orion.hermesRunLocator";

const ID_RE = /^[A-Za-z0-9._:-]{1,160}$/;
const ACTIVE_RUN_STATUSES = new Set([
  "queued",
  "running",
  "in_progress",
  // Accepted Hermes/P5 compatibility states that still represent live work.
  "waiting_for_approval",
  "stopping",
]);
const TERMINAL_RUN_STATUSES = new Set([
  "completed",
  "failed",
  "cancelled",
  "stopped",
]);

function exactId(value) {
  return typeof value === "string" && ID_RE.test(value)
    ? value
    : "";
}

export function encodeRunLocator(sessionId, runId) {
  const session = exactId(sessionId);
  const run = exactId(runId);
  if (!session || !run) return "";
  return JSON.stringify({
    version: 1,
    session_id: session,
    run_id: run,
  });
}

export function parseRunLocator(raw, expectedSessionId = "") {
  if (typeof raw !== "string" || !raw) return null;
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!payload || payload.version !== 1) return null;
  const sessionId = exactId(payload.session_id);
  const runId = exactId(payload.run_id);
  if (!sessionId || !runId) return null;
  if (expectedSessionId && sessionId !== expectedSessionId) return null;
  return { sessionId, runId };
}

export function classifyReconnectRunStatus(
  payload,
  expectedSessionId,
  expectedRunId,
) {
  if (!payload || typeof payload !== "object") {
    return { kind: "unavailable", reason: "run_status_missing" };
  }
  if (payload.object !== "orion.run_status") {
    return { kind: "unavailable", reason: "run_status_untrusted_object" };
  }
  const runId = exactId(payload.run_id);
  const sessionId = exactId(payload.session_id);
  const status =
    typeof payload.status === "string"
      ? payload.status.trim().toLowerCase()
      : "";

  if (!runId || runId !== expectedRunId) {
    return { kind: "unavailable", reason: "run_id_mismatch" };
  }
  if (!sessionId || sessionId !== expectedSessionId) {
    return { kind: "unavailable", reason: "session_id_mismatch" };
  }
  if (ACTIVE_RUN_STATUSES.has(status)) {
    return { kind: "active", runId, sessionId, status };
  }
  if (TERMINAL_RUN_STATUSES.has(status)) {
    return {
      kind: "terminal",
      runId,
      sessionId,
      status,
      runErrorObserved: payload.run_error_observed === true,
    };
  }
  return {
    kind: "unavailable",
    runId,
    sessionId,
    status,
    reason: "run_status_unrecognized",
  };
}
