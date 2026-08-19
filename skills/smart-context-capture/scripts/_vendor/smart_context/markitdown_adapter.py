"""Optional MarkItDown-backed adapter for rich local documents."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import AccessMode, AdapterStatus, Capability, ContextPacket, SourceType


class MarkItDownAdapterError(RuntimeError):
    """Raised when the optional MarkItDown provider cannot convert a file."""


class MarkItDownAdapter:
    """Use Microsoft MarkItDown when the user has installed it explicitly."""

    name = "local-rich"
    source_type = SourceType.LOCAL_FILE
    supported_extensions = {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".xls",
        ".epub",
        ".html",
        ".csv",
        ".json",
        ".xml",
        ".zip",
    }

    def __init__(self, max_bytes: int = 100 * 1024 * 1024) -> None:
        self.max_bytes = max_bytes

    def probe(self, locator: str) -> Capability:
        path = Path(locator).expanduser()
        if path.suffix.lower() not in self.supported_extensions:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNSUPPORTED,
                message=f"MarkItDown adapter does not target {path.suffix or 'this extension'}",
            )
        if not path.exists():
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNAVAILABLE,
                message=f"file does not exist: {path}",
            )
        if not path.is_file():
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNSUPPORTED,
                message=f"path is not a regular file: {path}",
            )
        if path.stat().st_size > self.max_bytes:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNSUPPORTED,
                message=f"file exceeds the {self.max_bytes} byte rich-document limit",
            )
        if self._load_converter() is None:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNAVAILABLE,
                message="install the optional 'markitdown' package to enable rich documents",
            )
        return Capability(
            self.name,
            self.source_type,
            AdapterStatus.AVAILABLE,
            metadata={"format": path.suffix.lower().lstrip(".")},
        )

    def diagnose(self) -> Capability:
        """Report optional dependency readiness without requiring a file path."""

        converter = self._load_converter()
        if converter is None:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNAVAILABLE,
                message="install the optional 'markitdown' package to enable rich documents",
            )
        return Capability(
            self.name,
            self.source_type,
            AdapterStatus.AVAILABLE,
            message="MarkItDown provider loaded; readiness is path-specific",
            metadata={"parser": "markitdown"},
        )

    def capture(self, locator: str) -> ContextPacket:
        path = Path(locator).expanduser().resolve()
        converter_type = self._load_converter()
        if converter_type is None:
            raise MarkItDownAdapterError(
                "optional MarkItDown is not installed; run 'pip install markitdown'"
            )
        if not path.exists() or not path.is_file():
            raise MarkItDownAdapterError(f"file is not readable: {path}")
        if path.stat().st_size > self.max_bytes:
            raise MarkItDownAdapterError(
                f"file exceeds the {self.max_bytes} byte rich-document limit"
            )
        try:
            converter = converter_type()
            result = converter.convert(str(path))
            content = str(getattr(result, "text_content", result) or "")
            title = getattr(result, "title", None) or path.name
        except Exception as exc:
            raise MarkItDownAdapterError(f"MarkItDown conversion failed: {exc}") from exc
        stat = path.stat()
        return ContextPacket(
            source_type=self.source_type,
            source_id=str(path),
            title=str(title),
            uri_or_path=str(path),
            content=content,
            structured_data={
                "format": path.suffix.lower().lstrip("."),
                "parser": "markitdown",
            },
            provenance=[
                {
                    "adapter": self.name,
                    "parser": "markitdown",
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            ],
            confidence="medium",
            warnings=[],
            adapter=self.name,
            fallback_used=True,
            access_mode=AccessMode.LOCAL_READ,
        )

    @staticmethod
    def _load_converter() -> Any | None:
        try:
            from markitdown import MarkItDown
        except ImportError:
            return None
        return MarkItDown
