"""Serve the converged HUD with isolated approval + summon visual fixtures.

The production HUD source is copied into a temporary directory. A tiny fixture-only
snippet is appended to the copied app.js so ?fixture=summon can display the
bounded summon shell. Repository/static source is never modified at runtime.
"""
from __future__ import annotations

import secrets
import shutil
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from probe_approval_surface import ApprovalFixtureHandler
from test_bridge import HUD_ROOT, bridge


FIXTURE_SNIPPET = r'''
const __fixtureParams = new URLSearchParams(window.location.search);
const __fixtureMode = __fixtureParams.get("fixture");

async function __fixtureSelectSession() {
  const deadline = Date.now() + 5000;

  while (
    Date.now() < deadline
    && ![...ui.sessionSelect.options].some(
      (option) => option.value === "session_1",
    )
  ) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }

  if (
    ![...ui.sessionSelect.options].some(
      (option) => option.value === "session_1",
    )
  ) {
    throw new Error("fixture_session_not_loaded");
  }

  ui.sessionSelect.value = "session_1";
  state.sessionId = "session_1";
  syncSessionLabels();
  await loadMessages();
}

document.documentElement.dataset.fixtureClock = "22:24";

if (__fixtureMode !== "motion" && __fixtureMode !== "core-review") {
  corePresence.destroy();
  ui.coreStage.dataset.motion = "reduced";
}

if (__fixtureMode === "motion") {
  const __fixtureAssertThinking = () => {
    setCore("THINKING", "Simulated fixture // active Core motion verification");
  };
  __fixtureAssertThinking();
  setInterval(__fixtureAssertThinking, 250);
}

if (__fixtureMode === "core-review") {
  setCore("READY", "Simulated fixture // isolated Core renderer review");
  corePresence.setGaze("forward");

  window.__orionCoreFixture = {
    neutral() {
      hideApproval();
      summonController.dismiss();
      corePresence.setGaze("forward");
      setCore("READY", "Simulated fixture // neutral Core review pose");
    },
    gaze(value) {
      return corePresence.setGaze(value);
    },
    blink() {
      return corePresence.blink();
    },
    state(value) {
      setCore(value, "Simulated fixture // manual Core state review");
    },
    attention(kind) {
      if (kind === "reply") {
        if (!state.approvalEvent) setCore("THINKING", "Simulated fixture // incoming reply");
        handleStreamEvent("assistant.delta", { delta: "Simulated reply: review the new conversation content below." }, {});
      }
      if (kind === "approval") {
        setCore("WAITING", "Simulated fixture // approval attention only");
        showApproval({ action_title: "Simulated decision needs your attention", description: "Presentation-only example. No action will execute.", choices: [] });
      }
      if (kind === "summon") {
        summonController.show({ kind: "text", title: "New material to review", content: "Simulated fixture: newly presented content receives a brief glance.", source: "fixture://core-attention" });
      }
    },
    snapshot() {
      return {
        state: ui.coreStage.dataset.coreState,
        gaze: ui.coreStage.dataset.gaze,
        blinkPhase: ui.coreStage.dataset.blinkPhase,
        motion: ui.coreStage.dataset.motion,
        attentionTarget: ui.coreStage.dataset.attentionTarget || null,
      };
    },
  };

  const controls = document.createElement("section");
  controls.id = "coreReviewControls";
  controls.setAttribute("aria-label", "Presentation-only Core review controls");
  controls.style.cssText =
    "position:fixed;left:18px;bottom:26px;z-index:80;padding:10px;"
    + "display:grid;grid-template-columns:repeat(4,auto);gap:6px;"
    + "background:rgba(3,10,14,.9);border:1px solid rgba(99,229,239,.22);"
    + "font:10px ui-monospace;color:#cfeff2;";
  controls.innerHTML =
    '<button type="button" data-core-fixture="neutral">NEUTRAL</button>'
    + '<button type="button" data-core-fixture="left">GAZE LEFT</button>'
    + '<button type="button" data-core-fixture="right">GAZE RIGHT</button>'
    + '<button type="button" data-core-fixture="blink">BLINK</button>'
    + '<button type="button" data-core-fixture="waiting">WAITING</button>'
    + '<button type="button" data-core-fixture="offline">OFFLINE</button>'
    + '<button type="button" data-core-fixture="reply">NEW REPLY</button>'
    + '<button type="button" data-core-fixture="approval">ATTENTION: APPROVAL</button>'
    + '<button type="button" data-core-fixture="summon">NEW CONTENT</button>';
  controls.addEventListener("click", (event) => {
    const action = event.target?.dataset?.coreFixture;
    if (action === "neutral") window.__orionCoreFixture.neutral();
    if (action === "left") window.__orionCoreFixture.gaze("left");
    if (action === "right") window.__orionCoreFixture.gaze("right");
    if (action === "blink") window.__orionCoreFixture.blink();
    if (action === "waiting") window.__orionCoreFixture.state("WAITING");
    if (action === "offline") window.__orionCoreFixture.state("OFFLINE");
    if (["reply", "approval", "summon"].includes(action)) window.__orionCoreFixture.attention(action);
  });
  document.body.append(controls);
}

if (__fixtureMode === "truth-matrix") {
  window.__orionTruthFixture = {
    render(stateName) {
      hideApproval();
      const projection = {
        schema_version: "orion.action-projection.v1",
        state: stateName,
        source: "fixture_truth_matrix",
        durability: "completed_record",
        action: "edit_note",
        target_relative_path: "Projects/Orion/next-phase-proposal.md",
        run_id: "run_truth_matrix",
        recovery_required: stateName === "failed",
        recovery_id: stateName === "failed" ? "f".repeat(64) : undefined,
        diff:
          stateName === "preview_ready"
            ? "--- old\n+++ new\n-old line\n+new line"
            : "",
      };
      state.actionEvidence = [projection];
      presentActionProjection(projection);
      return {
        state: ui.actionEvidencePanel.dataset.actionState,
        label: ui.actionStateBadge.textContent,
        execution: ui.actionExecution.textContent,
        recovery: ui.actionRecovery.textContent,
        coreState: ui.coreStage.dataset.coreState,
      };
    },
  };
}

if (__fixtureMode === "review") {
  (async () => {
    await __fixtureSelectSession();
    ui.transcript.scrollTop = 0;
    addActivity(
      "Reviewing project notes",
      "Reading the isolated Orion visual-convergence fixture.",
      "completed",
    );
    addActivity(
      "Synthesizing key themes",
      "Comparing the owner visual target with the current shell.",
      "completed",
    );
    addActivity(
      "Preparing proposal",
      "Drafting the next visual-convergence steps.",
      "running",
    );
  })();
}

if (__fixtureMode === "summon") {
  void __fixtureSelectSession();
}

if (__fixtureMode === "offline") {
  const __fixtureAssertOffline = () => {
    setHermesOnline(false);
    setCore("OFFLINE", "Simulated fixture // no live Hermes claim");
  };
  setTimeout(__fixtureAssertOffline, 300);
  setInterval(__fixtureAssertOffline, 500);
}

if (__fixtureMode === "summon" || __fixtureMode === "summon-approval") {
  summonController.show({
    kind: "evidence",
    title: "Summoned evidence fixture",
    source: "fixture://ui-convergence",
    content:
      "This is presentation-only fixture content.\n\n"
      + "Conversation remains selected underneath.\n"
      + "Approval focus must still outrank summon focus.\n"
      + "<b>literal markup</b> must remain literal text.",
  });
}

if (__fixtureMode === "approval" || __fixtureMode === "summon-approval") {
  (async () => {
    await __fixtureSelectSession();
    ui.transcript.scrollTop = 0;
    addActivity(
      "Reviewing project notes",
      "Reading the isolated Orion visual-convergence fixture.",
      "completed",
    );
    addActivity(
      "Synthesizing key themes",
      "Comparing the supplied reference with the current shell.",
      "completed",
    );
    addActivity(
      "Preparing proposal",
      "Drafting the next Orion interface proposal for operator review.",
      "running",
    );
    await new Promise((resolve) => setTimeout(resolve, 75));
    ui.messageInput.value =
      "Prepare the next Orion interface proposal from the reviewed notes. "
      + "Show me the exact change before anything is written.";
    ui.composer.requestSubmit();
    setTimeout(() => {
      ui.transcript.scrollTop = 0;
    }, 200);
  })();
}
'''


class UIConvergenceFixture:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = None
        self.cookie = secrets.token_urlsafe(32)
        self._tmp = tempfile.TemporaryDirectory(prefix="orion-ui-convergence-")
        self.static_root = Path(self._tmp.name) / "static"
        shutil.copytree(HUD_ROOT / "static", self.static_root)

        app_path = self.static_root / "app.js"
        app_text = app_path.read_text(encoding="utf-8")
        app_text += "\n" + FIXTURE_SNIPPET + "\n"
        app_path.write_text(app_text, encoding="utf-8")

        self.hermes = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            ApprovalFixtureHandler,
        )
        self.hermes.fixture = self

        state = bridge.BridgeState(
            target=bridge.HermesTarget(
                "127.0.0.1",
                self.hermes.server_port,
            ),
            api_key="disposable-fixture-only",
            ui_cookie=self.cookie,
            static_root=self.static_root,
        )
        self.orion = bridge.OrionHTTPServer(("127.0.0.1", 0), state)
        self.threads = [
            threading.Thread(target=s.serve_forever, daemon=True)
            for s in (self.hermes, self.orion)
        ]
        for thread in self.threads:
            thread.start()

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.orion.server_port}"

    @property
    def review_url(self):
        return self.origin + "/?fixture=review"

    @property
    def summon_url(self):
        return self.origin + "/?fixture=summon"

    @property
    def approval_url(self):
        return self.origin + "/?fixture=approval"

    @property
    def summon_approval_url(self):
        return self.origin + "/?fixture=summon-approval"

    @property
    def offline_url(self):
        return self.origin + "/?fixture=offline"

    @property
    def motion_url(self):
        return self.origin + "/?fixture=motion"

    @property
    def core_review_url(self):
        return self.origin + "/?fixture=core-review"

    @property
    def truth_matrix_url(self):
        return self.origin + "/?fixture=truth-matrix"

    def close(self):
        with self.lock:
            if self.pending:
                self.pending["done"].set()

        for server in (self.orion, self.hermes):
            server.shutdown()
            server.server_close()

        for thread in self.threads:
            thread.join(timeout=2)

        self._tmp.cleanup()


if __name__ == "__main__":
    import time

    fixture = UIConvergenceFixture()
    try:
        print(f"BASE HUD: {fixture.origin}", flush=True)
        print(f"REVIEW HUD: {fixture.review_url}", flush=True)
        print(f"SUMMON HUD: {fixture.summon_url}", flush=True)
        print(f"APPROVAL HUD: {fixture.approval_url}", flush=True)
        print(f"SUMMON + APPROVAL HUD: {fixture.summon_approval_url}", flush=True)
        print(f"OFFLINE HUD: {fixture.offline_url}", flush=True)
        print(f"MOTION HUD: {fixture.motion_url}", flush=True)
        print(f"CORE REVIEW HUD: {fixture.core_review_url}", flush=True)
        print(f"TRUTH MATRIX HUD: {fixture.truth_matrix_url}", flush=True)
        print(
            "Base: select orion-hud-main and send 'probe' for simulated approval.",
            flush=True,
        )
        print(
            "Summon URL: presentation-only temporary copy; no repository mutation.",
            flush=True,
        )
        print("Ctrl+C closes both fixture servers.", flush=True)
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        fixture.close()
