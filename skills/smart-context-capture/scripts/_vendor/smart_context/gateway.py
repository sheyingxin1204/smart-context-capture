"""Provider-neutral Python gateway that connects routing to adapters."""

from __future__ import annotations

from collections.abc import Iterable
from time import perf_counter
from typing import Protocol

from .capabilities import CapabilityRegistry
from .cache import PacketCache
from .local_adapter import LocalFileAdapter
from .markitdown_adapter import MarkItDownAdapter
from .http_adapter import PublicHttpAdapter
from .models import Capability, CaptureRequest, ContextPacket, SourceType
from .router import ContextRouter, RouteDecision


class Adapter(Protocol):
    """Minimal contract required by the gateway.

    Chrome, Figma, and third-party adapters can implement this same pair of
    methods without being imported by the core package.
    """

    name: str
    source_type: SourceType

    def probe(self, locator: str) -> Capability:
        ...

    def capture(self, locator: str) -> ContextPacket:
        ...


class CaptureGatewayError(RuntimeError):
    """Raised when routing or provider execution cannot complete."""


class CaptureGateway:
    """Discover adapter health, route one request, and invoke the winner."""

    def __init__(
        self, adapters: Iterable[Adapter] = (), cache: PacketCache | None = None
    ) -> None:
        self.registry = CapabilityRegistry()
        self.router = ContextRouter(self.registry)
        self.cache = cache
        self._adapters: dict[tuple[SourceType, str], Adapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: Adapter) -> None:
        """Add or replace one provider implementation."""

        self._adapters[(adapter.source_type, adapter.name)] = adapter

    def diagnose(self) -> tuple[Capability, ...]:
        """Return a fast, side-effect-free provider readiness report."""

        results: list[Capability] = []
        for adapter in self._adapters.values():
            try:
                diagnostic = getattr(adapter, "diagnose", None)
                if callable(diagnostic):
                    capability = diagnostic()
                elif adapter.source_type == SourceType.LOCAL_FILE:
                    capability = Capability(
                        adapter.name,
                        adapter.source_type,
                        status=_available_status(),
                        message="parser loaded; readiness is path-specific",
                    )
                elif adapter.source_type == SourceType.CHROME_TAB:
                    capability = adapter.probe("current")
                else:
                    capability = adapter.probe("figma:diagnostic-file")
            except Exception as exc:
                capability = Capability(
                    adapter.name,
                    adapter.source_type,
                    status=_error_status(),
                    message=f"provider diagnostic failed: {exc}",
                )
            results.append(capability)
        return tuple(results)

    def inspect(
        self, request: CaptureRequest, *, exhaustive: bool = True
    ) -> tuple[Capability, ...]:
        """Probe adapters for a request.

        Exhaustive inspection is useful for ``--doctor``-style diagnostics.
        Capture routing uses the ordered, short-circuiting mode so an ordinary
        public URL does not wait for an unrelated CDP timeout.
        """

        source_type = self.router.detect_source(request)
        capabilities: list[Capability] = []
        if exhaustive:
            candidates = tuple(
                adapter
                for (kind, _), adapter in self._adapters.items()
                if kind == source_type
            )
        else:
            candidates = tuple(
                self._adapters.get((source_type, name))
                for name in self.router.adapter_order(request)
            )
            candidates = tuple(item for item in candidates if item is not None)

        operation = request.operations[0] if request.operations else "read"
        for adapter in candidates:
            try:
                capability = adapter.probe(request.locator)
            except Exception as exc:  # provider health must not crash routing
                capability = Capability(
                    adapter.name,
                    adapter.source_type,
                    status=_error_status(),
                    message=f"provider probe failed: {exc}",
                )
            self.registry.register(capability)
            capabilities.append(capability)
            if (
                not exhaustive
                and capability.status == _available_status()
                and operation in capability.operations
            ):
                break
        return tuple(capabilities)

    def decide(self, request: CaptureRequest) -> RouteDecision:
        """Refresh relevant capability state and return the route decision."""

        capabilities = self.inspect(request, exhaustive=False)
        try:
            return self.router.route(request)
        except (RuntimeError, ValueError) as exc:
            details = "; ".join(
                f"{item.adapter}: {item.message or item.status.value}"
                for item in capabilities
            )
            message = str(exc)
            if details:
                message += f". Capability details: {details}"
            raise CaptureGatewayError(message) from exc

    def capture(self, request: CaptureRequest) -> ContextPacket:
        """Capture through the selected adapter and annotate fallback use."""

        decision = self.decide(request)
        adapter = self._adapters.get((decision.source_type, decision.adapter))
        if adapter is None:
            raise CaptureGatewayError(
                f"adapter '{decision.adapter}' is registered as available but has no implementation"
            )
        cache_key: str | None = None
        if self.cache is not None and request.operations == ("read",):
            cache_key = self.cache.make_key(request, decision)
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        started = perf_counter()
        try:
            packet = adapter.capture(request.locator)
        except Exception as exc:
            raise CaptureGatewayError(
                f"adapter '{decision.adapter}' failed: {exc}"
            ) from exc
        packet.fallback_used = decision.fallback
        packet.provenance.append(
            {
                "adapter": "gateway",
                "route": decision.adapter,
                "fallback": decision.fallback,
                "duration_ms": round((perf_counter() - started) * 1000, 1),
            }
        )
        if self.cache is not None and cache_key is not None:
            self.cache.put(cache_key, packet)
        return packet


def build_local_gateway() -> CaptureGateway:
    """Return the dependency-free gateway available in the P1 build."""

    return CaptureGateway([LocalFileAdapter()])


def build_default_gateway() -> CaptureGateway:
    """Build the standard read-only gateway with optional providers.

    Provider construction is dependency-free.  Chrome is usable when a local
    CDP endpoint is exposed, and Figma is usable when an explicit token is
    configured; otherwise capability inspection reports the missing setup.
    """

    from .chrome_adapter import ChromeCdpAdapter
    from .figma_adapter import FigmaRestAdapter

    return CaptureGateway(
        [
            LocalFileAdapter(),
            MarkItDownAdapter(),
            ChromeCdpAdapter(),
            PublicHttpAdapter(),
            FigmaRestAdapter(),
        ]
    )


def _error_status():
    # Local import avoids adding an enum-only dependency to the Adapter
    # protocol's public annotations while keeping error conversion explicit.
    from .models import AdapterStatus

    return AdapterStatus.ERROR


def _available_status():
    from .models import AdapterStatus

    return AdapterStatus.AVAILABLE
