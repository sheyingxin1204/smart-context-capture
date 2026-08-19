"""Run the bundled Smart Context CLI from any working directory.

The plugin may be invoked by Codex while the shell is rooted in the user's
workspace rather than the plugin directory. This launcher first discovers the
source tree shipped with the plugin, then falls back to an installed package.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _add_bundled_source() -> None:
    # scripts/run_capture.py -> smart-context-capture -> skills -> project root
    project_root = Path(__file__).resolve().parents[3]
    source_root = project_root / "src"
    package_root = source_root / "smart_context"
    if package_root.is_dir() and str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))


def main() -> int:
    _add_bundled_source()
    try:
        from smart_context.cli import main as cli_main
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Smart Context core is not bundled or installed; install the plugin package "
            "with `python -m pip install --editable .` or use the complete plugin archive."
        ) from exc
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
