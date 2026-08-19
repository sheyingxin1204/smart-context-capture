"""Dependency-free preflight for the Smart Context Capture release tree."""

from __future__ import annotations

import json
import re
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    manifest_path = root / ".codex-plugin" / "plugin.json"
    skill_path = root / "skills" / "smart-context-capture" / "SKILL.md"
    version_path = root / "src" / "smart_context" / "version.py"
    for required in (manifest_path, skill_path, version_path):
        if not required.is_file():
            errors.append(f"missing required file: {required.relative_to(root)}")

    manifest: dict[str, object] = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid plugin manifest: {exc}")
    manifest_version = str(manifest.get("version", ""))
    pyproject_version = _read_pyproject_version(root / "pyproject.toml")
    runtime_version = _read_runtime_version(version_path)
    if len({manifest_version, pyproject_version, runtime_version}) != 1:
        errors.append(
            "version mismatch: "
            f"manifest={manifest_version!r}, pyproject={pyproject_version!r}, runtime={runtime_version!r}"
        )

    if skill_path.is_file():
        contents = skill_path.read_text(encoding="utf-8")
        frontmatter = contents.split("\n---", 1)[0] if contents.startswith("---\n") else ""
        if not frontmatter or "name:" not in frontmatter or "description:" not in frontmatter:
            errors.append("skills/smart-context-capture/SKILL.md has invalid frontmatter")
        if "--browser-session" not in contents or "public HTTP" not in contents:
            errors.append("Skill instructions do not document the permission ladder")

    forbidden = re.compile(
        r"(^|[\\/])(__pycache__|\.smart-context-cache|\.env$|\.git)([\\/]|$)|\.pyc$"
    )
    for item in root.rglob("*"):
        relative = str(item.relative_to(root))
        parts = set(Path(relative).parts)
        if parts.intersection(
            {
                ".git",
                "dist",
                "tests",
                "planning",
                "submission",
                "skill",
                "plugins",
                "__pycache__",
            }
        ) or ".egg-info" in relative:
            continue
        if item.is_file() and forbidden.search(relative):
            errors.append(f"release tree contains forbidden local artifact: {relative}")

    if errors:
        print("Release preflight failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Release preflight passed: version {manifest_version}")
    return 0


def _read_pyproject_version(path: Path) -> str:
    if not path.is_file():
        return ""
    match = re.search(
        r'^version\s*=\s*["\']([^"\']+)["\']',
        path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return match.group(1) if match else ""


def _read_runtime_version(path: Path) -> str:
    if not path.is_file():
        return ""
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return match.group(1) if match else ""


if __name__ == "__main__":
    raise SystemExit(main())
