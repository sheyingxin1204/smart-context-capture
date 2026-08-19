"""Build the clean, skills-only plugin archive used for submission.

The archive is an explicit allow-list rather than a zip of the repository, so
tests, draft legal pages, local caches, credentials, and Git metadata cannot
leak into a public upload by accident.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


TOP_LEVEL_FILES = (
    ".codex-plugin/plugin.json",
    ".env.example",
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "scripts/build_release.py",
    "scripts/check_release.py",
    "scripts/sync_skill_runtime.py",
)
RUNTIME_ROOTS = (
    "skills/smart-context-capture",
    "src/smart_context",
)


def manifest_version(root: Path) -> str:
    value = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    version = str(value.get("version", "")).strip()
    if not version:
        raise SystemExit("plugin manifest has no version")
    return version


def release_files(root: Path) -> list[Path]:
    paths: set[Path] = {root / item for item in TOP_LEVEL_FILES}
    for relative_root in RUNTIME_ROOTS:
        runtime_root = root / relative_root
        if not runtime_root.is_dir():
            raise SystemExit(f"missing runtime directory: {relative_root}")
        for item in runtime_root.rglob("*"):
            if not item.is_file():
                continue
            if "__pycache__" in item.parts or item.suffix in {".pyc", ".pyo"}:
                continue
            paths.add(item)
    missing = [str(item.relative_to(root)) for item in paths if not item.is_file()]
    if missing:
        raise SystemExit("missing release file(s): " + ", ".join(sorted(missing)))
    return sorted(paths, key=lambda item: item.relative_to(root).as_posix())


def build(root: Path, output: Path) -> tuple[Path, Path]:
    files = release_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in files:
            relative = item.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, item.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest().upper()
    checksum = output.with_suffix(".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return output, checksum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="override the release ZIP path")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    version = manifest_version(root)
    output = args.output or root / "dist" / f"smart-context-capture-{version}-release.zip"
    archive, checksum = build(root, output)
    print(f"Built {archive}")
    print(f"SHA-256 file: {checksum}")
    print(f"SHA-256: {hashlib.sha256(archive.read_bytes()).hexdigest().upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
