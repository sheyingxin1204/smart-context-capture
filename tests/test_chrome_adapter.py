import json
import socketserver
import struct
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from smart_context import AdapterStatus
from smart_context.chrome_adapter import (
    ChromeCdpAdapter,
    ChromeCdpPolicy,
    ChromeTargetNotFoundError,
    _evaluate_page,
)


TARGETS = [
    {
        "id": "tab-1",
        "type": "page",
        "title": "Project dashboard",
        "url": "https://example.test/dashboard",
        "webSocketDebuggerUrl": "ws://127.0.0.1:1/devtools/page/tab-1",
    },
    {
        "id": "worker-1",
        "type": "service_worker",
        "title": "ignored",
        "url": "https://example.test/worker.js",
    },
]


class _TargetHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != "/json/list":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(TARGETS).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


class _CdpWebSocketHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        request = bytearray()
        while b"\r\n\r\n" not in request:
            request.extend(self.request.recv(1))
        headers = {
            line.split(":", 1)[0].strip().lower(): line.split(":", 1)[1].strip()
            for line in request.decode("latin-1").splitlines()[1:]
            if ":" in line
        }
        import base64
        import hashlib

        accept = base64.b64encode(
            hashlib.sha1(
                (headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
            ).digest()
        ).decode()
        self.request.sendall(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode()
        )
        first, second = self.request.recv(2)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self.request.recv(2))[0]
        mask_key = self.request.recv(4)
        body = bytearray(self.request.recv(length))
        for index in range(length):
            body[index] ^= mask_key[index % 4]
        command = json.loads(body.decode("utf-8"))
        response = {
            "id": command["id"],
            "result": {
                "result": {
                    "value": {
                        "title": "Fake tab",
                        "url": "https://example.test/fake",
                        "text": "Hello from CDP",
                        "links": [],
                    }
                }
            },
        }
        payload = json.dumps(response).encode("utf-8")
        if len(payload) < 126:
            frame = bytes([0x81, len(payload)]) + payload
        else:
            frame = bytes([0x81, 126]) + struct.pack("!H", len(payload)) + payload
        self.request.sendall(frame)


class ChromeAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.websocket_server = socketserver.ThreadingTCPServer(
            ("127.0.0.1", 0), _CdpWebSocketHandler
        )
        cls.websocket_thread = threading.Thread(
            target=cls.websocket_server.serve_forever, daemon=True
        )
        cls.websocket_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.websocket_server.shutdown()
        cls.websocket_server.server_close()
        cls.websocket_thread.join(timeout=2)

    def setUp(self) -> None:
        host, port = self.server.server_address
        self.adapter = ChromeCdpAdapter(
            ChromeCdpPolicy(endpoint=f"http://{host}:{port}")
        )

    def test_probe_and_select_existing_target(self) -> None:
        capability = self.adapter.probe("dashboard")

        self.assertEqual(capability.status, AdapterStatus.AVAILABLE)
        self.assertEqual(capability.metadata["target_id"], "tab-1")

    def test_select_target_supports_id_and_current_alias(self) -> None:
        target = self.adapter.select_target(TARGETS, "tab-1")
        self.assertEqual(target["title"], "Project dashboard")
        self.assertEqual(
            self.adapter.select_target(TARGETS, "chrome:current")["id"], "tab-1"
        )

    def test_current_is_rejected_when_multiple_pages_are_ambiguous(self) -> None:
        second_page = {
            "id": "tab-2",
            "type": "page",
            "title": "Settings",
            "url": "https://example.test/settings",
        }
        with self.assertRaisesRegex(ChromeTargetNotFoundError, "foreground tab"):
            self.adapter.select_target(TARGETS + [second_page], "current")

    def test_cdp_websocket_evaluates_page(self) -> None:
        _, port = self.websocket_server.server_address
        payload = _evaluate_page(
            f"ws://127.0.0.1:{port}/devtools/page/tab-1",
            ChromeCdpPolicy(timeout_seconds=2),
        )
        self.assertEqual(payload["text"], "Hello from CDP")


if __name__ == "__main__":
    unittest.main()
