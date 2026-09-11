"use strict";

import { installCorePresence } from "./core-state.js";
import { installWorkspaceController } from "./workspace-state.js";
import {
  ACCEPTED_BASELINE,
  classifyAuthority,
  createProvenanceState,
  displayProvenanceValue,
  observeCompletionRuntime,
} from "./provenance-state.js";

const $ = (id) => document.getElementById(id);

const ui = {
  bridgeStatus: $("bridgeStatus"),
  hermesStatus: $("hermesStatus"),
  originStatus: $("originStatus"),
  authorityStatus: $("authorityStatus"),
  sourceStatus: $("sourceStatus"),
  memoryUseStatus: $("memoryUseStatus"),
  bridgeValue: $("bridgeValue"),
  hermesValue: $("hermesValue"),
  credentialValue: $("credentialValue"),
  clock: $("clock"),
  sessionSelect: $("sessionSelect"),
  newSession: $("newSession"),
  sessionMeta: $("sessionMeta"),
  lifecycleValue: $("lifecycleValue"),
  coreStage: $("coreStage"),
  coreState: $("coreState"),
  coreDetail: $("coreDetail"),
  workspaceShell: $("workspaceShell"),
  workspaceContext: $("workspaceContext"),
  workspaceOrigin: $("workspaceOrigin"),
  workspaceProvider: $("workspaceProvider"),
  workspaceModel: $("workspaceModel"),
  workspaceProvenanceEvidence: $("workspaceProvenanceEvidence"),
  workspaceSource: $("workspaceSource"),
  workspaceMemoryUse: $("workspaceMemoryUse"),
  workspaceAuthority: $("workspaceAuthority"),
  workspaceBaseline: $("workspaceBaseline"),
  workspaceBridge: $("workspaceBridge"),
  workspaceHermes: $("workspaceHermes"),
  workspaceReadiness: $("workspaceReadiness"),
  workspaceCredential: $("workspaceCredential"),
  workspaceLifecycle: $("workspaceLifecycle"),
  workspaceSession: $("workspaceSession"),
  workspaceCoreState: $("workspaceCoreState"),
  workspaceCapSessions: $("workspaceCapSessions"),
  workspaceCapStop: $("workspaceCapStop"),
  workspaceCapApproval: $("workspaceCapApproval"),
  workspaceCapStream: $("workspaceCapStream"),
  workspaceSkills: $("workspaceSkills"),
  workspaceJobs: $("workspaceJobs"),
  transcript: $("transcript"),
  composer: $("composer"),
  messageInput: $("messageInput"),
  sendButton: $("sendButton"),
  stopButton: $("stopButton"),
  activity: $("activity"),
  approvalPanel: $("approvalPanel"),
  approvalDetail: $("approvalDetail"),
  approvalActions: $("approvalActions"),
  capSessions: $("capSessions"),
  capStop: $("capStop"),
  capApproval: $("capApproval"),
  capStream: $("capStream"),
  skillCount: $("skillCount"),
  jobCount: $("jobCount"),
  footerSession: $("footerSession"),
};

const state = {
  sessionId: localStorage.getItem("orion.hermesSession") || "",
  activeRunId: "",
  streaming: false,
  approvalEvent: null,
  provenance: createProvenanceState(),
};

const corePresence = installCorePresence(
  ui.coreStage,
  ui.coreState,
);

const workspaceController = installWorkspaceController(
  ui.workspaceShell,
  {
    buttons: [
      ...document.querySelectorAll("[data-workspace-target]"),
    ],
    panes: [
      ...document.querySelectorAll("[data-workspace-pane]"),
    ],
    contextNode: ui.workspaceContext,
  },
);

function syncProvenancePresentation() {
  const provenance = state.provenance || createProvenanceState();
  const authority = classifyAuthority({
    streaming: state.streaming,
    approvalPending: Boolean(state.approvalEvent),
    activeRunId: state.activeRunId,
  });

  const origin = displayProvenanceValue(provenance.origin);
  const provider = displayProvenanceValue(provenance.provider);
  const model = displayProvenanceValue(provenance.model);
  const evidence = displayProvenanceValue(
    provenance.evidenceClass,
  );
  const source = displayProvenanceValue(provenance.source);
  const memoryUse = displayProvenanceValue(
    provenance.memoryUse,
  );

  ui.originStatus.textContent = `ORIGIN \u00b7 ${origin}`;
  ui.originStatus.dataset.provenanceOrigin = origin;

  ui.authorityStatus.textContent =
    `AUTHORITY \u00b7 ${authority}`;
  ui.authorityStatus.dataset.authorityState = authority;

  ui.sourceStatus.textContent = `SOURCE \u00b7 ${source}`;
  ui.memoryUseStatus.textContent =
    `MEMORY USE \u00b7 ${memoryUse}`;

  ui.workspaceOrigin.textContent = origin;
  ui.workspaceProvider.textContent = provider;
  ui.workspaceModel.textContent = model;
  ui.workspaceProvenanceEvidence.textContent = evidence;
  ui.workspaceSource.textContent = source;
  ui.workspaceMemoryUse.textContent = memoryUse;
  ui.workspaceAuthority.textContent = authority;
  ui.workspaceBaseline.textContent =
    `${ACCEPTED_BASELINE.model} / ` +
    `${ACCEPTED_BASELINE.provider} / ` +
    `${ACCEPTED_BASELINE.origin}`;
}
function textOrDash(node) {
  const value = String(node?.textContent || "").trim();
  return value || "\u2014";
}

function syncSystemWorkspace() {
  ui.workspaceBridge.textContent = textOrDash(ui.bridgeValue);
  ui.workspaceHermes.textContent = textOrDash(ui.hermesValue);
  ui.workspaceCredential.textContent = textOrDash(
    ui.credentialValue,
  );
  ui.workspaceLifecycle.textContent = textOrDash(
    ui.lifecycleValue,
  );

  ui.workspaceSession.textContent = state.sessionId
    ? state.sessionId
    : "none";

  ui.workspaceCoreState.textContent = textOrDash(ui.coreState);
  ui.workspaceCapSessions.textContent = textOrDash(
    ui.capSessions,
  );
  ui.workspaceCapStop.textContent = textOrDash(ui.capStop);
  ui.workspaceCapApproval.textContent = textOrDash(
    ui.capApproval,
  );
  ui.workspaceCapStream.textContent = textOrDash(ui.capStream);
  ui.workspaceSkills.textContent = textOrDash(ui.skillCount);
  ui.workspaceJobs.textContent = textOrDash(ui.jobCount);
}

function setCore(name, detail = "") {
  ui.coreState.textContent = name;
  ui.workspaceCoreState.textContent = name;
  if (detail) ui.coreDetail.textContent = detail;
  corePresence.update(name);
}

function setHermesOnline(online, degraded = false) {
  const isDegraded = online && degraded;

  ui.hermesStatus.classList.toggle("offline", !online);
  ui.hermesStatus.classList.toggle("degraded", isDegraded);

  let label = "HERMES OFFLINE";
  let value = "offline";

  if (online && isDegraded) {
    label = "HERMES DEGRADED";
    value = "degraded";
  } else if (online) {
    label = "HERMES ONLINE";
    value = "online";
  }

  ui.hermesStatus.innerHTML = "<i></i> " + label;
  ui.hermesValue.textContent = value;
  syncSystemWorkspace();
}

function updateRunControls() {
  ui.stopButton.disabled = !state.activeRunId;
  ui.sendButton.disabled = state.streaming;
  ui.newSession.disabled = state.streaming;
  ui.sessionSelect.disabled = state.streaming;
  syncProvenancePresentation();
}

function formatClock() {
  ui.clock.textContent = new Date().toLocaleTimeString([], {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { raw: text.slice(0, 600) };
    }
  }
  if (!response.ok) {
    const error = new Error(payload?.message || payload?.error || `HTTP ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function arrayFrom(payload, keys) {
  if (Array.isArray(payload)) return payload;
  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key];
  }
  return [];
}

function extractId(payload) {
  return String(payload?.session?.id || payload?.id || payload?.session_id || "");
}

function messageText(message) {
  const content = message?.content;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part;
        return part?.text || part?.content || "";
      })
      .filter(Boolean)
      .join("\n");
  }
  return String(message?.text || "");
}

function clearTranscript() {
  ui.transcript.replaceChildren();
}

function showTranscriptEmpty(text) {
  clearTranscript();
  const wrap = document.createElement("div");
  wrap.className = "empty-state";
  const strong = document.createElement("strong");
  strong.textContent = "ORION HUD LINK READY";
  const span = document.createElement("span");
  span.textContent = text;
  wrap.append(strong, span);
  ui.transcript.append(wrap);
}

function appendMessage(role, text = "") {
  const article = document.createElement("article");
  article.className = `message ${role === "user" ? "user" : "assistant"}`;
  const label = document.createElement("span");
  label.className = "message-role";
  label.textContent = role === "user" ? "YOU" : "ORION";
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = text;
  article.append(label, body);
  ui.transcript.append(article);
  ui.transcript.scrollTop = ui.transcript.scrollHeight;
  return body;
}

function renderMessages(payload) {
  const messages = arrayFrom(payload, ["messages", "items", "data"]);
  const visible = messages
    .filter((m) => m && (m.role === "user" || m.role === "assistant"))
    .map((m) => ({ role: m.role, text: messageText(m) }))
    .filter((m) => m.text.trim().length > 0);

  if (!visible.length) {
    showTranscriptEmpty("Session is ready. Send the first message.");
    return;
  }

  clearTranscript();
  for (const message of visible) appendMessage(message.role, message.text);
}

function sessionTitle(item) {
  return String(item?.title || item?.name || item?.id || "Hermes session");
}

async function refreshSessions({ loadCurrent = true } = {}) {
  try {
    const payload = await api("/api/orion/sessions");
    const sessions = arrayFrom(payload, ["sessions", "items", "data"]);
    const previous = state.sessionId;
    ui.sessionSelect.replaceChildren();
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "No session selected";
    ui.sessionSelect.append(none);

    for (const item of sessions) {
      const id = String(item?.id || item?.session_id || "");
      if (!id) continue;
      const option = document.createElement("option");
      option.value = id;
      option.textContent = sessionTitle(item);
      ui.sessionSelect.append(option);
    }

    if (previous && [...ui.sessionSelect.options].some((o) => o.value === previous)) {
      ui.sessionSelect.value = previous;
    } else if (previous) {
      state.sessionId = "";
      state.provenance = createProvenanceState();
      syncProvenancePresentation();
      localStorage.removeItem("orion.hermesSession");
    }

    syncSessionLabels();
    if (loadCurrent && state.sessionId) await loadMessages();
  } catch (error) {
    ui.sessionMeta.textContent = `Session list unavailable: ${error.message}`;
  }
}

function syncSessionLabels() {
  ui.footerSession.textContent = state.sessionId ? `SESSION ${state.sessionId}` : "NO SESSION";
  ui.sessionMeta.textContent = state.sessionId
    ? `Hermes SessionDB // ${state.sessionId}`
    : "Hermes SessionDB is authoritative.";
  syncSystemWorkspace();
}

async function loadMessages() {
  if (!state.sessionId) {
    showTranscriptEmpty("Select or create a Hermes session to begin.");
    return;
  }
  try {
    const payload = await api(`/api/orion/sessions/${encodeURIComponent(state.sessionId)}/messages`);
    renderMessages(payload);
  } catch (error) {
    showTranscriptEmpty(`Session history unavailable: ${error.message}`);
  }
}

async function createSession() {
  try {
    setCore("LINKING", "Creating persisted Hermes session...");
    const payload = await api("/api/orion/sessions", {
      method: "POST",
      body: JSON.stringify({ title: "orion-hud-main" }),
    });
    const id = extractId(payload);
    if (!id) throw new Error("Hermes created a session without an id");
    state.sessionId = id;
    state.provenance = createProvenanceState();
    syncProvenancePresentation();
    localStorage.setItem("orion.hermesSession", id);
    await refreshSessions({ loadCurrent: true });
    ui.sessionSelect.value = id;
    syncSessionLabels();
    setCore("READY", "Persistent Hermes session linked");
  } catch (error) {
    setCore("ERROR", `Session creation failed: ${error.message}`);
  }
}

function clearActivity() {
  ui.activity.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "muted-line";
  empty.textContent = "No active tool use.";
  ui.activity.append(empty);
}

function addActivity(name, preview, event = "running") {
  if (ui.activity.querySelector(".muted-line")) ui.activity.replaceChildren();
  const item = document.createElement("div");
  item.className = "activity-item";
  item.dataset.tool = name || "tool";
  const nameEl = document.createElement("div");
  nameEl.className = "activity-name";
  nameEl.textContent = name || "tool";
  const previewEl = document.createElement("div");
  previewEl.className = "activity-preview";
  previewEl.textContent = String(preview || "").slice(0, 240);
  const statusEl = document.createElement("div");
  statusEl.className = "activity-state";
  statusEl.textContent = event.toUpperCase();
  item.append(nameEl, previewEl, statusEl);
  ui.activity.prepend(item);
  while (ui.activity.children.length > 10) ui.activity.lastElementChild?.remove();
}

function finishActivity(name, failed = false) {
  const items = [...ui.activity.querySelectorAll(".activity-item")];
  const item = items.find((node) => node.dataset.tool === (name || "tool"));
  if (!item) return;
  const status = item.querySelector(".activity-state");
  if (status) status.textContent = failed ? "FAILED" : "COMPLETED";
  item.classList.toggle("failed", failed);
}

function hideApproval() {
  state.approvalEvent = null;
  syncProvenancePresentation();
  workspaceController.setApprovalFocus(false);
  ui.approvalPanel.classList.add("hidden");
  ui.approvalDetail.textContent = "";
  ui.approvalActions.replaceChildren();
}

function showApproval(data) {
  state.approvalEvent = data;
  syncProvenancePresentation();
  workspaceController.setApprovalFocus(true);
  ui.approvalPanel.classList.remove("hidden");
  const summary = data.command || data.description || data.reason || data.tool_name || "Hermes requires an operator decision.";
  ui.approvalDetail.textContent = String(summary).slice(0, 1000);
  ui.approvalActions.replaceChildren();

  const canonical = ["once", "session", "always", "deny"];
  const advertised = Array.isArray(data.choices) ? data.choices : canonical;
  const choices = canonical.filter((choice) => advertised.includes(choice));

  const labels = {
    once: "ALLOW ONCE",
    session: "ALLOW SESSION",
    always: "ALWAYS ALLOW",
    deny: "DENY",
  };

  for (const choice of choices) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = labels[choice];
    if (choice === "deny") button.classList.add("deny");
    button.addEventListener("click", () => decideApproval(choice));
    ui.approvalActions.append(button);
  }
}

async function decideApproval(choice) {
  const event = state.approvalEvent;
  const runId = event?.run_id || state.activeRunId;
  if (!runId) {
    setCore("ERROR", "Approval has no active Hermes run");
    return;
  }
  for (const button of ui.approvalActions.querySelectorAll("button")) button.disabled = true;
  try {
    await api(`/api/orion/runs/${encodeURIComponent(runId)}/approval`, {
      method: "POST",
      body: JSON.stringify({ choice }),
    });
    hideApproval();
    setCore("THINKING", `Approval recorded: ${choice}`);
  } catch (error) {
    setCore("ERROR", `Approval reconciliation: ${error.message}`);
    for (const button of ui.approvalActions.querySelectorAll("button")) button.disabled = false;
  }
}

function capabilityFlag(payload, names) {
  const features = payload?.features || {};
  const endpoints = payload?.endpoints || {};
  for (const name of names) {
    if (features[name] === true || endpoints[name]) return true;
  }
  return false;
}

function renderCapabilities(payload) {
  ui.capSessions.textContent = capabilityFlag(payload, ["sessions", "session_list", "session_chat", "session_chat_stream"]) ? "YES" : "—";
  ui.capStop.textContent = capabilityFlag(payload, ["run_stop"]) ? "YES" : "—";
  ui.capApproval.textContent = capabilityFlag(payload, ["run_approval"]) ? "YES" : "—";
  ui.capStream.textContent = capabilityFlag(payload, ["run_events_sse", "session_chat_stream"]) ? "YES" : "—";
  syncSystemWorkspace();
}

async function refreshDiscovery() {
  const results = await Promise.allSettled([
    api("/api/orion/capabilities"),
    api("/api/orion/skills"),
    api("/api/orion/jobs"),
  ]);

  if (results[0].status === "fulfilled") renderCapabilities(results[0].value);
  if (results[1].status === "fulfilled") {
    ui.skillCount.textContent = String(arrayFrom(results[1].value, ["skills", "items", "data"]).length);
  }
  if (results[2].status === "fulfilled") {
    ui.jobCount.textContent = String(arrayFrom(results[2].value, ["jobs", "items", "data"]).length);
  }
  syncSystemWorkspace();
}

async function refreshStatus(loadCurrentSession = false) {
  try {
    const payload = await api("/api/orion/status");
    const online = Boolean(payload?.hermes?.online);
    const detailedStatus = String(payload?.hermes?.detailed?.status || "").toLowerCase();
    const degraded = online && detailedStatus !== "ok";

    ui.workspaceReadiness.textContent =
      detailedStatus || "unavailable";

    setHermesOnline(online, degraded);
    ui.bridgeValue.textContent = payload?.bridge?.status || "online";
    ui.credentialValue.textContent = payload?.hermes?.credentials_available ? "available" : "missing";
    syncSystemWorkspace();

    if (online) {
      await Promise.all([
        refreshDiscovery(),
        refreshSessions({ loadCurrent: loadCurrentSession }),
      ]);

      if (!state.streaming && !state.approvalEvent) {
        if (degraded) {
          const readiness = detailedStatus || "unavailable";
          setCore("DEGRADED", `Hermes online // detailed readiness ${readiness}`);
        } else {
          setCore("READY", "Hermes link online // persistent session transport available");
        }
      }
    } else if (!state.streaming) {
      setCore("OFFLINE", "Manual-off preserved // HUD did not start Hermes");
    }
  } catch (error) {
    setHermesOnline(false);
    ui.hermesValue.textContent = "unavailable";
    ui.workspaceReadiness.textContent = "unavailable";
    syncSystemWorkspace();
    if (!state.streaming) setCore("ERROR", `Bridge status failed: ${error.message}`);
  }
}

function parseSSEFrame(frame) {
  let eventName = "";
  const dataLines = [];
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  const raw = dataLines.join("\n");
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  return { event: eventName || data?.event || "message", data };
}

function ensureAssistantBody(holder) {
  if (!holder.body) {
    holder.body = appendMessage("assistant", "");
  }

  return holder.body;
}

function handleStreamEvent(eventName, data, assistant) {
  const runId = String(data?.run_id || "");
  if (runId && !state.activeRunId) {
    state.activeRunId = runId;
    updateRunControls();
  }

  switch (eventName) {
    case "run.started":
      state.provenance = createProvenanceState();
      state.activeRunId = runId;
      setCore("THINKING", runId ? `Hermes run ${runId}` : "Hermes run started");
      updateRunControls();
      break;
    case "message.started":
      setCore("THINKING", "Generating response...");
      break;
    case "assistant.delta": {
      const delta = String(data?.delta || "");

      if (delta) {
        const assistantBody = ensureAssistantBody(assistant);
        assistantBody.textContent += delta;
        ui.transcript.scrollTop = ui.transcript.scrollHeight;
      }

      break;
    }
    case "tool.progress":
      setCore("THINKING", String(data?.delta || data?.preview || "Reasoning...").slice(0, 160));
      break;
    case "tool.started":
      setCore("ACTING", `Tool: ${data?.tool_name || "tool"}`);
      addActivity(String(data?.tool_name || "tool"), data?.preview, "running");
      break;
    case "tool.completed":
      finishActivity(String(data?.tool_name || "tool"), false);
      setCore("THINKING", "Tool complete // composing response");
      break;
    case "tool.failed":
      finishActivity(String(data?.tool_name || "tool"), true);
      setCore("THINKING", "Tool failed // Hermes is reconciling");
      break;
    case "approval.request":
      setCore("WAITING", "Operator approval required");
      showApproval(data || {});
      break;
    case "assistant.completed":
      state.provenance = observeCompletionRuntime(
        state.provenance,
        data?.runtime,
      );
      syncProvenancePresentation();
      if (typeof data?.content === "string" && data.content) {
        const assistantBody = ensureAssistantBody(assistant);
        assistantBody.textContent = data.content;
      }

      setCore("FINALIZING", "Reconciling Hermes session...");
      break;
    case "run.completed":
      state.provenance = observeCompletionRuntime(
        state.provenance,
        data?.runtime,
      );
      syncProvenancePresentation();
      if (!runId || runId === state.activeRunId) state.activeRunId = "";
      hideApproval();
      setCore("READY", "Turn complete");
      updateRunControls();
      break;
    case "run.cancelled":
      if (!runId || runId === state.activeRunId) state.activeRunId = "";
      hideApproval();
      setCore("READY", "Run cancelled");
      updateRunControls();
      break;
    case "run.failed":
    case "error":
      if (!runId || runId === state.activeRunId) state.activeRunId = "";
      setCore("ERROR", String(data?.message || data?.error || "Hermes run failed").slice(0, 180));
      updateRunControls();
      break;
    default:
      break;
  }
}

async function streamTurn(input) {
  const response = await fetch(`/api/orion/sessions/${encodeURIComponent(state.sessionId)}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });

  if (!response.ok || !response.body) {
    const text = await response.text();
    let message = text.slice(0, 400) || `HTTP ${response.status}`;
    try {
      const payload = JSON.parse(text);
      message = payload.message || payload.error || message;
    } catch {
      // text fallback already bounded
    }
    throw new Error(message);
  }

  const assistant = { body: null };
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    let splitAt;
    while ((splitAt = buffer.search(/\r?\n\r?\n/)) >= 0) {
      const match = buffer.match(/\r?\n\r?\n/);
      const delimiterLength = match ? match[0].length : 2;
      const frame = buffer.slice(0, splitAt);
      buffer = buffer.slice(splitAt + delimiterLength);
      const parsed = parseSSEFrame(frame);
      if (parsed) handleStreamEvent(parsed.event, parsed.data, assistant);
    }
    if (done) break;
  }

  if (buffer.trim()) {
    const parsed = parseSSEFrame(buffer);
    if (parsed) handleStreamEvent(parsed.event, parsed.data, assistant);
  }
}

async function sendMessage(event) {
  event.preventDefault();
  if (state.streaming) return;
  const input = ui.messageInput.value.trim();
  if (!input) return;
  if (!state.sessionId) {
    setCore("WAITING", "Create or select a Hermes session first");
    return;
  }

  state.streaming = true;
  state.activeRunId = "";
  hideApproval();
  updateRunControls();
  if (ui.transcript.querySelector(".empty-state")) clearTranscript();
  appendMessage("user", input);
  ui.messageInput.value = "";
  setCore("THINKING", "Submitting typed turn to Hermes...");

  try {
    await streamTurn(input);
  } catch (error) {
    setCore("ERROR", `Turn failed: ${error.message}`);
  } finally {
    state.streaming = false;
    state.activeRunId = "";
    updateRunControls();
    await loadMessages();
  }
}

async function stopRun() {
  if (!state.activeRunId) {
    setCore("READY", "No active run to stop");
    updateRunControls();
    return;
  }
  const runId = state.activeRunId;
  ui.stopButton.disabled = true;
  setCore("STOPPING", `Requesting safe stop for ${runId}`);
  try {
    await api(`/api/orion/runs/${encodeURIComponent(runId)}/stop`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  } catch (error) {
    setCore("ERROR", `Stop failed: ${error.message}`);
    updateRunControls();
  }
}

ui.newSession.addEventListener("click", createSession);
ui.composer.addEventListener("submit", sendMessage);
ui.stopButton.addEventListener("click", stopRun);
ui.sessionSelect.addEventListener("change", async () => {
  state.sessionId = ui.sessionSelect.value;
  state.provenance = createProvenanceState();
  syncProvenancePresentation();
  if (state.sessionId) localStorage.setItem("orion.hermesSession", state.sessionId);
  else localStorage.removeItem("orion.hermesSession");
  syncSessionLabels();
  await loadMessages();
});
ui.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    ui.composer.requestSubmit();
  }
});

formatClock();
setInterval(formatClock, 1000);
clearActivity();
syncSessionLabels();
updateRunControls();
refreshStatus(true);
setInterval(refreshStatus, 15000);
