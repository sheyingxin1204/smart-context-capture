"""Run the bundled Smart Context CLI from any working directory.

The launcher is intentionally usable in two distribution shapes:

* a complete plugin archive, where the project ``src`` tree sits beside
  ``skills/``; and
* a standalone Skill directory copied into ``.codex/skills``, where only this
  folder (and its small dependency-free vendor copy) is present.

That distinction matters because Codex can install a Skill without installing
the repository's Python package first.  We try the self-contained vendor copy
first, then the complete archive source tree, and only then an installed
package supplied by the user.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _add_bundled_source() -> None:
    script_dir = Path(__file__).resolve().parent
    # Standalone Skill installs keep this path; it contains only stdlib Python
    # and is synchronized from src/smart_context during release preparation.
    vendor_root = script_dir / "_vendor"
    # scripts/run_capture.py -> smart-context-capture -> skills -> project root
    project_root = script_dir.parents[2]
    archive_source_root = project_root / "src"
    candidates = (vendor_root, archive_source_root)
    for source_root in candidates:
        if (source_root / "smart_context").is_dir() and str(source_root) not in sys.path:
            sys.path.insert(0, str(source_root))
            break


def main() -> int:
    _add_bundled_source()
    try:
        from smart_context.cli import main as cli_main
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Smart Context core is not bundled or installed; reinstall the complete "
            "plugin/Skill bundle or install the optional package with "
            "`python -m pip install --editable .`."
        ) from exc
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
