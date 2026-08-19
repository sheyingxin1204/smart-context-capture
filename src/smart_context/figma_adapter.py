"""Read-only Figma REST adapter for file and node links.

The official Figma MCP remains the preferred provider when it is available.
This adapter is a small, dependency-free fallback for users who explicitly
configure a Figma personal/access token.  It never attempts to discover or
read browser cookies or the Figma desktop application's session.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .models import AccessMode, AdapterStatus, Capability, ContextPacket, SourceType
from .redaction import redact_url
from .version import USER_AGENT


class FigmaAdapterError(RuntimeError):
    """Base error for Figma REST failures."""


class FigmaAuthError(FigmaAdapterError):
    """Raised when no explicit Figma token is configured or it is rejected."""


class FigmaLocatorError(FigmaAdapterError):
    """Raised when a Figma file/node key cannot be parsed."""


@dataclass(frozen=True)
class FigmaRestPolicy:
    token: str = ""
    api_base: str = ""
    timeout_seconds: float = 8.0
    max_tree_depth: int = 8
    max_tree_nodes: int = 2_000
    include_render: bool = True
    max_download_bytes: int = 50 * 1024 * 1024

    def resolved_token(self) -> str:
        return (
            self.token.strip()
            or os.environ.get("FIGMA_ACCESS_TOKEN", "").strip()
            or os.environ.get("FIGMA_PERSONAL_ACCESS_TOKEN", "").strip()
        )

    def resolved_api_base(self) -> str:
        return (
            self.api_base.strip()
            or os.environ.get("SMART_CONTEXT_FIGMA_API_BASE", "").strip()
            or "https://api.figma.com"
        ).rstrip("/")


class FigmaRestAdapter:
    """Capture Figma file/node structure and optional render URLs."""

    # The router treats ``figma`` as the primary source adapter.  The
    # transport remains visible in provenance/metadata so an official MCP
    # implementation can replace this adapter without changing the packet.
    name = "figma"
    source_type = SourceType.FIGMA_NODE

    def __init__(self, policy: FigmaRestPolicy | None = None) -> None:
        self.policy = policy or FigmaRestPolicy()

    def probe(self, locator: str) -> Capability:
        try:
            file_key, node_id = parse_figma_locator(locator)
        except FigmaLocatorError as exc:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNSUPPORTED,
                message=str(exc),
            )
        if not self.policy.resolved_token():
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNAUTHORIZED,
                message="set FIGMA_ACCESS_TOKEN (or pass a token in FigmaRestPolicy)",
                metadata={"file_key": file_key, "node_id": node_id},
            )
        return Capability(
            self.name,
            self.source_type,
            AdapterStatus.AVAILABLE,
            metadata={"file_key": file_key, "node_id": node_id, "transport": "rest"},
        )

    def capture(self, locator: str) -> ContextPacket:
        file_key, node_id = parse_figma_locator(locator)
        token = self.policy.resolved_token()
        if not token:
            raise FigmaAuthError(
                "Figma REST requires an explicit FIGMA_ACCESS_TOKEN; browser login is not reused"
            )

        if node_id:
            endpoint = f"/v1/files/{urllib.parse.quote(file_key, safe='')}/nodes"
            payload = self._get(endpoint, {"ids": node_id})
            node_entry = next(iter(payload.get("nodes", {}).values()), {})
            node = node_entry.get("document", node_entry)
            file_name = payload.get("name") or node_entry.get("name")
        else:
            endpoint = f"/v1/files/{urllib.parse.quote(file_key, safe='')}"
            payload = self._get(endpoint, {"depth": 2})
            node = payload.get("document", {})
            file_name = payload.get("name")

        if not isinstance(node, dict):
            raise FigmaAdapterError("Figma returned no document/node object")

        warnings: list[str] = []
        tree_lines: list[str] = []
        state = {"count": 0, "truncated": False}
        _append_node_lines(
            node,
            tree_lines,
            depth=0,
            policy=self.policy,
            state=state,
        )
        if state["truncated"]:
            warnings.append(
                f"node tree truncated to depth {self.policy.max_tree_depth} or "
                f"{self.policy.max_tree_nodes} nodes"
            )

        components = payload.get("components") or {}
        styles = payload.get("styles") or {}
        component_names = _named_entries(components)
        style_names = _named_entries(styles)
        content_lines = [
            f"# {file_name or node.get('name') or 'Figma design'}",
            f"- File key: `{file_key}`",
            f"- Node: `{node_id or node.get('id', 'document')}`",
            f"- Root type: `{node.get('type', 'UNKNOWN')}`",
            "",
            "## Node tree",
            *(tree_lines or ["- (empty node tree)"]),
        ]
        if component_names:
            content_lines.extend(["", "## Components", *[f"- {name}" for name in component_names]])
        if style_names:
            content_lines.extend(["", "## Styles", *[f"- {name}" for name in style_names]])

        assets: list[dict[str, Any]] = []
        screenshots: list[dict[str, Any]] = []
        if node_id and self.policy.include_render:
            try:
                image_payload = self._get(
                    f"/v1/images/{urllib.parse.quote(file_key, safe='')}",
                    {"ids": node_id, "format": "png", "scale": "1"},
                )
                image_url = (image_payload.get("images") or {}).get(node_id)
                if image_url:
                    asset = {
                        "kind": "figma-render",
                        "node_id": node_id,
                        "format": "png",
                        "url": image_url,
                    }
                    assets.append(asset)
                    screenshots.append(asset.copy())
            except FigmaAdapterError as exc:
                warnings.append(f"render URL unavailable: {exc}")

        return ContextPacket(
            source_type=self.source_type,
            source_id=f"{file_key}:{node_id}" if node_id else file_key,
            title=str(file_name or node.get("name") or "Figma design"),
            uri_or_path=redact_url(locator),
            content="\n".join(content_lines),
            structured_data={
                "format": "figma-rest",
                "file_key": file_key,
                "node_id": node_id,
                "root": {
                    "id": node.get("id"),
                    "name": node.get("name"),
                    "type": node.get("type"),
                    "width": (node.get("absoluteBoundingBox") or {}).get("width"),
                    "height": (node.get("absoluteBoundingBox") or {}).get("height"),
                },
                "component_names": component_names,
                "style_names": style_names,
                "component_count": len(components) if isinstance(components, dict) else 0,
                "style_count": len(styles) if isinstance(styles, dict) else 0,
            },
            assets=assets,
            screenshots=screenshots,
            provenance=[
                {
                    "adapter": self.name,
                    "transport": "rest",
                    "api_base": self.policy.resolved_api_base(),
                    "file_key": file_key,
                    "node_id": node_id,
                }
            ],
            confidence="high" if node_id else "medium",
            warnings=warnings,
            adapter=self.name,
            fallback_used=False,
            access_mode=AccessMode.API_TOKEN_READ,
        )

    def download_assets(
        self,
        packet: ContextPacket,
        directory: str | Path,
        *,
        confirm: bool = False,
    ) -> list[Path]:
        """Download render URLs only after an explicit caller confirmation."""

        if not confirm:
            raise FigmaAdapterError(
                "asset download requires explicit confirmation (confirm=True)"
            )
        if packet.source_type != SourceType.FIGMA_NODE or packet.adapter != self.name:
            raise FigmaAdapterError("asset packet was not produced by this Figma adapter")

        destination = Path(directory).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []
        file_stem = packet.source_id.replace(":", "-").replace("/", "-")
        for index, asset in enumerate(packet.assets, start=1):
            url = str(asset.get("url") or "")
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme not in {"http", "https"}:
                continue
            suffix = Path(parsed.path).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
                suffix = ".bin"
            target = destination / f"figma-{file_stem}-{index}{suffix}"
            collision = 1
            while target.exists():
                target = destination / f"figma-{file_stem}-{index}-{collision}{suffix}"
                collision += 1
            request = urllib.request.Request(
                url,
                headers={"Accept": "image/*", "User-Agent": USER_AGENT},
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self.policy.timeout_seconds
                ) as response:
                    content = response.read(self.policy.max_download_bytes + 1)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise FigmaAdapterError(f"asset download failed: {exc}") from exc
            if len(content) > self.policy.max_download_bytes:
                raise FigmaAdapterError(
                    f"asset exceeds the {self.policy.max_download_bytes} byte limit"
                )
            target.write_bytes(content)
            asset["downloaded_path"] = str(target)
            downloaded.append(target)
            packet.provenance.append(
                {
                    "adapter": self.name,
                    "operation": "download",
                    "url": url,
                    "path": str(target),
                    "size_bytes": len(content),
                }
            )
        return downloaded

    def _get(self, endpoint: str, query: dict[str, Any]) -> dict[str, Any]:
        query_string = urllib.parse.urlencode(query)
        url = f"{self.policy.resolved_api_base()}{endpoint}"
        if query_string:
            url += "?" + query_string
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "X-Figma-Token": self.policy.resolved_token(),
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.policy.timeout_seconds) as response:
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise FigmaAuthError(
                    f"Figma rejected the configured token (HTTP {exc.code})"
                ) from exc
            raise FigmaAdapterError(
                f"Figma API returned HTTP {exc.code} for {endpoint}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise FigmaAdapterError(f"Figma API request failed: {exc}") from exc
        if not isinstance(value, dict):
            raise FigmaAdapterError("Figma API returned a non-object response")
        return value


def parse_figma_locator(locator: str) -> tuple[str, str | None]:
    """Extract a file key and optional node id from common Figma links."""

    raw = (locator or "").strip()
    if not raw:
        raise FigmaLocatorError("Figma locator is empty")

    if raw.startswith("figma:"):
        parsed = urllib.parse.urlsplit("https://figma.local/" + raw[6:])
        key_part = parsed.path.strip("/").split("/", 1)[0]
    elif raw.startswith("figma://"):
        parsed = urllib.parse.urlsplit(raw)
        key_part = parsed.netloc or parsed.path.strip("/").split("/", 1)[0]
    else:
        parsed = urllib.parse.urlsplit(raw)
        if parsed.scheme not in {"http", "https"} or "figma.com" not in parsed.netloc.casefold():
            raise FigmaLocatorError("locator is not a supported Figma URL or figma: key")
        parts = [part for part in parsed.path.split("/") if part]
        key_part = ""
        for marker in ("design", "file", "proto"):
            if marker in parts:
                index = parts.index(marker)
                if index + 1 < len(parts):
                    key_part = parts[index + 1]
                    break
        if not key_part and parts:
            key_part = parts[0]

    key = key_part.strip()
    if not key or len(key) < 5:
        raise FigmaLocatorError("could not find a Figma file key in locator")

    query = urllib.parse.parse_qs(parsed.query)
    fragment = urllib.parse.parse_qs(parsed.fragment)
    node_raw = (query.get("node-id") or query.get("node_id") or fragment.get("node-id") or [None])[0]
    node_id = _normalize_node_id(node_raw) if node_raw else None
    return key, node_id


def _normalize_node_id(value: str) -> str:
    return urllib.parse.unquote(value).replace("-", ":")


def _named_entries(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    names: list[str] = []
    for item in value.values():
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names[:500]


def _append_node_lines(
    node: dict[str, Any],
    lines: list[str],
    *,
    depth: int,
    policy: FigmaRestPolicy,
    state: dict[str, Any],
) -> None:
    if depth > policy.max_tree_depth or state["count"] >= policy.max_tree_nodes:
        state["truncated"] = True
        return
    state["count"] += 1
    indent = "  " * depth
    node_type = node.get("type", "UNKNOWN")
    name = node.get("name") or "(unnamed)"
    line = f"{indent}- {name} [{node_type}]"
    node_id = node.get("id")
    if node_id:
        line += f" (`{node_id}`)"
    bounds = node.get("absoluteBoundingBox")
    if isinstance(bounds, dict) and bounds.get("width") is not None:
        line += f" — {bounds.get('width')}×{bounds.get('height')}"
    characters = node.get("characters")
    if characters:
        preview = " ".join(str(characters).split())[:300]
        line += f" — text: {preview}"
    lines.append(line)
    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                _append_node_lines(
                    child,
                    lines,
                    depth=depth + 1,
                    policy=policy,
                    state=state,
                )
                if state["truncated"]:
                    break
