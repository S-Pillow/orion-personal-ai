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

if (
  __fixtureMode === "review"
  || __fixtureMode === "summon"
  || __fixtureMode === "summon-approval"
) {
  void __fixtureSelectSession();
}

if (__fixtureMode === "review") {
  addActivity(
    "Reading project files",
    "Reviewing current Orion UI and memory-system notes.",
    "running",
  );
  addActivity(
    "Synthesizing insights",
    "Comparing owner visual target against the active HUD branch.",
    "running",
  );
  addActivity(
    "Preparing response",
    "Prioritizing composition, readability, and state presentation.",
    "running",
  );
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

if (__fixtureMode === "summon-approval") {
  (async () => {
    await __fixtureSelectSession();
    ui.messageInput.value = "probe";
    ui.composer.requestSubmit();
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
        marker = "void summonController;"
        if marker not in app_text:
            raise RuntimeError("summon_controller_marker_missing")
        app_text = app_text.replace(
            marker,
            marker + "\n" + FIXTURE_SNIPPET,
            1,
        )
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
    def summon_approval_url(self):
        return self.origin + "/?fixture=summon-approval"

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
        print(f"SUMMON + APPROVAL HUD: {fixture.summon_approval_url}", flush=True)
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
