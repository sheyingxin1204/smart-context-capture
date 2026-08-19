"""In-memory capability registry used by the P0 router."""

from __future__ import annotations

from collections.abc import Iterable

from .models import AdapterStatus, Capability, SourceType


class CapabilityRegistry:
    """Keep provider health separate from routing policy."""

    def __init__(self, capabilities: Iterable[Capability] = ()) -> None:
        self._capabilities: dict[tuple[SourceType, str], Capability] = {
            (item.source_type, item.adapter): item for item in capabilities
        }

    def register(self, capability: Capability) -> None:
        self._capabilities[(capability.source_type, capability.adapter)] = capability

    def get(self, source_type: SourceType, adapter: str) -> Capability | None:
        return self._capabilities.get((source_type, adapter))

    def for_source(self, source_type: SourceType) -> tuple[Capability, ...]:
        return tuple(
            item for (kind, _), item in self._capabilities.items() if kind == source_type
        )

    def available_for(
        self, source_type: SourceType, operation: str = "read"
    ) -> tuple[Capability, ...]:
        return tuple(
            item
            for item in self.for_source(source_type)
            if item.status == AdapterStatus.AVAILABLE and operation in item.operations
        )

    def snapshot(self) -> tuple[Capability, ...]:
        return tuple(self._capabilities.values())
