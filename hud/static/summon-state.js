"use strict";

const SUMMON_KINDS = new Set([
  "text",
  "evidence",
  "link",
]);

const MAX_TITLE_CHARS = 160;
const MAX_SOURCE_CHARS = 500;
const MAX_CONTENT_CHARS = 12000;
const MAX_LINK_CHARS = 2048;

function boundedText(value, maximum, { required = false } = {}) {
  const text = String(value ?? "").trim();

  if (required && !text) {
    throw new Error("summon_required_text_missing");
  }

  if (text.length > maximum) {
    throw new Error("summon_text_too_large");
  }

  return text;
}

function normalizeLink(value) {
  const raw = boundedText(value, MAX_LINK_CHARS, { required: true });
  let url;

  try {
    url = new URL(raw);
  } catch {
    throw new Error("summon_link_invalid");
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("summon_link_scheme_rejected");
  }

  return url.href;
}

export function normalizeSummonPayload(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("summon_payload_object_required");
  }

  const kind = String(value.kind || "").trim().toLowerCase();

  if (!SUMMON_KINDS.has(kind)) {
    throw new Error("summon_kind_rejected");
  }

  const normalized = {
    kind,
    title: boundedText(value.title, MAX_TITLE_CHARS, { required: true }),
    source: boundedText(value.source, MAX_SOURCE_CHARS),
    content: boundedText(value.content, MAX_CONTENT_CHARS),
    href: "",
  };

  if (kind === "link") {
    normalized.href = normalizeLink(value.href);
  } else if (value.href) {
    throw new Error("summon_link_not_allowed_for_kind");
  }

  if ((kind === "text" || kind === "evidence") && !normalized.content) {
    throw new Error("summon_content_required");
  }

  return normalized;
}

export function installSummonController(
  {
    panel = null,
    titleNode = null,
    kindNode = null,
    sourceNode = null,
    bodyNode = null,
    linkNode = null,
    dismissButton = null,
    workspaceController = null,
    coreStage = null,
  } = {},
) {
  let active = false;

  function setPresentationFocus(enabled) {
    active = Boolean(enabled);

    if (workspaceController?.setSummonFocus) {
      workspaceController.setSummonFocus(active);
    }

    if (coreStage) {
      coreStage.dataset.presentationFocus =
        active ? "summon" : "normal";
    }
  }

  function clearNodes() {
    if (titleNode) titleNode.textContent = "";
    if (kindNode) kindNode.textContent = "";
    if (sourceNode) sourceNode.textContent = "";
    if (bodyNode) bodyNode.textContent = "";

    if (linkNode) {
      linkNode.textContent = "";
      linkNode.removeAttribute("href");
      linkNode.hidden = true;
    }
  }

  function dismiss() {
    setPresentationFocus(false);
    clearNodes();

    if (panel) {
      panel.hidden = true;
      delete panel.dataset.summonKind;
    }

    return false;
  }

  function show(value) {
    const payload = normalizeSummonPayload(value);

    clearNodes();

    if (titleNode) titleNode.textContent = payload.title;
    if (kindNode) kindNode.textContent = payload.kind.toUpperCase();
    if (sourceNode) {
      sourceNode.textContent = payload.source || "UNSPECIFIED";
    }
    if (bodyNode) bodyNode.textContent = payload.content;

    if (linkNode && payload.kind === "link") {
      linkNode.href = payload.href;
      linkNode.textContent = payload.href;
      linkNode.hidden = false;
    }

    if (panel) {
      panel.dataset.summonKind = payload.kind;
      panel.hidden = false;
      panel.focus?.();
    }

    setPresentationFocus(true);
    return payload;
  }

  const dismissHandler = () => dismiss();
  dismissButton?.addEventListener("click", dismissHandler);

  dismiss();

  return {
    show,
    dismiss,

    isActive() {
      return active;
    },

    destroy() {
      dismissButton?.removeEventListener("click", dismissHandler);
      dismiss();
    },
  };
}
