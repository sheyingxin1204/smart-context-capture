import tempfile
import unittest
from pathlib import Path

from smart_context import (
    CaptureGatewayError,
    CaptureRequest,
    SourceType,
    build_local_gateway,
)


class CaptureGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.gateway = build_local_gateway()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_routes_and_captures_local_file(self) -> None:
        path = self.root / "notes.md"
        path.write_text("# Notes\n\nready", encoding="utf-8")

        packet = self.gateway.capture(
            CaptureRequest(str(path), source_hint=SourceType.LOCAL_FILE)
        )

        self.assertEqual(packet.adapter, "local")
        self.assertFalse(packet.fallback_used)
        self.assertIn("ready", packet.content)

    def test_explains_when_no_local_provider_can_read_format(self) -> None:
        path = self.root / "archive.pdf"
        path.write_bytes(b"%PDF-1.7")

        with self.assertRaisesRegex(CaptureGatewayError, "No available adapter"):
            self.gateway.capture(
                CaptureRequest(str(path), source_hint=SourceType.LOCAL_FILE)
            )


if __name__ == "__main__":
    unittest.main()
