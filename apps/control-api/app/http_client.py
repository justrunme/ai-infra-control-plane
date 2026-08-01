"""Shared httpx client for outbound control-plane probes."""

from __future__ import annotations

import threading
from typing import Any

import httpx

from app.settings import get_settings

_client: httpx.Client | None = None
_lock = threading.Lock()


def get_http_client() -> httpx.Client:
    """Return a process-wide httpx.Client singleton."""
    global _client
    if _client is not None:
        return _client

    with _lock:
        if _client is None:
            settings = get_settings()
            _client = httpx.Client(
                timeout=5.0,
                trust_env=settings.http_trust_env,
            )
    return _client


def close_http_client() -> None:
    """Close and clear the shared client."""
    global _client
    with _lock:
        if _client is not None:
            _client.close()
            _client = None


def get(url: str, **kwargs: Any) -> httpx.Response:
    """GET via the shared client."""
    return get_http_client().get(url, **kwargs)


def post(url: str, **kwargs: Any) -> httpx.Response:
    """POST via the shared client."""
    return get_http_client().post(url, **kwargs)
