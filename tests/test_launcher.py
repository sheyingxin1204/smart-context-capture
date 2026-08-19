from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "skills" / "smart-context-capture" / "scripts" / "run_capture.py"
FIXTURE = ROOT / "submission" / "fixtures" / "notes.md"


class StandaloneLauncherTests(unittest.TestCase):
    def test_works_without_site_packages(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                "-B",
                str(LAUNCHER),
                str(FIXTURE),
                "--source",
                "local_file",
            ],
            cwd=Path.home(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["source_type"], "local_file")
        self.assertEqual(packet["access_mode"], "local_read")


if __name__ == "__main__":
    unittest.main()
