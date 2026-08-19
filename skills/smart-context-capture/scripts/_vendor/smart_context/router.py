"""Source detection and adapter selection for the first project milestone."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .capabilities import CapabilityRegistry
from .models import AdapterStatus, CaptureRequest, SourceType


PRIMARY_ADAPTERS = {
    SourceType.LOCAL_FILE: "local",
    SourceType.CHROME_TAB: "chrome",
    SourceType.FIGMA_NODE: "figma",
}

FALLBACK_ADAPTERS = {
    SourceType.LOCAL_FILE: ("local-rich", "plain-text", "ocr"),
    SourceType.CHROME_TAB: ("public-http", "screenshot"),
    SourceType.FIGMA_NODE: ("export", "screenshot"),
}


@dataclass(frozen=True)
class RouteDecision:
    source_type: SourceType
    adapter: str
    fallback: bool
    reason: str


class ContextRouter:
    """Choose an available adapter without coupling to its implementation."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def detect_source(self, request: CaptureRequest) -> SourceType:
        if request.source_hint is not None:
            return request.source_hint

        locator = request.locator.lower()
        if "figma.com/" in locator or locator.startswith("figma:"):
            return SourceType.FIGMA_NODE
        if locator.startswith(("http://", "https://", "chrome://")):
            return SourceType.CHROME_TAB
        if Path(request.locator).exists() or Path(request.locator).suffix:
            return SourceType.LOCAL_FILE
        raise ValueError("Cannot infer source type; provide source_hint explicitly")

    def adapter_order(self, request: CaptureRequest) -> tuple[str, ...]:
        """Return providers in least-privilege order for one request."""

        source_type = self.detect_source(request)
        if source_type != SourceType.CHROME_TAB:
            return (PRIMARY_ADAPTERS[source_type], *FALLBACK_ADAPTERS[source_type])

        locator = request.locator.strip().lower()
        current_tab_locator = locator in {"current", "active", "active-tab", "current-tab"} or locator.startswith("chrome://")
        if current_tab_locator:
            return ("chrome", "screenshot")
        if request.prefer_browser_session:
            return ("chrome", "public-http", "screenshot")
        return ("public-http", "chrome", "screenshot")

    def route(self, request: CaptureRequest) -> RouteDecision:
        source_type = self.detect_source(request)
        operation = request.operations[0] if request.operations else "read"

        order = self.adapter_order(request)
        for index, adapter in enumerate(order):
            capability = self.registry.get(source_type, adapter)
            if (
                capability is not None
                and capability.status == AdapterStatus.AVAILABLE
                and operation in capability.operations
            ):
                return RouteDecision(
                    source_type,
                    adapter,
                    index > 0,
                    "primary adapter available" if index == 0 else f"using fallback {adapter}",
                )

        raise RuntimeError(
            f"No available adapter for {source_type.value}; "
            "install/configure the provider or provide an export"
        )
