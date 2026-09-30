"use strict";

export const SUMMON_SCHEMA_VERSION = 1;
export const SUMMON_KINDS = new Set(["text", "evidence", "link"]);
export const SUMMON_LIMITS = Object.freeze({
  title: 120,
  body: 12000,
  source: 512,
  url: 2048,
});

function asString(value) {
  return typeof value === "string" ? value : "";
}

function bounded(value, maximum) {
  const text = asString(value);
  return text.length <= maximum ? text : null;
}

function normalizeHttpUrl(value) {
  const raw = bounded(value, SUMMON_LIMITS.url);
  if (raw === null || !raw) return null;
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    return null;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
  return parsed.href;
}

export function normalizeSummonPayload(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  if (raw.schema_version !== SUMMON_SCHEMA_VERSION) return null;

  const kind = asString(raw.kind);
  if (!SUMMON_KINDS.has(kind)) return null;

  const title = bounded(raw.title, SUMMON_LIMITS.title);
  if (title === null || !title.trim()) return null;

  const source = bounded(raw.source, SUMMON_LIMITS.source);
  if (source === null) return null;

  const body = bounded(raw.body, SUMMON_LIMITS.body);
  if (body === null) return null;

  const normalized = {
    schema_version: SUMMON_SCHEMA_VERSION,
    kind,
    title,
    body,
    source,
    url: "",
  };

  if (kind === "link") {
    const url = normalizeHttpUrl(raw.url);
    if (!url) return null;
    normalized.url = url;
  } else if (asString(raw.url)) {
    // Keep the first slice strict: text/evidence may not smuggle a remote
    // navigation/fetch target that the renderer could accidentally activate.
    return null;
  }

  if ((kind === "text" || kind === "evidence") && !body) return null;
  return Object.freeze(normalized);
}

function normalizeWorkspace(value) {
  const workspace = String(value || "").toLowerCase();
  return ["conversation", "system", "memory"].includes(workspace)
    ? workspace
    : "conversation";
}

export function createSummonState(initialWorkspace = "conversation") {
  let state = Object.freeze({
    open: false,
    payload: null,
    priorWorkspace: normalizeWorkspace(initialWorkspace),
    sequence: 0,
  });

  return {
    snapshot() {
      return state;
    },

    present(raw, currentWorkspace = "conversation") {
      const payload = normalizeSummonPayload(raw);
      if (!payload) {
        return { accepted: false, state };
      }

      const priorWorkspace = state.open
        ? state.priorWorkspace
        : normalizeWorkspace(currentWorkspace);

      state = Object.freeze({
        open: true,
        payload,
        priorWorkspace,
        sequence: state.sequence + 1,
      });
      return { accepted: true, state };
    },

    dismiss() {
      const restoreWorkspace = state.priorWorkspace;
      const wasOpen = state.open;
      state = Object.freeze({
        open: false,
        payload: null,
        priorWorkspace: restoreWorkspace,
        sequence: state.sequence + (wasOpen ? 1 : 0),
      });
      return { wasOpen, restoreWorkspace, state };
    },
  };
}
