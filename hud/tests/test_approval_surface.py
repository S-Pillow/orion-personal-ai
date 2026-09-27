"""Exercise the real bridge's long approval SSE and decision routes locally."""
import http.client
import json
import unittest

from probe_approval_surface import ApprovalSurfaceFixture, DESCRIPTION, serve_until_interrupted


class ApprovalSurfaceTests(unittest.TestCase):
    def test_ctrl_c_shutdown_always_closes_fixture(self):
        class DummyFixture:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        fixture = DummyFixture()

        def interrupted_sleep(_seconds):
            raise KeyboardInterrupt

        serve_until_interrupted(fixture, sleeper=interrupted_sleep)
        self.assertTrue(fixture.closed)

    def test_fixture_exposes_selectable_session(self):
        fixture = ApprovalSurfaceFixture()
        self.addCleanup(fixture.close)
        conn = http.client.HTTPConnection("127.0.0.1", fixture.orion.server_port, timeout=5)
        self.addCleanup(conn.close)
        conn.request("GET", "/api/orion/sessions", headers={"Cookie": f"orion_ui={fixture.cookie}"})
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read()), {"sessions": [{
            "id": "session_1", "title": "orion-hud-main",
        }]})

    def test_long_exact_event_and_simulated_once_deny_round_trip(self):
        fixture = ApprovalSurfaceFixture()
        self.addCleanup(fixture.close)
        headers = {"Cookie": f"orion_ui={fixture.cookie}",
                   "Origin": fixture.origin, "Content-Type": "application/json"}
        for choice in ("deny", "once"):
            with self.subTest(choice=choice):
                conn = http.client.HTTPConnection("127.0.0.1", fixture.orion.server_port, timeout=5)
                self.addCleanup(conn.close)
                conn.request("POST", "/api/orion/sessions/session_1/chat/stream",
                             json.dumps({"input": "probe"}), headers)
                stream = conn.getresponse()
                self.assertEqual(stream.status, 200)
                approval = None
                # run.started and approval.request, each with event/data/blank lines.
                for _ in range(6):
                    line = stream.readline().decode("utf-8")
                    if line.startswith("data:"):
                        data = json.loads(line[5:])
                        if data.get("event") == "approval.request":
                            approval = data
                self.assertIsNotNone(approval)
                self.assertGreater(len(DESCRIPTION), 1000)
                self.assertEqual(approval["description"], DESCRIPTION)
                self.assertEqual(approval["command"], "orion_vault_apply_plan")
                decision = http.client.HTTPConnection("127.0.0.1", fixture.orion.server_port, timeout=5)
                try:
                    decision.request("POST", f"/api/orion/runs/{approval['run_id']}/approval",
                                     json.dumps({"choice": choice}), headers)
                    response = decision.getresponse()
                    self.assertEqual(response.status, 200)
                    projected = json.loads(response.read())
                    self.assertEqual(
                        projected["projection"]["state"],
                        "approval_denied" if choice == "deny" else "approval_accepted",
                    )
                    self.assertFalse(projected["execution_proven"])
                finally:
                    decision.close()
                self.assertIn(b"event: run.completed", stream.read())
                conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
