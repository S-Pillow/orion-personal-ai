"use strict";

const DISPLAY_LIMIT = 160;

export const ACCEPTED_BASELINE = Object.freeze({
  model: "qwen3.5-hermes:9b",
  provider: "Ollama",
  origin: "LOCAL",
  evidenceClass: "ACCEPTED_BASELINE",
});

function cleanDisplayValue(value) {
  if (typeof value !== "string") return "";

  return value
    .replace(/[\u0000-\u001f\u007f]/g, " ")
    .trim()
    .slice(0, DISPLAY_LIMIT);
}

export function displayProvenanceValue(value) {
  return cleanDisplayValue(value) || "UNOBSERVED";
}

export function createProvenanceState() {
  return {
    origin: "UNOBSERVED",
    provider: "",
    model: "",
    routeSource: "",
    source: "",
    memoryUse: "",
    evidenceClass: "UNOBSERVED",
  };
}

export function normalizeCompletionRuntime(runtime) {
  if (
    !runtime ||
    typeof runtime !== "object" ||
    Array.isArray(runtime)
  ) {
    return {
      provider: "",
      model: "",
      routeSource: "",
      observed: false,
    };
  }

  const provider = cleanDisplayValue(runtime.provider);
  const model = cleanDisplayValue(runtime.model);
  const routeSource = cleanDisplayValue(
    runtime.route_source || runtime.routeSource,
  );

  return {
    provider,
    model,
    routeSource,
    observed: Boolean(provider || model),
  };
}

export function observeCompletionRuntime(current, runtime) {
  const base =
    current && typeof current === "object"
      ? current
      : createProvenanceState();

  const observed = normalizeCompletionRuntime(runtime);

  if (!observed.observed) {
    return { ...base };
  }

  return {
    origin: "UNOBSERVED",
    provider: observed.provider || base.provider || "",
    model: observed.model || base.model || "",
    routeSource:
      observed.routeSource || base.routeSource || "",
    source: base.source || "",
    memoryUse: base.memoryUse || "",
    evidenceClass: "OBSERVED_RUNTIME",
  };
}

export function classifyAuthority({
  streaming = false,
  approvalPending = false,
  activeRunId = "",
} = {}) {
  if (approvalPending) {
    return "ACT WITH APPROVAL";
  }

  if (streaming || cleanDisplayValue(activeRunId)) {
    return "ASSIST";
  }

  return "OBSERVE";
}
