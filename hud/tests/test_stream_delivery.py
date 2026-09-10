"""Prove SSE delivery before completion using gated, real loopback sockets."""

from __future__ import annotations

import http.client
import queue
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HUD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUD_ROOT))

import orion_hud_bridge as bridge


class StreamDeliveryTests(unittest.TestCase):
    def check_delivery(self, framing: str) -> None:
        frames = (
            b'event: run.started\ndata: {"run_id":"probe_run"}\n\n',
            'event: assistant.delta\ndata: {"delta":"early caf\u00e9"}\n\n'.encode("utf-8"),
            b'event: run.completed\ndata: {"run_id":"probe_run"}\n\n',
        )
        first_flushed = threading.Event()
        allow_delta = threading.Event()
        delta_flushed = threading.Event()
        allow_finish = threading.Event()
        finished = threading.Event()
        received: queue.Queue[bytes] = queue.Queue()
        received_bytes = bytearray()
        failures: list[str] = []

        class GatedHermes(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):  # noqa: N802
                try:
                    if self.path != "/api/sessions/probe_session/chat/stream":
                        raise AssertionError("Unexpected upstream route")
                    if self.headers.get("Authorization") != "Bearer synthetic-key":
                        raise AssertionError("Missing synthetic upstream credential")
                    self.rfile.read(int(self.headers["Content-Length"]))
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    if framing == "chunked":
                        self.send_header("Transfer-Encoding", "chunked")
                    elif framing == "content-length":
                        self.send_header("Content-Length", str(sum(map(len, frames))))
                    else:
                        self.send_header("Connection", "close")
                    self.end_headers()

                    def send_frame(frame):
                        if framing == "chunked":
                            self.wfile.write(f"{len(frame):x}\r\n".encode())
                            self.wfile.write(frame + b"\r\n")
                        else:
                            self.wfile.write(frame)
                        self.wfile.flush()

                    send_frame(frames[0])
                    first_flushed.set()
                    if not allow_delta.wait(5):
                        raise AssertionError("Delta gate was not released")
                    send_frame(frames[1])
                    delta_flushed.set()
                    if not allow_finish.wait(5):
                        raise AssertionError("Completion gate was not released")
                    send_frame(frames[2])
                    if framing == "chunked":
                        self.wfile.write(b"0\r\n\r\n")
                        self.wfile.flush()
                    self.close_connection = True
                    finished.set()
                except Exception as exc:
                    failures.append(f"upstream: {type(exc).__name__}: {exc}")
                    self.close_connection = True

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), GatedHermes)
        upstream.daemon_threads = True
        self.addCleanup(upstream.server_close)
        state = bridge.BridgeState(
            target=bridge.HermesTarget("127.0.0.1", upstream.server_port),
            api_key="synthetic-key",
            ui_cookie="synthetic-cookie",
            static_root=HUD_ROOT / "static",
        )
        hud = bridge.OrionHTTPServer(("127.0.0.1", 0), state)
        self.addCleanup(hud.server_close)
        servers = (upstream, hud)
        threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
        for thread in threads:
            thread.start()
        client = http.client.HTTPConnection("127.0.0.1", hud.server_port, timeout=3)
        reader = None
        try:
            client.request(
                "POST",
                "/api/orion/sessions/probe_session/chat/stream",
                body=b'{"input":"synthetic stream probe"}',
                headers={
                    "Content-Type": "application/json",
                    "Cookie": "orion_ui=synthetic-cookie",
                    "Origin": f"http://127.0.0.1:{hud.server_port}",
                },
            )
            response = client.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn("text/event-stream", response.getheader("Content-Type"))

            def consume():
                pending = b""
                try:
                    while True:
                        chunk = response.read1(4096)
                        if not chunk:
                            break
                        received_bytes.extend(chunk)
                        pending += chunk
                        while b"\n\n" in pending:
                            frame, pending = pending.split(b"\n\n", 1)
                            received.put(frame + b"\n\n")
                    if pending:
                        failures.append("Incomplete final SSE frame")
                except Exception as exc:
                    failures.append(f"client: {type(exc).__name__}: {exc}")

            reader = threading.Thread(target=consume, daemon=True)
            reader.start()
            self.assertTrue(first_flushed.wait(2), "Upstream did not flush run.started")
            try:
                first = received.get(timeout=1.5)
            except queue.Empty:
                self.fail("run.started was buffered while upstream awaited the delta gate")
            self.assertEqual(first, frames[0])
            self.assertFalse(finished.is_set())

            allow_delta.set()
            self.assertTrue(delta_flushed.wait(2), "Upstream did not flush assistant.delta")
            try:
                delta = received.get(timeout=1.5)
            except queue.Empty:
                self.fail("assistant.delta was buffered while upstream awaited completion")
            self.assertEqual(delta, frames[1])
            self.assertFalse(finished.is_set())

            allow_finish.set()
            self.assertEqual(received.get(timeout=2), frames[2])
            reader.join(timeout=3)
            self.assertFalse(reader.is_alive(), "Client did not observe stream EOF")
            self.assertEqual(bytes(received_bytes), b"".join(frames))
            self.assertTrue(received.empty(), "Duplicate or unexpected SSE frames")
            self.assertEqual(failures, [])
        finally:
            allow_delta.set()
            allow_finish.set()
            if reader is not None:
                reader.join(timeout=3)
            client.close()
            for server in servers:
                server.shutdown()
            for thread in threads:
                thread.join(timeout=2)

    def test_chunked_events_arrive_before_completion(self):
        self.check_delivery("chunked")

    def test_close_delimited_events_arrive_before_completion(self):
        self.check_delivery("close-delimited")

    def test_content_length_events_arrive_before_completion(self):
        self.check_delivery("content-length")


if __name__ == "__main__":
    unittest.main(verbosity=2)
