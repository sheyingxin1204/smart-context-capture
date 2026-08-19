import json
import tempfile
import unittest
from pathlib import Path

from smart_context import (
    AdapterStatus,
    FileTooLargeError,
    LocalFileAdapter,
    LocalFilePolicy,
    SourceType,
    UnsupportedLocalFileError,
)


class LocalFileAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.adapter = LocalFileAdapter()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_reads_text_and_records_provenance(self) -> None:
        path = self.root / "说明.txt"
        path.write_text("第一行\n第二行", encoding="utf-8")

        packet = self.adapter.capture(path)

        self.assertEqual(packet.source_type, SourceType.LOCAL_FILE)
        self.assertEqual(packet.content, "第一行\n第二行")
        self.assertEqual(packet.confidence, "high")
        self.assertEqual(packet.adapter, "local")
        self.assertEqual(packet.provenance[0]["encoding"], "utf-8")

    def test_reads_json_as_structured_data(self) -> None:
        path = self.root / "config.json"
        path.write_text(json.dumps({"enabled": True, "count": 2}), encoding="utf-8")

        packet = self.adapter.capture(path)

        self.assertEqual(packet.structured_data["format"], "json")
        self.assertEqual(packet.structured_data["value"]["count"], 2)
        self.assertIn('"enabled": true', packet.content)

    def test_reads_csv_as_markdown_and_rows(self) -> None:
        path = self.root / "people.csv"
        path.write_text("name,role\nAda,Engineer\nLin,Designer\n", encoding="utf-8")

        packet = self.adapter.capture(path)

        self.assertIn("| name | role |", packet.content)
        self.assertEqual(packet.structured_data["columns"], ["name", "role"])
        self.assertEqual(packet.structured_data["rows"][1], ["Lin", "Designer"])

    def test_strips_script_from_html(self) -> None:
        path = self.root / "page.html"
        path.write_text(
            "<html><head><title>Demo</title><script>secret()</script></head>"
            "<body><h1>Hello</h1><p>World</p></body></html>",
            encoding="utf-8",
        )

        packet = self.adapter.capture(path)

        self.assertEqual(packet.structured_data["title"], "Demo")
        self.assertEqual(packet.content, "Demo Hello World")
        self.assertNotIn("secret", packet.content)

    def test_limits_size_before_reading(self) -> None:
        path = self.root / "large.txt"
        path.write_text("1234567890", encoding="utf-8")
        adapter = LocalFileAdapter(LocalFilePolicy(max_bytes=4))

        with self.assertRaises(FileTooLargeError):
            adapter.capture(path)
        self.assertEqual(adapter.probe(path).status, AdapterStatus.UNSUPPORTED)

    def test_rejects_unregistered_binary_formats(self) -> None:
        path = self.root / "design.pdf"
        path.write_bytes(b"%PDF-1.7")

        with self.assertRaises(UnsupportedLocalFileError):
            self.adapter.capture(path)


if __name__ == "__main__":
    unittest.main()
