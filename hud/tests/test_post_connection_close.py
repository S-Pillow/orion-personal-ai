from __future__ import annotations

import http.client
import json
import unittest

from test_bridge import ServerFixture


class RejectedPostConnectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ServerFixture()

    def tearDown(self):
        self.fixture.close()

    def _post(self, path: str, body: dict, *, origin: bool):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.fixture.orion.server_port, timeout=5
        )
        payload = json.dumps(body).encode("utf-8")
        headers = {
            "Cookie": "orion_ui=test-cookie",
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
        }
        if origin:
            headers["Origin"] = self.fixture.origin
        try:
            conn.request("POST", path, body=payload, headers=headers)
            response = conn.getresponse()
            data = response.read()
            return response.status, response.getheader("Connection"), data
        finally:
            conn.close()

    def test_same_origin_rejection_explicitly_closes_connection(self):
        status, connection, data = self._post(
            "/api/orion/sessions", {"title": "x"}, origin=False
        )
        self.assertEqual(status, 403)
        self.assertEqual(connection, "close")
        self.assertIn(b"same_origin_required", data)

    def test_invalid_post_target_explicitly_closes_connection(self):
        status, connection, _ = self._post(
            "/api/orion/runs/%2e%2e/stop", {}, origin=True
        )
        self.assertIn(status, (400, 404))
        self.assertEqual(connection, "close")


if __name__ == "__main__":
    unittest.main(verbosity=2)
