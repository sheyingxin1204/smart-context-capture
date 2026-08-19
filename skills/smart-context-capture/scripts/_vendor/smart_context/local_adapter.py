"""Read-only, dependency-free local file adapter for the P1 milestone.

The adapter intentionally covers formats that can be handled reliably with
the Python standard library.  Rich binary formats (PDF, Office files, and
images) are reported as unsupported until an optional provider is explicitly
installed and registered; they are never silently treated as plain text.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .models import AccessMode, AdapterStatus, Capability, ContextPacket, SourceType


class LocalAdapterError(RuntimeError):
    """Base error for a local-file capture failure."""


class FileTooLargeError(LocalAdapterError):
    """Raised before reading a file that exceeds the configured byte limit."""


class UnsupportedLocalFileError(LocalAdapterError):
    """Raised when no safe parser is registered for the file."""


@dataclass(frozen=True)
class LocalFilePolicy:
    """Safety and output limits for local reads."""

    max_bytes: int = 20 * 1024 * 1024
    max_text_chars: int = 200_000
    max_rows: int = 5_000
    max_cell_chars: int = 2_000


class _VisibleTextParser(HTMLParser):
    """Extract visible-ish text without depending on BeautifulSoup."""

    _ignored_tags = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._ignored_tags:
            self._ignored_depth += 1
        elif tag == "title" and self._ignored_depth == 0:
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        self.parts.append(data)


class LocalFileAdapter:
    """Capture local text and common structured files without writing them."""

    name = "local"
    source_type = SourceType.LOCAL_FILE

    _text_extensions = {
        ".txt",
        ".md",
        ".markdown",
        ".rst",
        ".log",
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".css",
        ".scss",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".xml",
        ".svg",
    }
    _html_extensions = {".html", ".htm"}
    _csv_extensions = {".csv", ".tsv"}
    _json_extensions = {".json", ".jsonl", ".ndjson"}

    def __init__(self, policy: LocalFilePolicy | None = None) -> None:
        self.policy = policy or LocalFilePolicy()

    def probe(self, path: str | Path) -> Capability:
        """Report whether this adapter can read ``path`` without capturing it."""

        candidate = Path(path).expanduser()
        if not candidate.exists():
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNAVAILABLE,
                message=f"file does not exist: {candidate}",
            )
        if not candidate.is_file():
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNSUPPORTED,
                message=f"path is not a regular file: {candidate}",
            )
        if candidate.stat().st_size > self.policy.max_bytes:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNSUPPORTED,
                message=(
                    f"file is larger than the {self.policy.max_bytes} byte limit"
                ),
            )

        kind = self._kind_for(candidate)
        if kind is None:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNSUPPORTED,
                message=f"no local parser registered for {candidate.suffix or 'this file'}",
            )
        try:
            with candidate.open("rb") as handle:
                sample = handle.read(8192)
            if b"\x00" in sample:
                return Capability(
                    self.name,
                    self.source_type,
                    AdapterStatus.UNSUPPORTED,
                    message="file contains binary NUL bytes",
                )
        except OSError as exc:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.ERROR,
                message=f"cannot inspect file: {exc}",
            )
        return Capability(
            self.name,
            self.source_type,
            AdapterStatus.AVAILABLE,
            metadata={"format": kind},
        )

    def capture(self, path: str | Path) -> ContextPacket:
        """Read and normalize one user-selected file into a ``ContextPacket``."""

        candidate = Path(path).expanduser()
        if not candidate.exists():
            raise LocalAdapterError(f"file does not exist: {candidate}")
        if not candidate.is_file():
            raise LocalAdapterError(f"path is not a regular file: {candidate}")

        stat = candidate.stat()
        if stat.st_size > self.policy.max_bytes:
            raise FileTooLargeError(
                f"file is {stat.st_size} bytes; limit is {self.policy.max_bytes} bytes"
            )

        resolved = candidate.resolve()
        kind = self._kind_for(resolved)
        if kind is None:
            raise UnsupportedLocalFileError(
                f"no local parser registered for {resolved.suffix or 'this file'}"
            )

        raw = resolved.read_bytes()
        if b"\x00" in raw[:8192]:
            raise UnsupportedLocalFileError(
                "file contains binary NUL bytes; an explicit binary parser is required"
            )
        text, encoding, replacement_used = _decode_bytes(raw)
        warnings: list[str] = []
        if replacement_used:
            warnings.append(
                "file contained undecodable bytes; replacement characters were inserted"
            )

        structured_data: dict[str, Any] = {"format": kind}
        confidence = "medium"
        if kind == "json":
            content, structured_data, parse_warnings = self._parse_json(text)
            warnings.extend(parse_warnings)
            confidence = "high" if not parse_warnings else "medium"
        elif kind == "csv":
            content, structured_data, parse_warnings = self._parse_csv(text, resolved)
            warnings.extend(parse_warnings)
            confidence = "high"
        elif kind == "html":
            content, title = self._parse_html(text)
            structured_data["title"] = title
            confidence = "medium"
        else:
            content = text
            confidence = "high"

        content, truncated = _limit_text(content, self.policy.max_text_chars)
        if truncated:
            warnings.append(
                f"content truncated to {self.policy.max_text_chars} characters"
            )

        modified_at = datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat()
        provenance = [
            {
                "adapter": self.name,
                "path": str(resolved),
                "size_bytes": stat.st_size,
                "modified_at": modified_at,
                "encoding": encoding,
                "format": kind,
            }
        ]
        return ContextPacket(
            source_type=self.source_type,
            source_id=str(resolved),
            title=resolved.name,
            uri_or_path=str(resolved),
            content=content,
            structured_data=structured_data,
            provenance=provenance,
            confidence=confidence,
            warnings=warnings,
            adapter=self.name,
            fallback_used=False,
            access_mode=AccessMode.LOCAL_READ,
        )

    def _kind_for(self, path: Path) -> str | None:
        suffix = path.suffix.lower()
        if suffix in self._json_extensions:
            return "json"
        if suffix in self._csv_extensions:
            return "csv"
        if suffix in self._html_extensions:
            return "html"
        if suffix in self._text_extensions:
            return "text"
        return None

    def _parse_json(
        self, text: str
    ) -> tuple[str, dict[str, Any], list[str]]:
        warnings: list[str] = []
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            warnings.append(f"invalid JSON; returned raw text ({exc.msg})")
            content = text
            return content, {"format": "json", "parse_error": exc.msg}, warnings

        content = json.dumps(value, ensure_ascii=False, indent=2)
        return content, {"format": "json", "value": value}, warnings

    def _parse_csv(
        self, text: str, path: Path
    ) -> tuple[str, dict[str, Any], list[str]]:
        warnings: list[str] = []
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        if path.suffix.lower() != ".tsv":
            try:
                sample = text[:8192]
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            except csv.Error:
                pass

        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        truncated = len(rows) > self.policy.max_rows
        rows = rows[: self.policy.max_rows]
        if truncated:
            warnings.append(f"rows truncated to {self.policy.max_rows}")

        if not rows:
            return "", {
                "format": "csv",
                "delimiter": delimiter,
                "columns": [],
                "rows": [],
                "row_count": 0,
            }, warnings

        raw_header = rows[0]
        columns = [
            _trim_cell(value, self.policy.max_cell_chars) or f"column_{index + 1}"
            for index, value in enumerate(raw_header)
        ]
        data_rows = rows[1:]
        normalized_rows: list[list[str]] = []
        for row in data_rows:
            normalized = [
                _trim_cell(value, self.policy.max_cell_chars) for value in row
            ]
            if len(normalized) < len(columns):
                normalized.extend([""] * (len(columns) - len(normalized)))
            normalized_rows.append(normalized[: len(columns)])

        content = _markdown_table(columns, normalized_rows)
        structured = {
            "format": "csv",
            "delimiter": delimiter,
            "columns": columns,
            "rows": normalized_rows,
            "row_count": len(data_rows),
            "total_rows_read": len(rows),
        }
        return content, structured, warnings

    def _parse_html(self, text: str) -> tuple[str, str | None]:
        parser = _VisibleTextParser()
        parser.feed(text)
        parser.close()
        content = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
        title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip() or None
        return content, title


def _decode_bytes(data: bytes) -> tuple[str, str, bool]:
    """Decode common local encodings, preserving a useful provenance label."""

    if data.startswith(b"\xef\xbb\xbf"):
        candidates = ["utf-8-sig", "utf-8", "gb18030", "big5", "cp1252", "latin-1"]
    else:
        candidates = ["utf-8", "gb18030", "big5", "cp1252", "latin-1"]
    for encoding in candidates:
        try:
            return _normalize_newlines(data.decode(encoding)), encoding, False
        except UnicodeDecodeError:
            continue
    return _normalize_newlines(data.decode("utf-8", errors="replace")), "utf-8", True


def _normalize_newlines(text: str) -> str:
    """Use one newline convention in packets from Windows and Unix files."""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def _limit_text(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n\n[content truncated]", True


def _trim_cell(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "…"


def _markdown_table(columns: list[str], rows: list[list[str]]) -> str:
    if not columns:
        return ""
    header = "| " + " | ".join(_escape_pipe(value) for value in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(_escape_pipe(value) for value in row) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
