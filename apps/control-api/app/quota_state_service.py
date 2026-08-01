"""Read shared tenant quota counters from Redis."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

REDIS_KEY_PREFIX = "ai:tenant:"

QuotaOnUnavailable = Literal["allow", "block", "approval_required"]


class QuotaStateSnapshot(BaseModel):
    team: str
    requests_last_minute: int = 0
    tokens_today: int = 0
    source: str = "request"
    unavailable: bool = False


class QuotaStateStatus(BaseModel):
    enabled: bool
    redis_url: str | None = None
    backend: str = "request"
    on_unavailable: QuotaOnUnavailable = "allow"


def is_quota_redis_enabled() -> bool:
    return bool(os.getenv("QUOTA_REDIS_URL", "").strip())


def get_quota_redis_url() -> str | None:
    url = os.getenv("QUOTA_REDIS_URL", "").strip()
    return url or None


def get_quota_on_unavailable() -> QuotaOnUnavailable:
    """Policy when Redis quota state cannot be read.

    Default ``allow`` preserves demo/dev fail-open. Production Helm sets
    ``approval_required`` (fail-closed to human review).
    """
    raw = os.getenv("QUOTA_ON_UNAVAILABLE", "allow").strip().lower()
    if raw in {"allow", "block", "approval_required"}:
        return raw  # type: ignore[return-value]
    return "allow"


def _normalize_state(
    state: dict[str, str], *, now: float | None = None
) -> tuple[int, int]:
    if not state:
        return 0, 0

    current = now if now is not None else time.time()
    window_start = float(state.get("window_start", 0) or 0)
    requests_last_minute = int(state.get("requests_last_minute", 0) or 0)
    tokens_today = int(state.get("tokens_today", 0) or 0)
    tokens_day = state.get("tokens_day") or ""

    if current - window_start >= 60:
        requests_last_minute = 0
    if tokens_day != datetime.now(UTC).strftime("%Y-%m-%d"):
        tokens_today = 0
    return requests_last_minute, tokens_today


def read_quota_state(team: str) -> QuotaStateSnapshot | None:
    """Return Redis snapshot, an unavailable marker, or None when Redis is off.

    - Redis disabled → ``None`` (caller uses request body counters).
    - Redis error → snapshot with ``unavailable=True`` (caller applies
      ``QUOTA_ON_UNAVAILABLE``).
    - Redis ok → normal snapshot ``source=redis``.
    """
    redis_url = get_quota_redis_url()
    if not redis_url:
        return None

    import redis

    try:
        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        try:
            state = client.hgetall(f"{REDIS_KEY_PREFIX}{team}")
        finally:
            client.close()
    except Exception:  # noqa: BLE001
        return QuotaStateSnapshot(
            team=team,
            source="unavailable",
            unavailable=True,
        )

    rpm, tokens = _normalize_state(state)
    return QuotaStateSnapshot(
        team=team,
        requests_last_minute=rpm,
        tokens_today=tokens,
        source="redis",
        unavailable=False,
    )


def quota_state_status() -> QuotaStateStatus:
    redis_url = get_quota_redis_url()
    return QuotaStateStatus(
        enabled=bool(redis_url),
        redis_url=redis_url,
        backend="redis" if redis_url else "request",
        on_unavailable=get_quota_on_unavailable(),
    )
