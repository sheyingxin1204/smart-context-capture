"""Small JSON-first command-line entry point for local capture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .chrome_adapter import ChromeCdpAdapter, ChromeCdpPolicy
from .cache import FilePacketCache
from .figma_adapter import FigmaAdapterError, FigmaRestAdapter, FigmaRestPolicy
from .gateway import CaptureGateway, CaptureGatewayError
from .http_adapter import PublicHttpAdapter
from .local_adapter import LocalFileAdapter, LocalFilePolicy
from .markitdown_adapter import MarkItDownAdapter
from .models import CaptureRequest, SourceType


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smart-context",
        description="Capture a user-selected local file, Chrome tab, or Figma link.",
    )
    parser.add_argument(
        "locator",
        nargs="?",
        help="path, Chrome URL/title, or Figma URL (omit with --doctor)",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="report provider readiness without capturing content",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "local_file", "chrome_tab", "figma_node"),
        default="auto",
        help="source type (default: infer from the locator)",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=LocalFilePolicy.max_bytes,
        help="maximum file size to read (default: 20 MiB)",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="pretty-print JSON output"
    )
    parser.add_argument(
        "--content-only",
        action="store_true",
        help="print normalized content instead of the full packet",
    )
    parser.add_argument(
        "--cdp-url",
        default="",
        help="Chrome CDP base URL (default: SMART_CONTEXT_CDP_URL or localhost:9222)",
    )
    parser.add_argument(
        "--browser-session",
        action="store_true",
        help="prefer the configured Chrome session/CDP for a URL (needed for login state or the current tab)",
    )
    parser.add_argument(
        "--figma-token",
        default="",
        help="explicit Figma token (default: FIGMA_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "--figma-api-base",
        default="",
        help="Figma API base URL override, useful for a local test proxy",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="do not request a Figma node render URL",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=None,
        help="download Figma render assets into this directory",
    )
    parser.add_argument(
        "--confirm-download",
        action="store_true",
        help="explicitly authorize Figma asset downloads",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="opt in to a JSON packet cache at this directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    figma_adapter = FigmaRestAdapter(
        FigmaRestPolicy(
            token=args.figma_token,
            api_base=args.figma_api_base,
            include_render=not args.no_render,
        )
    )
    adapters = [
        LocalFileAdapter(LocalFilePolicy(max_bytes=args.max_bytes)),
        MarkItDownAdapter(),
        ChromeCdpAdapter(ChromeCdpPolicy(endpoint=args.cdp_url)),
        PublicHttpAdapter(),
        figma_adapter,
    ]
    cache = FilePacketCache(args.cache_dir) if args.cache_dir is not None else None
    gateway = CaptureGateway(adapters, cache=cache)
    if args.doctor:
        report = {
            "providers": [
                {
                    "adapter": item.adapter,
                    "source_type": item.source_type.value,
                    "status": item.status.value,
                    "operations": list(item.operations),
                    "message": item.message,
                    "metadata": dict(item.metadata),
                }
                for item in gateway.diagnose()
            ]
        }
        indent = 2 if args.pretty else None
        print(json.dumps(report, ensure_ascii=False, indent=indent))
        return 0
    if not args.locator:
        print(
            json.dumps(
                {"error": "MissingLocator", "message": "provide a locator or use --doctor"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    source_hint = None if args.source == "auto" else SourceType(args.source)
    operations = ("read", "download") if args.download_dir is not None else ("read",)
    try:
        packet = gateway.capture(
            CaptureRequest(
                args.locator,
                source_hint=source_hint,
                operations=operations,
                prefer_browser_session=args.browser_session,
            )
        )
        if args.download_dir is not None:
            if not args.confirm_download:
                raise CaptureGatewayError(
                    "--download-dir requires --confirm-download"
                )
            if packet.source_type != SourceType.FIGMA_NODE:
                raise CaptureGatewayError(
                    "--download-dir is only supported for Figma captures"
                )
            figma_adapter.download_assets(
                packet, args.download_dir, confirm=args.confirm_download
            )
    except (CaptureGatewayError, FigmaAdapterError) as exc:
        error = {"error": type(exc).__name__, "message": str(exc)}
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        return 2

    if args.content_only:
        print(packet.content)
    else:
        indent = 2 if args.pretty else None
        print(json.dumps(packet.to_dict(), ensure_ascii=False, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
