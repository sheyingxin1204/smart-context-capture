"""Small privacy helpers for provenance and user-visible packet fields."""

from __future__ import annotations

import re
import urllib.parse


_SENSITIVE_QUERY = re.compile(
    r"(?:token|access[_-]?token|api[_-]?key|secret|password|passwd|session|sid|auth|code|sig|signature|credential|private[_-]?key)",
    re.IGNORECASE,
)


def redact_url(value: str) -> str:
    """Remove URL userinfo and likely secret query values for output only."""

    raw = str(value or "")
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError:
        return raw
    if parsed.scheme not in {"http", "https", "ws", "wss"} or not parsed.netloc:
        return raw

    try:
        hostname = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        return raw
    host = hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if port is not None:
        host = f"{host}:{port}"

    query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query = urllib.parse.urlencode(
        [
            (key, "[REDACTED]" if _SENSITIVE_QUERY.search(key) else val)
            for key, val in query_items
        ]
    )
    return urllib.parse.urlunsplit(
        (parsed.scheme, host, parsed.path, redacted_query, parsed.fragment)
    )
