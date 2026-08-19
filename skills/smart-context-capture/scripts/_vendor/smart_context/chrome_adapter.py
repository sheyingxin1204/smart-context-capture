"""Read-only Chrome DevTools Protocol adapter.

This adapter deliberately talks to the standard local CDP endpoint instead of
depending on one particular browser extension.  Chrome must be started with a
remote-debugging port (or an installed relay must expose a compatible
endpoint); a normal Chrome profile does not grant a process implicit access to
open tabs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import socket
import ssl
import struct
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .models import AccessMode, AdapterStatus, Capability, ContextPacket, SourceType
from .redaction import redact_url
from .version import USER_AGENT


class ChromeAdapterError(RuntimeError):
    """Base error for Chrome CDP failures."""


class ChromeUnavailableError(ChromeAdapterError):
    """Raised when the CDP endpoint cannot be reached."""


class ChromeTargetNotFoundError(ChromeAdapterError):
    """Raised when no open tab matches the requested locator."""


@dataclass(frozen=True)
class ChromeCdpPolicy:
    endpoint: str = ""
    timeout_seconds: float = 1.5
    max_text_chars: int = 200_000
    max_links: int = 500

    def resolved_endpoint(self) -> str:
        return (
            self.endpoint.strip()
            or os.environ.get("SMART_CONTEXT_CDP_URL", "")
            or "http://127.0.0.1:9222"
        ).rstrip("/")


class ChromeCdpAdapter:
    """Capture visible text and links from one existing Chrome page target."""

    name = "chrome"
    source_type = SourceType.CHROME_TAB

    def __init__(self, policy: ChromeCdpPolicy | None = None) -> None:
        self.policy = policy or ChromeCdpPolicy()

    def probe(self, locator: str) -> Capability:
        try:
            targets = self._list_targets()
        except ChromeUnavailableError as exc:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNAVAILABLE,
                message=str(exc),
                metadata={"transport": "cdp", "endpoint": self.policy.resolved_endpoint()},
            )
        try:
            target = self.select_target(targets, locator)
        except ChromeTargetNotFoundError as exc:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNAVAILABLE,
                message=str(exc),
                metadata={"transport": "cdp", "target_count": len(targets)},
            )
        return Capability(
            self.name,
            self.source_type,
            AdapterStatus.AVAILABLE,
            metadata={
                "transport": "cdp",
                "target_id": target.get("id"),
                "target_url": target.get("url"),
            },
        )

    def diagnose(self) -> Capability:
        """Check the CDP endpoint without guessing which tab is active."""

        try:
            targets = self._list_targets()
        except ChromeUnavailableError as exc:
            return Capability(
                self.name,
                self.source_type,
                AdapterStatus.UNAVAILABLE,
                message=str(exc),
                metadata={"transport": "cdp", "endpoint": self.policy.resolved_endpoint()},
            )
        pages = [item for item in targets if item.get("type") == "page"]
        return Capability(
            self.name,
            self.source_type,
            AdapterStatus.AVAILABLE if pages else AdapterStatus.UNAVAILABLE,
            message=(
                f"CDP endpoint loaded; {len(pages)} page target(s) available"
                if pages
                else "CDP endpoint loaded but no page targets are open"
            ),
            metadata={
                "transport": "cdp",
                "endpoint": self.policy.resolved_endpoint(),
                "page_count": len(pages),
            },
        )

    def capture(self, locator: str) -> ContextPacket:
        targets = self._list_targets()
        target = self.select_target(targets, locator)
        websocket_url = target.get("webSocketDebuggerUrl")
        if not websocket_url:
            raise ChromeAdapterError(
                "the selected Chrome tab does not expose a CDP websocket"
            )

        payload = _evaluate_page(websocket_url, self.policy)
        url = str(payload.get("url") or target.get("url") or "")
        safe_url = redact_url(url)
        title = str(payload.get("title") or target.get("title") or "") or None
        content = _normalize_newlines(str(payload.get("text") or "")).strip()
        warnings: list[str] = []
        if len(content) > self.policy.max_text_chars:
            content = content[: self.policy.max_text_chars] + "\n\n[content truncated]"
            warnings.append(
                f"page text truncated to {self.policy.max_text_chars} characters"
            )
        if not content:
            warnings.append("the selected tab returned no visible text")

        links = payload.get("links")
        if not isinstance(links, list):
            links = []
        safe_links = []
        for item in links[: self.policy.max_links]:
            if not isinstance(item, dict):
                continue
            safe_item = dict(item)
            if isinstance(safe_item.get("href"), str):
                safe_item["href"] = redact_url(safe_item["href"])
            safe_links.append(safe_item)
        structured_data = {
            "format": "chrome-dom",
            "url": safe_url,
            "title": title,
            "target_id": target.get("id"),
            "links": safe_links,
        }
        return ContextPacket(
            source_type=self.source_type,
            source_id=str(target.get("id") or safe_url),
            title=title,
            uri_or_path=safe_url,
            content=content,
            structured_data=structured_data,
            provenance=[
                {
                    "adapter": self.name,
                    "transport": "cdp",
                    "endpoint": self.policy.resolved_endpoint(),
                    "target_id": target.get("id"),
                    "url": safe_url,
                }
            ],
            confidence="high" if content else "low",
            warnings=warnings,
            adapter=self.name,
            fallback_used=False,
            access_mode=AccessMode.BROWSER_CDP_READ,
        )

    def _list_targets(self) -> list[dict[str, Any]]:
        endpoint = self.policy.resolved_endpoint()
        url = f"{endpoint}/json/list"
        try:
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(request, timeout=self.policy.timeout_seconds) as response:
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ChromeUnavailableError(
                    f"Chrome CDP endpoint refused access ({exc.code})"
                ) from exc
            raise ChromeUnavailableError(
                f"Chrome CDP endpoint returned HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ChromeUnavailableError(
                f"Chrome CDP endpoint unavailable at {url}: {exc}"
            ) from exc

        if not isinstance(value, list):
            raise ChromeUnavailableError("Chrome CDP /json/list returned a non-list response")
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def select_target(
        targets: list[dict[str, Any]], locator: str
    ) -> dict[str, Any]:
        pages = [item for item in targets if item.get("type") == "page"]
        if not pages:
            raise ChromeTargetNotFoundError("no normal page targets are open in Chrome")

        requested = (locator or "").strip()
        if requested.lower() in {"", "current", "chrome:current", "chrome://current"}:
            if len(pages) == 1:
                return pages[0]
            raise ChromeTargetNotFoundError(
                "CDP cannot identify the foreground tab among multiple pages; "
                "provide an exact URL, title, or target id, or use a Chrome connector"
            )

        for target in pages:
            if requested == str(target.get("id", "")):
                return target
        for target in pages:
            if requested == str(target.get("url", "")):
                return target

        lowered = requested.casefold()
        for target in pages:
            if lowered in str(target.get("url", "")).casefold():
                return target
            if lowered in str(target.get("title", "")).casefold():
                return target
        raise ChromeTargetNotFoundError(
            f"no open Chrome tab matched '{requested}'"
        )


def _evaluate_page(websocket_url: str, policy: ChromeCdpPolicy) -> dict[str, Any]:
    expression = """
(() => {
  const root = document.body || document.documentElement;
  const links = Array.from(document.querySelectorAll('a[href]'))
    .slice(0, 500)
    .map(a => ({text: (a.innerText || a.textContent || '').trim(), href: a.href}))
    .filter(x => x.href);
  return {
    title: document.title || '',
    url: location.href || '',
    text: root ? (root.innerText || root.textContent || '') : '',
    links
  };
})()
""".strip()
    try:
        result = _CdpWebSocket(websocket_url, policy.timeout_seconds).call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
    except (OSError, TimeoutError, ValueError) as exc:
        raise ChromeAdapterError(f"Chrome page evaluation failed: {exc}") from exc

    exception = result.get("exceptionDetails")
    if exception:
        description = exception.get("text") or "page evaluation raised an exception"
        raise ChromeAdapterError(str(description))
    value = result.get("result", {}).get("value")
    if not isinstance(value, dict):
        raise ChromeAdapterError("Chrome returned no structured page result")
    return value


class _CdpWebSocket:
    """Tiny client for the subset of WebSocket needed by CDP Runtime.evaluate."""

    def __init__(self, url: str, timeout: float) -> None:
        self.url = url
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._connect()
        try:
            self._send_text(
                json.dumps({"id": 1, "method": method, "params": params})
            )
            while True:
                message = self._receive_text()
                value = json.loads(message)
                if value.get("id") == 1:
                    return value.get("result", value)
        finally:
            self._close()

    def _connect(self) -> None:
        parsed = urllib.parse.urlsplit(self.url)
        if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
            raise ValueError(f"unsupported CDP websocket URL: {self.url}")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        sock = socket.create_connection((parsed.hostname, port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        if parsed.scheme == "wss":
            context = ssl.create_default_context()
            sock = context.wrap_socket(sock, server_hostname=parsed.hostname)
        self.sock = sock

        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        host_header = parsed.hostname
        if parsed.port:
            host_header += f":{parsed.port}"
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        sock.sendall(request)
        response = self._read_until(b"\r\n\r\n")
        header_text = response.decode("latin-1", errors="replace")
        if not header_text.startswith("HTTP/1.1 101"):
            raise OSError(f"CDP websocket handshake failed: {header_text.splitlines()[0]}")
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode("ascii")
        headers = {
            line.split(":", 1)[0].strip().lower(): line.split(":", 1)[1].strip()
            for line in header_text.splitlines()[1:]
            if ":" in line
        }
        if headers.get("sec-websocket-accept") != expected:
            raise OSError("CDP websocket handshake returned an invalid accept key")

    def _send_text(self, text: str) -> None:
        if self.sock is None:
            raise OSError("websocket is not connected")
        payload = text.encode("utf-8")
        mask_key = secrets.token_bytes(4)
        masked = bytes(value ^ mask_key[index % 4] for index, value in enumerate(payload))
        length = len(masked)
        if length < 126:
            header = bytes([0x81, 0x80 | length])
        elif length < 65536:
            header = bytes([0x81, 0x80 | 126]) + struct.pack("!H", length)
        else:
            header = bytes([0x81, 0x80 | 127]) + struct.pack("!Q", length)
        self.sock.sendall(header + mask_key + masked)

    def _receive_text(self) -> str:
        fragments: list[bytes] = []
        while True:
            first, second = self._read_exact(2)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            masked = bool(second & 0x80)
            mask_key = self._read_exact(4) if masked else b""
            payload = bytearray(self._read_exact(length))
            if masked:
                for index in range(length):
                    payload[index] ^= mask_key[index % 4]
            if opcode == 0x8:
                raise OSError("CDP websocket closed before returning a result")
            if opcode == 0x9:
                self._send_control(0xA, bytes(payload))
                continue
            if opcode in (0x1, 0x0):
                fragments.append(bytes(payload))
                if first & 0x80:
                    return b"".join(fragments).decode("utf-8")

    def _send_control(self, opcode: int, payload: bytes) -> None:
        if self.sock is None:
            return
        mask_key = secrets.token_bytes(4)
        masked = bytes(value ^ mask_key[index % 4] for index, value in enumerate(payload))
        self.sock.sendall(bytes([0x80 | opcode, 0x80 | len(masked)]) + mask_key + masked)

    def _read_until(self, marker: bytes) -> bytes:
        data = bytearray()
        while marker not in data:
            data.extend(self._read_exact(1))
        return bytes(data)

    def _read_exact(self, size: int) -> bytes:
        if self.sock is None:
            raise OSError("websocket is not connected")
        data = bytearray()
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise OSError("CDP websocket closed unexpectedly")
            data.extend(chunk)
        return bytes(data)

    def _close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
