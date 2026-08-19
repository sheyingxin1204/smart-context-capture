import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from smart_context import AdapterStatus
from smart_context.figma_adapter import (
    FigmaAdapterError,
    FigmaRestAdapter,
    FigmaRestPolicy,
    parse_figma_locator,
)


class _FigmaHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path.startswith("/v1/files/file123/nodes"):
            body = {
                "name": "Demo file",
                "nodes": {
                    "10:20": {
                        "document": {
                            "id": "10:20",
                            "name": "Hero",
                            "type": "FRAME",
                            "absoluteBoundingBox": {"width": 800, "height": 600},
                            "children": [
                                {
                                    "id": "10:21",
                                    "name": "Title",
                                    "type": "TEXT",
                                    "characters": "Hello Figma",
                                }
                            ],
                        }
                    }
                },
                "components": {"10:22": {"name": "Button"}},
                "styles": {"10:23": {"name": "Heading"}},
            }
        elif self.path.startswith("/v1/images/file123"):
            body = {"images": {"10:20": "https://cdn.test/hero.png"}}
        else:
            self.send_response(404)
            self.end_headers()
            return
        raw = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args) -> None:
        return


class FigmaAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _FigmaHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self) -> None:
        host, port = self.server.server_address
        self.adapter = FigmaRestAdapter(
            FigmaRestPolicy(
                token="test-token",
                api_base=f"http://{host}:{port}",
            )
        )

    def test_parses_design_url_and_node_id(self) -> None:
        file_key, node_id = parse_figma_locator(
            "https://www.figma.com/design/file123/Demo?node-id=10-20"
        )
        self.assertEqual(file_key, "file123")
        self.assertEqual(node_id, "10:20")

    def test_probe_requires_explicit_token(self) -> None:
        adapter = FigmaRestAdapter(FigmaRestPolicy(api_base="http://127.0.0.1:1"))
        capability = adapter.probe("https://www.figma.com/file/file123/Demo")
        self.assertEqual(capability.status, AdapterStatus.UNAUTHORIZED)

    def test_captures_node_tree_and_render_asset(self) -> None:
        packet = self.adapter.capture(
            "https://www.figma.com/design/file123/Demo?node-id=10-20"
        )
        self.assertEqual(packet.source_id, "file123:10:20")
        self.assertIn("Hello Figma", packet.content)
        self.assertEqual(packet.structured_data["component_names"], ["Button"])
        self.assertEqual(packet.assets[0]["format"], "png")

    def test_download_requires_explicit_confirmation(self) -> None:
        packet = self.adapter.capture(
            "https://www.figma.com/design/file123/Demo?node-id=10-20"
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FigmaAdapterError):
                self.adapter.download_assets(packet, directory)


if __name__ == "__main__":
    unittest.main()
