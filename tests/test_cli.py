import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from smart_context.cli import main


class CliTests(unittest.TestCase):
    def test_local_capture_is_json_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.txt"
            path.write_text("hello", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main([str(path)])

        self.assertEqual(exit_code, 0)
        packet = json.loads(output.getvalue())
        self.assertEqual(packet["adapter"], "local")
        self.assertEqual(packet["content"], "hello")


if __name__ == "__main__":
    unittest.main()
