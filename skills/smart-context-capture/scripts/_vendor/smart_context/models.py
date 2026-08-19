"""Small, dependency-free data contracts shared by adapters and the router."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .redaction import redact_url


class SourceType(str, Enum):
    LOCAL_FILE = "local_file"
    CHROME_TAB = "chrome_tab"
    FIGMA_NODE = "figma_node"


class AccessMode(str, Enum):
    """How a packet was obtained, including the privilege boundary."""

    LOCAL_READ = "local_read"
    PUBLIC_HTTP_READ = "public_http_read"
    CONNECTOR_READ = "connector_read"
    BROWSER_CDP_READ = "browser_cdp_read"
    API_TOKEN_READ = "api_token_read"
    COMPUTER_USE = "computer_use"
    EXTERNAL_WRITE = "external_write"
    UNKNOWN = "unknown"


class AdapterStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNAUTHORIZED = "unauthorized"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


@dataclass(frozen=True)
class CaptureRequest:
    """The normalized request passed from the Skill to the Python router."""

    locator: str
    task: str = "read"
    source_hint: SourceType | None = None
    operations: tuple[str, ...] = ("read",)
    session_id: str | None = None
    prefer_browser_session: bool = False


@dataclass(frozen=True)
class Capability:
    """A provider's current ability to serve one source type."""

    adapter: str
    source_type: SourceType
    status: AdapterStatus
    operations: tuple[str, ...] = ("read",)
    message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class ContextPacket:
    """Stable output contract returned to Codex."""

    source_type: SourceType
    source_id: str
    title: str | None = None
    uri_or_path: str | None = None
    content: str = ""
    structured_data: dict[str, Any] = field(default_factory=dict)
    assets: list[dict[str, Any]] = field(default_factory=list)
    screenshots: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)
    confidence: str = "low"
    warnings: list[str] = field(default_factory=list)
    adapter: str | None = None
    fallback_used: bool = False
    access_mode: AccessMode | str = AccessMode.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation of the packet.

        Keeping serialization next to the contract prevents every adapter or
        CLI entry point from inventing a slightly different result shape.
        """

        return {
            "source_type": self.source_type.value,
            "source_id": redact_url(self.source_id),
            "title": self.title,
            "uri_or_path": redact_url(self.uri_or_path or "") if self.uri_or_path else None,
            "content": self.content,
            "structured_data": _redact_packet_values(self.structured_data),
            "assets": _redact_packet_values(self.assets),
            "screenshots": _redact_packet_values(self.screenshots),
            "provenance": _redact_packet_values(self.provenance),
            "confidence": self.confidence,
            "warnings": self.warnings,
            "adapter": self.adapter,
            "fallback_used": self.fallback_used,
            "access_mode": (
                self.access_mode.value
                if isinstance(self.access_mode, AccessMode)
                else str(self.access_mode)
            ),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ContextPacket":
        """Rehydrate a packet from the JSON cache representation."""

        return cls(
            source_type=SourceType(str(value["source_type"])),
            source_id=str(value["source_id"]),
            title=value.get("title"),
            uri_or_path=value.get("uri_or_path"),
            content=str(value.get("content", "")),
            structured_data=dict(value.get("structured_data", {})),
            assets=list(value.get("assets", [])),
            screenshots=list(value.get("screenshots", [])),
            provenance=list(value.get("provenance", [])),
            confidence=str(value.get("confidence", "low")),
            warnings=list(value.get("warnings", [])),
            adapter=value.get("adapter"),
            fallback_used=bool(value.get("fallback_used", False)),
            access_mode=value.get("access_mode", AccessMode.UNKNOWN.value),
        )


_URL_FIELDS = {
    "url",
    "href",
    "requested_url",
    "final_url",
    "uri_or_path",
}


def _redact_packet_values(value: Any, key: str | None = None) -> Any:
    """Redact URL-like metadata while leaving captured text untouched."""

    if isinstance(value, dict):
        return {
            str(item_key): _redact_packet_values(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_packet_values(item) for item in value]
    if key in _URL_FIELDS and isinstance(value, str):
        return redact_url(value)
    return value
