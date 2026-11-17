"""Small expiring in-memory cache of actual locally generated speech, never substitute audio."""

from collections import OrderedDict
from copy import deepcopy
import threading
import time
from typing import Any


class SpeechCache:
    """Bound generated WAV bytes by count, bytes and monotonic TTL; no user text is a cache key."""

    def __init__(self, entries: int, max_bytes: int, ttl_seconds: float) -> None:
        if min(entries, max_bytes, ttl_seconds) <= 0:
            raise ValueError("Positive speech cache bounds required")
        self.entries, self.max_bytes, self.ttl_seconds = entries, max_bytes, ttl_seconds
        self.data: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self.bytes = 0
        self.lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        """Return only an unexpired previously generated result with independent metadata."""
        with self.lock:
            value = self.data.get(key)
            if value is None:
                return None
            if time.monotonic() - value[0] > self.ttl_seconds:
                self.bytes -= len(self.data.pop(key)[1]["audio_bytes"])
                return None
            self.data.move_to_end(key)
            return deepcopy(value[1])

    def put(self, key: str, value: dict[str, Any]) -> None:
        """Cache successful real audio only; oversized output remains uncached."""
        size = len(value["audio_bytes"])
        if size > self.max_bytes:
            return
        with self.lock:
            previous = self.data.pop(key, None)
            if previous:
                self.bytes -= len(previous[1]["audio_bytes"])
            while self.data and (
                len(self.data) >= self.entries or self.bytes + size > self.max_bytes
            ):
                self.bytes -= len(self.data.popitem(last=False)[1][1]["audio_bytes"])
            self.data[key] = (time.monotonic(), deepcopy(value))
            self.bytes += size
