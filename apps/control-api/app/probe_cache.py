"""Thread-safe TTL cache for short-lived probe results."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

_lock = threading.Lock()
_entries: dict[str, tuple[float, object]] = {}


def get_or_set[T](key: str, ttl_seconds: float, factory: Callable[[], T]) -> T:
    """Return a cached value or compute and store a fresh one."""
    now = time.monotonic()
    with _lock:
        entry = _entries.get(key)
        if entry is not None:
            expires_at, value = entry
            if now < expires_at:
                return value  # type: ignore[return-value]

        value = factory()
        _entries[key] = (now + max(ttl_seconds, 0.0), value)
        return value


def clear_probe_cache() -> None:
    """Drop all cached probe entries (tests/ops)."""
    with _lock:
        _entries.clear()
