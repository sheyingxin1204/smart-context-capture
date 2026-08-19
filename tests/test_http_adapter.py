import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from smart_context import (
    CaptureGateway,
    CaptureRequest,
    ChromeCdpAdapter,
    ChromeCdpPolicy,
    PublicHttpAdapter,
    SourceType,
)


class _PublicPageHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path == "/data":
            body = b'{"ok": true, "value": 3}'
            content_type = "application/json"
        else:
            body = (
                b"<html><head><title>Public page</title><script>secret()</script></head>"
                b"<body><h1>Hello</h1><a href='/next'>Next</a></body></html>"
            )
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


class PublicHttpAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _PublicPageHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self) -> None:
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/page"

    def test_reads_public_html_without_browser_state(self) -> None:
        packet = PublicHttpAdapter().capture(self.url)

        self.assertEqual(packet.access_mode, "public_http_read")
        self.assertEqual(packet.title, "Public page")
        self.assertIn("Hello", packet.content)
        self.assertNotIn("secret", packet.content)
        self.assertFalse(packet.structured_data["uses_browser_session"])

    def test_marks_javascript_shell_without_upgrading_permission(self) -> None:
        class _ShellHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
                body = b'<html><body><div id="root"></div><p>Enable JavaScript</p></body></html>'
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), _ShellHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            packet = PublicHttpAdapter().capture(f"http://{host}:{port}/shell")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertTrue(packet.structured_data["javascript_required_suspected"])
        self.assertEqual(packet.confidence, "low")
        self.assertTrue(any("JavaScript-rendered shell" in item for item in packet.warnings))

    def test_gateway_uses_public_http_before_cdp(self) -> None:
        gateway = CaptureGateway(
            [
                ChromeCdpAdapter(ChromeCdpPolicy(endpoint="http://127.0.0.1:1")),
                PublicHttpAdapter(),
            ]
        )
        packet = gateway.capture(
            CaptureRequest(self.url, source_hint=SourceType.CHROME_TAB)
        )

        self.assertEqual(packet.adapter, "public-http")
        self.assertFalse(packet.fallback_used)

    def test_browser_session_falls_back_to_public_http(self) -> None:
        gateway = CaptureGateway(
            [
                ChromeCdpAdapter(ChromeCdpPolicy(endpoint="http://127.0.0.1:1")),
                PublicHttpAdapter(),
            ]
        )
        packet = gateway.capture(
            CaptureRequest(
                self.url,
                source_hint=SourceType.CHROME_TAB,
                prefer_browser_session=True,
            )
        )

        self.assertEqual(packet.adapter, "public-http")
        self.assertTrue(packet.fallback_used)
        self.assertIn("public HTTP read", packet.warnings[0])


if __name__ == "__main__":
    unittest.main()
