"""Opt-in, JSON-backed packet cache for repeated context reads."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import CaptureRequest, ContextPacket
from .router import RouteDecision


class PacketCache(Protocol):
    def make_key(self, request: CaptureRequest, decision: RouteDecision) -> str:
        ...

    def get(self, key: str) -> ContextPacket | None:
        ...

    def put(self, key: str, packet: ContextPacket) -> None:
        ...


@dataclass(frozen=True)
class CachePolicy:
    ttl_seconds: float = 300.0


class FilePacketCache:
    """Persist packets only in a directory explicitly chosen by the user."""

    def __init__(
        self, directory: str | Path, policy: CachePolicy | None = None
    ) -> None:
        self.directory = Path(directory).expanduser().resolve()
        self.policy = policy or CachePolicy()

    def make_key(self, request: CaptureRequest, decision: RouteDecision) -> str:
        fingerprint = _locator_fingerprint(request.locator)
        payload = {
            "locator": request.locator,
            "fingerprint": fingerprint,
            "source_type": decision.source_type.value,
            "adapter": decision.adapter,
            "fallback": decision.fallback,
            "task": request.task,
            "operations": request.operations,
            "prefer_browser_session": request.prefer_browser_session,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def get(self, key: str) -> ContextPacket | None:
        cache_file = self.directory / f"{key}.json"
        try:
            raw = json.loads(cache_file.read_text(encoding="utf-8"))
            cached_at = float(raw["cached_at"])
            if time.time() - cached_at > self.policy.ttl_seconds:
                return None
            packet = ContextPacket.from_dict(raw["packet"])
            packet.warnings.append("served from opt-in packet cache")
            packet.provenance.append(
                {"adapter": "cache", "cached_at": cached_at, "cache_key": key}
            )
            return packet
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def put(self, key: str, packet: ContextPacket) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            cache_file = self.directory / f"{key}.json"
            temp_file = self.directory / f".{key}.{os.getpid()}.tmp"
            payload = {
                "cached_at": time.time(),
                "packet": packet.to_dict(),
            }
            temp_file.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            temp_file.replace(cache_file)
        except (OSError, TypeError, ValueError):
            # A cache must never turn a successful provider read into a failed
            # capture.  The next request will simply perform a fresh read.
            return


def _locator_fingerprint(locator: str) -> dict[str, object]:
    path = Path(locator).expanduser()
    try:
        stat = path.stat()
    except (OSError, ValueError):
        return {"kind": "remote-or-missing", "locator": locator}
    if not path.is_file():
        return {"kind": "non-file", "locator": locator}
    return {
        "kind": "file",
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
