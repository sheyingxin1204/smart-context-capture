"""Low-permission public HTTP adapter for ordinary web pages."""

from __future__ import annotations

import json
import gzip
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from .local_adapter import _decode_bytes
from .models import AccessMode, AdapterStatus, Capability, ContextPacket, SourceType
from .redaction import redact_url
from .version import USER_AGENT


class HttpAdapterError(RuntimeError):
    """Raised when a public HTTP fetch cannot be completed safely."""


@dataclass(frozen=True)
class PublicHttpPolicy:
    timeout_seconds: float = 6.0
    max_bytes: int = 10 * 1024 * 1024
    max_text_chars: int = 200_000
    max_links: int = 500


class _PageParser(HTMLParser):
    _ignored_tags = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._ignored_depth = 0
        self._in_title = False
        self._current_link: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in self._ignored_tags:
            self._ignored_depth += 1
        elif lowered == "title" and self._ignored_depth == 0:
            self._in_title = True
        elif lowered == "a" and self._ignored_depth == 0:
            href = dict(attrs).get("href")
            if href and len(self.links) < 500:
                self.links.append({"href": href, "text": ""})
                self._current_link = len(self.links) - 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        elif lowered == "title":
            self._in_title = False
        elif lowered == "a":
            self._current_link = None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        self.parts.append(data)
        if self._current_link is not None:
            self.links[self._current_link]["text"] += data


class PublicHttpAdapter:
    """Fetch public HTTP content without browser automation or login state."""

    name = "public-http"
    source_type = SourceType.CHROME_TAB

    def __init__(self, policy: PublicHttpPolicy | None = None) -> None:
        self.policy = policy or PublicHttpPolicy()

    def probe(self, locator: str) -> Capability:
        parsed = urllib.parse.urlsplit((locator or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNSUPPORTED,
                message="public HTTP adapter requires an http(s) URL",
            )
        return Capability(
            self.name,
            self.source_type,
            AdapterStatus.AVAILABLE,
            metadata={
                "transport": "http",
                "access_mode": AccessMode.PUBLIC_HTTP_READ.value,
                "uses_browser_session": False,
                "executes_javascript": False,
            },
        )

    def diagnose(self) -> Capability:
        return Capability(
            self.name,
            self.source_type,
            AdapterStatus.AVAILABLE,
            message="public HTTP reader loaded; readiness is URL-specific",
            metadata={
                "transport": "http",
                "access_mode": AccessMode.PUBLIC_HTTP_READ.value,
                "uses_browser_session": False,
            },
        )

    def capture(self, locator: str) -> ContextPacket:
        url = (locator or "").strip()
        capability = self.probe(url)
        if capability.status != AdapterStatus.AVAILABLE:
            raise HttpAdapterError(capability.message or "unsupported HTTP locator")

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.1",
                "Accept-Encoding": "gzip",
                "User-Agent": f"{USER_AGENT} (public-read-only)",
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.policy.timeout_seconds
            ) as response:
                final_url = response.geturl()
                status = getattr(response, "status", 200)
                content_type = response.headers.get_content_type()
                content_encoding = response.headers.get("Content-Encoding", "").lower()
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > self.policy.max_bytes:
                    raise HttpAdapterError(
                        f"response exceeds the {self.policy.max_bytes} byte limit"
                    )
                raw = response.read(self.policy.max_bytes + 1)
        except HttpAdapterError:
            raise
        except urllib.error.HTTPError as exc:
            raise HttpAdapterError(
                f"public HTTP request returned HTTP {exc.code}; it did not send browser login state; use --browser-session only if this page is authorized"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise HttpAdapterError(f"public HTTP request failed: {exc}") from exc

        if len(raw) > self.policy.max_bytes:
            raise HttpAdapterError(
                f"response exceeds the {self.policy.max_bytes} byte limit"
            )
        if "gzip" in content_encoding:
            try:
                raw = gzip.decompress(raw)
            except (OSError, EOFError) as exc:
                raise HttpAdapterError(f"invalid gzip HTTP response: {exc}") from exc
            if len(raw) > self.policy.max_bytes:
                raise HttpAdapterError(
                    f"decompressed response exceeds the {self.policy.max_bytes} byte limit"
                )
        text, encoding, replacement_used = _decode_bytes(raw)
        warnings = [
            "public HTTP read did not use browser cookies, login state, or JavaScript"
        ]
        if replacement_used:
            warnings.append("response contained undecodable bytes; replacement characters were inserted")
        title: str | None = None
        links: list[dict[str, str]] = []
        structured_data: dict[str, Any] = {
            "format": content_type,
            "status": status,
            "url": redact_url(final_url),
            "uses_browser_session": False,
            "executes_javascript": False,
            "encoding": encoding,
        }
        if content_type in {"text/html", "application/xhtml+xml"}:
            parser = _PageParser()
            parser.feed(text)
            parser.close()
            content = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
            title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip() or None
            links = [
                {
                    "text": " ".join(item["text"].split())[:500],
                    "href": redact_url(urllib.parse.urljoin(final_url, item["href"])),
                }
                for item in parser.links
            ][: self.policy.max_links]
            structured_data["title"] = title
            structured_data["links"] = links
            lowered_html = text.lower()
            javascript_shell_suspected = (
                not content
                or len(content) < 80
                and any(
                    marker in lowered_html
                    for marker in (
                        "enable javascript",
                        "javascript is required",
                        'id="root"',
                        'id="app"',
                        "__next_data__",
                    )
                )
            )
            structured_data["javascript_required_suspected"] = javascript_shell_suspected
            if javascript_shell_suspected:
                warnings.append(
                    "page may be a JavaScript-rendered shell; public HTTP did not execute JavaScript; use --browser-session if authorized"
                )
                confidence = "low"
            else:
                confidence = "medium"
        elif content_type == "application/json":
            try:
                value = json.loads(text)
                content = json.dumps(value, ensure_ascii=False, indent=2)
                structured_data["value"] = value
                confidence = "high"
            except json.JSONDecodeError as exc:
                content = text
                warnings.append(f"response advertised JSON but was invalid ({exc.msg})")
                confidence = "low"
        else:
            if b"\x00" in raw[:8192]:
                raise HttpAdapterError(
                    f"unsupported binary response content type: {content_type}"
                )
            content = text
            confidence = "medium"

        if len(content) > self.policy.max_text_chars:
            content = content[: self.policy.max_text_chars] + "\n\n[content truncated]"
            warnings.append(
                f"content truncated to {self.policy.max_text_chars} characters"
            )
        return ContextPacket(
            source_type=self.source_type,
            source_id=redact_url(final_url),
            title=title or redact_url(final_url),
            uri_or_path=redact_url(final_url),
            content=content,
            structured_data=structured_data,
            provenance=[
                {
                    "adapter": self.name,
                    "transport": "http",
                    "requested_url": redact_url(url),
                    "final_url": redact_url(final_url),
                    "content_type": content_type,
                    "content_encoding": content_encoding or None,
                    "status": status,
                }
            ],
            confidence=confidence,
            warnings=warnings,
            adapter=self.name,
            fallback_used=True,
            access_mode=AccessMode.PUBLIC_HTTP_READ,
        )
