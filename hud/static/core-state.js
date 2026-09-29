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

const KNOWN_GAZES = new Set([
  "forward",
  "center",
  "left",
  "right",
  "up",
  "down",
]);

const BLINK_TIMING = Object.freeze({
  closing: 80,
  closed: 30,
  opening: 140,
});

export function normalizeCoreState(value) {
  const normalized = String(value || "")
    .trim()
    .toUpperCase();

  return KNOWN_STATES.has(normalized)
    ? normalized
    : "READY";
}

export function deriveCoreGaze() {
  return "forward";
}

// Attention follows the visible surface, never an operational-state label.
export function attentionDirection(source, target) {
  const dx = target.x + target.width / 2 - source.x - source.width / 2;
  const dy = target.y + target.height / 2 - source.y - source.height / 2;
  if (Math.hypot(dx, dy) < 24) return "forward";
  return Math.abs(dx) > Math.abs(dy)
    ? (dx < 0 ? "left" : "right")
    : (dy < 0 ? "up" : "down");
}

function normalizeGaze(value) {
  const gaze = String(value || "")
    .trim()
    .toLowerCase();

  return KNOWN_GAZES.has(gaze)
    ? gaze
    : "forward";
}

export function applyCorePresentation(root, value) {
  const state = normalizeCoreState(value);
  const gaze = root
    ? normalizeGaze(root.dataset.gaze)
    : deriveCoreGaze(state);

  if (!root) {
    return { state, gaze };
  }

  root.dataset.coreState = state;

  if (!root.dataset.gaze || state === "OFFLINE") {
    root.dataset.gaze = "forward";
  }

  return {
    state,
    gaze: normalizeGaze(root.dataset.gaze),
  };
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
          gaze: "forward",
        };
      },
      setGaze() {},
      glance() {},
      lookAt() {},
      blink() {},
      destroy() {},
    };
  }

  let destroyed = false;
  let blinkTimer = 0;
  let blinkPhaseTimer = 0;
  let gazeResetTimer = 0;
  let blinkActive = false;
  let nextAttentionAt = 0;
  let attentionPriority = 0;

  const motionQuery =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;

  function reducedMotion() {
    return Boolean(motionQuery && motionQuery.matches);
  }

  function surfaceVisible() {
    return typeof document === "undefined"
      || document.visibilityState !== "hidden";
  }

  function clearTimer(timer) {
    if (timer) {
      window.clearTimeout(timer);
    }
  }

  function clearBlinkTimers() {
    clearTimer(blinkTimer);
    clearTimer(blinkPhaseTimer);
    blinkTimer = 0;
    blinkPhaseTimer = 0;
  }

  function clearGazeTimer() {
    clearTimer(gazeResetTimer);
    gazeResetTimer = 0;
    delete root.dataset.attentionTarget;
  }

  function resetBlinkPose() {
    blinkActive = false;
    root.classList.remove(
      "blink-closing",
      "blink-closed",
      "blink-opening",
    );
    root.dataset.blinkPhase = "open";
  }

  function setGaze(value, duration = 0) {
    clearGazeTimer();

    const gaze = normalizeGaze(value);
    root.dataset.gaze = gaze;

    if (
      duration > 0
      && !destroyed
      && !reducedMotion()
      && surfaceVisible()
    ) {
      gazeResetTimer = window.setTimeout(() => {
        root.dataset.gaze = "forward";
        gazeResetTimer = 0;
        delete root.dataset.attentionTarget;
      }, duration);
    }

    return gaze;
  }

  function glance(value, duration = 520) {
    if (
      destroyed
      || reducedMotion()
      || !surfaceVisible()
      || normalizeCoreState(root.dataset.coreState) === "OFFLINE"
    ) {
      return "forward";
    }

    return setGaze(value, duration);
  }

  function visibleRect(element) {
    if (!element?.getClientRects().length) return null;
    const style = window.getComputedStyle(element);
    if (style.visibility !== "visible" || Number(style.opacity) === 0) return null;
    const box = element.getBoundingClientRect();
    const x = Math.max(0, box.x), y = Math.max(0, box.y);
    const width = Math.min(window.innerWidth, box.right) - x;
    const height = Math.min(window.innerHeight, box.bottom) - y;
    return width > 0 && height > 0 ? { x, y, width, height } : null;
  }

  function lookAt(target, priority = 1) {
    if (destroyed || reducedMotion() || !surfaceVisible()
        || normalizeCoreState(root.dataset.coreState) === "OFFLINE") return false;
    const source = visibleRect(root.querySelector(".core-visual"));
    const destination = visibleRect(target);
    if (!source || !destination) return false;
    const now = performance.now();
    if (now < nextAttentionAt && priority <= attentionPriority) return false;
    const direction = attentionDirection(source, destination);
    if (direction === "forward") return false;
    glance(direction, priority > 1 ? 1800 : 1200);
    root.dataset.attentionTarget = target.id || "surface";
    attentionPriority = priority;
    nextAttentionAt = now + 2600;
    return true;
  }

  function beginBlink() {
    if (
      destroyed
      || blinkActive
      || reducedMotion()
      || !surfaceVisible()
      || normalizeCoreState(root.dataset.coreState) === "OFFLINE"
    ) {
      return false;
    }

    blinkActive = true;
    root.classList.remove("blink-closed", "blink-opening");
    root.classList.add("blink-closing");
    root.dataset.blinkPhase = "closing";

    blinkPhaseTimer = window.setTimeout(() => {
      root.classList.remove("blink-closing");
      root.classList.add("blink-closed");
      root.dataset.blinkPhase = "closed";

      blinkPhaseTimer = window.setTimeout(() => {
        root.classList.remove("blink-closed");
        root.classList.add("blink-opening");
        root.dataset.blinkPhase = "opening";

        blinkPhaseTimer = window.setTimeout(() => {
          root.classList.remove("blink-opening");
          root.dataset.blinkPhase = "open";
          blinkPhaseTimer = 0;
          blinkActive = false;
          scheduleBlink();
        }, BLINK_TIMING.opening);
      }, BLINK_TIMING.closed);
    }, BLINK_TIMING.closing);

    return true;
  }

  function scheduleBlink() {
    clearTimer(blinkTimer);
    blinkTimer = 0;

    if (
      destroyed
      || blinkActive
      || reducedMotion()
      || !surfaceVisible()
      || normalizeCoreState(root.dataset.coreState) === "OFFLINE"
    ) {
      return;
    }

    blinkTimer = window.setTimeout(() => {
      blinkTimer = 0;
      beginBlink();
    }, randomDelay(3600, 4000));
  }

  function cancelPresentationMotion() {
    clearBlinkTimers();
    clearGazeTimer();
    resetBlinkPose();
    root.dataset.gaze = "forward";
    nextAttentionAt = 0;
    attentionPriority = 0;
  }

  function syncMotionMode() {
    cancelPresentationMotion();

    if (reducedMotion()) {
      root.dataset.motion = "reduced";
      return;
    }

    if (!surfaceVisible()) {
      root.dataset.motion = "paused";
      return;
    }

    root.dataset.motion = "full";

    if (normalizeCoreState(root.dataset.coreState) !== "OFFLINE") {
      scheduleBlink();
    }
  }

  function update(value) {
    const result = applyCorePresentation(root, value);
    const state = result.state;

    if (
      state === "OFFLINE"
      || reducedMotion()
      || !surfaceVisible()
    ) {
      cancelPresentationMotion();
    } else if (!blinkActive && !blinkTimer) {
      scheduleBlink();
    }

    root.dataset.motion = reducedMotion()
      ? "reduced"
      : surfaceVisible()
        ? "full"
        : "paused";

    return {
      state,
      gaze: normalizeGaze(root.dataset.gaze),
    };
  }

  function onMotionPreferenceChange() {
    update(
      stateNode
        ? stateNode.textContent
        : root.dataset.coreState,
    );
    syncMotionMode();
  }

  function onVisibilityChange() {
    syncMotionMode();
  }

  if (
    motionQuery
    && typeof motionQuery.addEventListener === "function"
  ) {
    motionQuery.addEventListener(
      "change",
      onMotionPreferenceChange,
    );
  }

  if (
    typeof document !== "undefined"
    && typeof document.addEventListener === "function"
  ) {
    document.addEventListener(
      "visibilitychange",
      onVisibilityChange,
    );
  }

  root.dataset.blinkPhase = "open";
  root.dataset.gaze = normalizeGaze(root.dataset.gaze);

  update(
    stateNode
      ? stateNode.textContent
      : root.dataset.coreState,
  );
  syncMotionMode();

  return {
    update,
    setGaze,
    glance,
    lookAt,
    blink: beginBlink,

    destroy() {
      destroyed = true;
      cancelPresentationMotion();

      if (
        motionQuery
        && typeof motionQuery.removeEventListener === "function"
      ) {
        motionQuery.removeEventListener(
          "change",
          onMotionPreferenceChange,
        );
      }

      if (
        typeof document !== "undefined"
        && typeof document.removeEventListener === "function"
      ) {
        document.removeEventListener(
          "visibilitychange",
          onVisibilityChange,
        );
      }
    },
  };
}
