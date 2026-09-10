"use strict";

const KNOWN_STATES = new Set([
  "READY",
  "LINKING",
  "THINKING",
  "FINALIZING",
  "ACTING",
  "WAITING",
  "STOPPING",
  "DEGRADED",
  "OFFLINE",
  "ERROR",
]);

const GAZE_BY_STATE = Object.freeze({
  READY: "forward",
  LINKING: "center",
  THINKING: "center",
  FINALIZING: "center",
  ACTING: "right",
  WAITING: "right",
  STOPPING: "center",
  DEGRADED: "left",
  OFFLINE: "left",
  ERROR: "left",
});

const SACCADE_CLASSES = Object.freeze([
  "saccade-left",
  "saccade-right",
  "saccade-up",
  "saccade-down",
]);

export function normalizeCoreState(value) {
  const normalized = String(value || "")
    .trim()
    .toUpperCase();

  return KNOWN_STATES.has(normalized)
    ? normalized
    : "READY";
}

export function deriveCoreGaze(value) {
  const state = normalizeCoreState(value);
  return GAZE_BY_STATE[state] || "forward";
}

function clearSaccade(root) {
  root.classList.remove(...SACCADE_CLASSES);
}

export function applyCorePresentation(root, value) {
  const state = normalizeCoreState(value);
  const gaze = deriveCoreGaze(state);

  if (!root) {
    return { state, gaze };
  }

  root.dataset.coreState = state;
  root.dataset.gaze = gaze;

  if (gaze !== "forward") {
    clearSaccade(root);
  }

  return { state, gaze };
}

function randomDelay(minimum, spread) {
  return minimum + Math.floor(Math.random() * spread);
}

export function installCorePresence(root, stateNode) {
  if (!root) {
    return {
      update(value) {
        return {
          state: normalizeCoreState(value),
          gaze: deriveCoreGaze(value),
        };
      },
      destroy() {},
    };
  }

  let destroyed = false;
  let blinkTimer = 0;
  let blinkResetTimer = 0;
  let saccadeTimer = 0;
  let saccadeResetTimer = 0;

  const motionQuery =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;

  function reducedMotion() {
    return Boolean(motionQuery && motionQuery.matches);
  }

  function clearTimer(timer) {
    if (timer) {
      window.clearTimeout(timer);
    }
  }

  function clearMotionTimers() {
    clearTimer(blinkTimer);
    clearTimer(blinkResetTimer);
    clearTimer(saccadeTimer);
    clearTimer(saccadeResetTimer);

    blinkTimer = 0;
    blinkResetTimer = 0;
    saccadeTimer = 0;
    saccadeResetTimer = 0;
  }

  function clearMotionClasses() {
    root.classList.remove("is-blinking");
    clearSaccade(root);
  }

  function scheduleBlink() {
    if (destroyed || reducedMotion()) {
      return;
    }

    blinkTimer = window.setTimeout(() => {
      const state = normalizeCoreState(root.dataset.coreState);

      if (state !== "OFFLINE") {
        root.classList.add("is-blinking");

        blinkResetTimer = window.setTimeout(() => {
          root.classList.remove("is-blinking");
        }, 120);
      }

      scheduleBlink();
    }, randomDelay(2800, 3200));
  }

  function scheduleSaccade() {
    if (destroyed || reducedMotion()) {
      return;
    }

    saccadeTimer = window.setTimeout(() => {
      if (root.dataset.gaze === "forward") {
        clearSaccade(root);

        const selected =
          SACCADE_CLASSES[
            Math.floor(Math.random() * SACCADE_CLASSES.length)
          ];

        root.classList.add(selected);

        saccadeResetTimer = window.setTimeout(() => {
          clearSaccade(root);
        }, 420);
      }

      scheduleSaccade();
    }, randomDelay(1700, 2100));
  }

  function syncMotionMode() {
    clearMotionTimers();
    clearMotionClasses();

    if (reducedMotion()) {
      root.dataset.motion = "reduced";
      return;
    }

    root.dataset.motion = "full";
    scheduleBlink();
    scheduleSaccade();
  }

  function update(value) {
    const result = applyCorePresentation(root, value);

    root.dataset.motion = reducedMotion()
      ? "reduced"
      : "full";

    return result;
  }

  function onMotionPreferenceChange() {
    update(
      stateNode
        ? stateNode.textContent
        : root.dataset.coreState,
    );

    syncMotionMode();
  }

  if (
    motionQuery &&
    typeof motionQuery.addEventListener === "function"
  ) {
    motionQuery.addEventListener(
      "change",
      onMotionPreferenceChange,
    );
  }

  update(
    stateNode
      ? stateNode.textContent
      : root.dataset.coreState,
  );

  syncMotionMode();

  return {
    update,

    destroy() {
      destroyed = true;
      clearMotionTimers();
      clearMotionClasses();

      if (
        motionQuery &&
        typeof motionQuery.removeEventListener === "function"
      ) {
        motionQuery.removeEventListener(
          "change",
          onMotionPreferenceChange,
        );
      }
    },
  };
}
