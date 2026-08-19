import tempfile
import unittest
from pathlib import Path

from smart_context import CaptureGateway, CaptureRequest, FilePacketCache, LocalFileAdapter


class PacketCacheTests(unittest.TestCase):
    def test_cache_hit_is_explicit_and_invalidates_on_file_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "note.txt"
            cache_dir = root / "cache"
            source.write_text("first", encoding="utf-8")
            gateway = CaptureGateway(
                [LocalFileAdapter()], cache=FilePacketCache(cache_dir)
            )
            request = CaptureRequest(str(source))

            first = gateway.capture(request)
            second = gateway.capture(request)
            self.assertEqual(first.content, "first")
            self.assertEqual(second.content, "first")
            self.assertIn("opt-in packet cache", second.warnings[-1])

            source.write_text("second content", encoding="utf-8")
            third = gateway.capture(request)
            self.assertEqual(third.content, "second content")


if __name__ == "__main__":
    unittest.main()
