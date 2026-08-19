"""Core contracts for the Smart Context Capture project."""

from .version import __version__

from .capabilities import CapabilityRegistry
from .models import (
    AccessMode,
    AdapterStatus,
    Capability,
    CaptureRequest,
    ContextPacket,
    SourceType,
)
from .router import ContextRouter, RouteDecision
from .local_adapter import (
    FileTooLargeError,
    LocalAdapterError,
    LocalFileAdapter,
    LocalFilePolicy,
    UnsupportedLocalFileError,
)
from .gateway import CaptureGateway, CaptureGatewayError, build_local_gateway
from .gateway import build_default_gateway
from .chrome_adapter import (
    ChromeAdapterError,
    ChromeCdpAdapter,
    ChromeCdpPolicy,
    ChromeTargetNotFoundError,
    ChromeUnavailableError,
)
from .figma_adapter import (
    FigmaAdapterError,
    FigmaAuthError,
    FigmaLocatorError,
    FigmaRestAdapter,
    FigmaRestPolicy,
    parse_figma_locator,
)
from .markitdown_adapter import MarkItDownAdapter, MarkItDownAdapterError
from .http_adapter import HttpAdapterError, PublicHttpAdapter, PublicHttpPolicy
from .cache import CachePolicy, FilePacketCache

__all__ = [
    "AdapterStatus",
    "AccessMode",
    "Capability",
    "CapabilityRegistry",
    "CaptureRequest",
    "ContextPacket",
    "ContextRouter",
    "CaptureGateway",
    "CaptureGatewayError",
    "CachePolicy",
    "ChromeAdapterError",
    "ChromeCdpAdapter",
    "ChromeCdpPolicy",
    "ChromeTargetNotFoundError",
    "ChromeUnavailableError",
    "FileTooLargeError",
    "FilePacketCache",
    "FigmaAdapterError",
    "FigmaAuthError",
    "FigmaLocatorError",
    "FigmaRestAdapter",
    "FigmaRestPolicy",
    "HttpAdapterError",
    "LocalAdapterError",
    "LocalFileAdapter",
    "LocalFilePolicy",
    "MarkItDownAdapter",
    "MarkItDownAdapterError",
    "PublicHttpAdapter",
    "PublicHttpPolicy",
    "RouteDecision",
    "SourceType",
    "UnsupportedLocalFileError",
    "__version__",
    "build_default_gateway",
    "build_local_gateway",
    "parse_figma_locator",
]
