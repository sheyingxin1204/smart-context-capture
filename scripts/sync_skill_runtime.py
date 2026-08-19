"""Synchronize the dependency-free Python core into the standalone Skill.

The marketplace plugin can ship the repository ``src`` tree, but a direct
Skill installation may contain only ``skills/smart-context-capture``.  The
small vendored copy keeps the basic local/public-HTTP path usable in both
layouts without an implicit network install.  Run this script after changing
``src/smart_context`` and use ``--check`` in release/CI validation.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def paths(root: Path) -> tuple[Path, Path]:
    source = root / "src" / "smart_context"
    target = root / "skills" / "smart-context-capture" / "scripts" / "_vendor" / "smart_context"
    return source, target


def sync(source: Path, target: Path) -> list[str]:
    if not source.is_dir():
        raise SystemExit(f"missing source package: {source}")
    target.mkdir(parents=True, exist_ok=True)
    source_files = {path.name: path for path in source.glob("*.py")}
    for stale in target.glob("*.py"):
        if stale.name not in source_files:
            stale.unlink()
    changed: list[str] = []
    for name, source_path in sorted(source_files.items()):
        target_path = target / name
        if not target_path.is_file() or target_path.read_bytes() != source_path.read_bytes():
            shutil.copy2(source_path, target_path)
            changed.append(name)
    return changed


def check(source: Path, target: Path) -> list[str]:
    if not source.is_dir():
        return [f"missing source package: {source}"]
    expected = {path.name: path for path in source.glob("*.py")}
    actual = {path.name: path for path in target.glob("*.py")} if target.is_dir() else {}
    errors: list[str] = []
    for name in sorted(expected.keys() | actual.keys()):
        if name not in expected:
            errors.append(f"stale vendored file: {name}")
        elif name not in actual:
            errors.append(f"missing vendored file: {name}")
        elif expected[name].read_bytes() != actual[name].read_bytes():
            errors.append(f"vendored file differs: {name}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the vendor copy is stale")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    source, target = paths(root)
    if args.check:
        errors = check(source, target)
        if errors:
            print("Skill runtime check failed:")
            for error in errors:
                print(f"- {error}")
            return 1
        print("Skill runtime check passed")
        return 0
    changed = sync(source, target)
    print(f"Synchronized Skill runtime: {len(changed)} file(s) updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
