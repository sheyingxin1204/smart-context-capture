import unittest
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

from smart_context import AdapterStatus
from smart_context.markitdown_adapter import MarkItDownAdapter


class MarkItDownAdapterTests(unittest.TestCase):
    def test_probe_does_not_claim_unsupported_extension(self) -> None:
        capability = MarkItDownAdapter().probe("notes.txt")
        self.assertEqual(capability.status, AdapterStatus.UNSUPPORTED)

    def test_diagnose_is_explicit_about_optional_provider(self) -> None:
        capability = MarkItDownAdapter().diagnose()
        self.assertIn(capability.status, (AdapterStatus.AVAILABLE, AdapterStatus.UNAVAILABLE))

    def test_capture_uses_optional_provider_contract(self) -> None:
        class FakeResult:
            title = "Fake PDF"
            text_content = "converted content"

        class FakeMarkItDown:
            def convert(self, _path):
                return FakeResult()

        fake_module = types.SimpleNamespace(MarkItDown=FakeMarkItDown)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            path.write_bytes(b"fake")
            with mock.patch.dict(sys.modules, {"markitdown": fake_module}):
                packet = MarkItDownAdapter().capture(str(path))
        self.assertEqual(packet.content, "converted content")
        self.assertEqual(packet.adapter, "local-rich")


if __name__ == "__main__":
    unittest.main()
