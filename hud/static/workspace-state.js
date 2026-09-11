"use strict";

const WORKSPACES = new Set([
  "conversation",
  "system",
  "memory",
]);

export function normalizeWorkspace(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();

  return WORKSPACES.has(normalized)
    ? normalized
    : "conversation";
}

export function applyWorkspaceState(
  root,
  value,
  {
    buttons = [],
    panes = [],
    contextNode = null,
  } = {},
) {
  const workspace = normalizeWorkspace(value);

  if (!root) {
    return workspace;
  }

  root.dataset.workspace = workspace;

  for (const button of buttons) {
    const selected =
      button.dataset.workspaceTarget === workspace;

    button.setAttribute(
      "aria-pressed",
      selected ? "true" : "false",
    );
  }

  for (const pane of panes) {
    pane.hidden =
      pane.dataset.workspacePane !== workspace;
  }

  if (contextNode) {
    contextNode.textContent = workspace.toUpperCase();
  }

  return workspace;
}

export function applyWorkspaceFocus(root, focus) {
  const normalized =
    focus === "approval"
      ? "approval"
      : "normal";

  if (root) {
    root.dataset.workspaceFocus = normalized;
  }

  return normalized;
}

export function installWorkspaceController(
  root,
  {
    buttons = [],
    panes = [],
    contextNode = null,
  } = {},
) {
  const listeners = [];

  function select(value) {
    return applyWorkspaceState(
      root,
      value,
      {
        buttons,
        panes,
        contextNode,
      },
    );
  }

  function setApprovalFocus(active) {
    return applyWorkspaceFocus(
      root,
      active ? "approval" : "normal",
    );
  }

  for (const button of buttons) {
    const handler = () => {
      select(button.dataset.workspaceTarget);
    };

    button.addEventListener("click", handler);
    listeners.push([button, handler]);
  }

  select(
    root
      ? root.dataset.workspace
      : "conversation",
  );

  setApprovalFocus(false);

  return {
    select,
    setApprovalFocus,

    current() {
      return normalizeWorkspace(
        root
          ? root.dataset.workspace
          : "conversation",
      );
    },

    destroy() {
      for (const [button, handler] of listeners) {
        button.removeEventListener("click", handler);
      }
    },
  };
}
