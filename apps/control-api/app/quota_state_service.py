"""Read and update shared tenant quota counters in Redis (server-authoritative)."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

REDIS_KEY_PREFIX = "ai:tenant:"
FINOPS_KEY_PREFIX = "ai:finops:"

QuotaOnUnavailable = Literal["allow", "block", "approval_required"]

# Atomic read of the legacy hash format written by the runtime gateway, with
# sliding-window normalization. Returns rpm, tokens_today, or nil on miss.
_READ_QUOTA_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local today = ARGV[2]
local state = redis.call('HGETALL', key)
if #state == 0 then
  return {0, 0}
end
local map = {}
for i = 1, #state, 2 do
  map[state[i]] = state[i + 1]
end
local window_start = tonumber(map['window_start'] or '0') or 0
local rpm = tonumber(map['requests_last_minute'] or '0') or 0
local tokens = tonumber(map['tokens_today'] or '0') or 0
local tokens_day = map['tokens_day'] or ''
if (now - window_start) >= 60 then
  rpm = 0
end
if tokens_day ~= today then
  tokens = 0
end
return {rpm, tokens}
"""

# Atomic INCR + EXPIRE for fixed-window RPM and daily token counters.
_INCR_QUOTA_LUA = """
local rpm_key = KEYS[1]
local tokens_key = KEYS[2]
local hash_key = KEYS[3]
local now = tonumber(ARGV[1])
local today = ARGV[2]
local token_delta = tonumber(ARGV[3])
local rpm_ttl = tonumber(ARGV[4])
local tokens_ttl = tonumber(ARGV[5])

local rpm = redis.call('INCR', rpm_key)
if rpm == 1 then
  redis.call('EXPIRE', rpm_key, rpm_ttl)
end
local tokens = redis.call('INCRBY', tokens_key, token_delta)
if tokens == token_delta then
  redis.call('EXPIRE', tokens_key, tokens_ttl)
end

-- Keep the legacy hash in sync for readers that still use HGETALL.
redis.call('HSET', hash_key,
  'window_start', tostring(now - (now % 60)),
  'requests_last_minute', tostring(rpm),
  'tokens_today', tostring(tokens),
  'tokens_day', today)
redis.call('EXPIRE', hash_key, math.max(rpm_ttl, tokens_ttl))
return {rpm, tokens}
"""


class QuotaStateSnapshot(BaseModel):
    team: str
    requests_last_minute: int = 0
    tokens_today: int = 0
    month_to_date_cost_usd: float = 0.0
    source: str = "request"
    unavailable: bool = False


class QuotaStateStatus(BaseModel):
    enabled: bool
    redis_url: str | None = None
    backend: str = "request"
    on_unavailable: QuotaOnUnavailable = "approval_required"


def is_quota_redis_enabled() -> bool:
    return bool(os.getenv("QUOTA_REDIS_URL", "").strip())


def get_quota_redis_url() -> str | None:
    url = os.getenv("QUOTA_REDIS_URL", "").strip()
    return url or None


def get_quota_on_unavailable() -> QuotaOnUnavailable:
    """Policy when Redis quota state cannot be read.

    Default ``approval_required`` fails closed to human review. ``allow`` is
    opt-in only (explicit ``QUOTA_ON_UNAVAILABLE=allow``) and must be marked
    with reason ``quota_backend_unavailable_allowed``. Unknown values fail closed.
    """
    raw = os.getenv("QUOTA_ON_UNAVAILABLE", "approval_required").strip().lower()
    if raw in {"allow", "block", "approval_required"}:
        return raw  # type: ignore[return-value]
    return "approval_required"


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


def _minute_bucket(now: float | None = None) -> int:
    current = int(now if now is not None else time.time())
    return current - (current % 60)


def _redis_client(redis_url: str):
    import redis

    return redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )


def read_finops_month_cost(team: str) -> float | None:
    """Return month-to-date spend from Redis, or None when Redis is off/error."""
    redis_url = get_quota_redis_url()
    if not redis_url:
        return None
    try:
        client = _redis_client(redis_url)
        try:
            raw = client.get(f"{FINOPS_KEY_PREFIX}{team}:month_to_date_cost_usd")
        finally:
            client.close()
    except Exception:  # noqa: BLE001
        return None
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def read_quota_state(team: str) -> QuotaStateSnapshot | None:
    """Return Redis snapshot, an unavailable marker, or None when Redis is off.

    - Redis disabled → ``None`` (caller applies simulate / onUnavailable policy).
    - Redis error → snapshot with ``unavailable=True``.
    - Redis ok → normal snapshot ``source=redis`` (server-authoritative).
    """
    redis_url = get_quota_redis_url()
    if not redis_url:
        return None

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    now = time.time()
    try:
        client = _redis_client(redis_url)
        try:
            # Prefer atomic counters when present; fall back to legacy hash.
            rpm_key = f"{REDIS_KEY_PREFIX}{team}:rpm:{_minute_bucket(now)}"
            tokens_key = f"{REDIS_KEY_PREFIX}{team}:tokens:{today}"

            def _as_int(value: object) -> int | None:
                if value is None or isinstance(value, bool):
                    return None
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                    return int(value)
                return None

            rpm_counter = _as_int(client.get(rpm_key))
            tokens_counter = _as_int(client.get(tokens_key))
            if rpm_counter is not None or tokens_counter is not None:
                rpm = int(rpm_counter or 0)
                tokens = int(tokens_counter or 0)
            else:
                result = client.eval(
                    _READ_QUOTA_LUA,
                    1,
                    f"{REDIS_KEY_PREFIX}{team}",
                    str(now),
                    today,
                )
                rpm = int(result[0] if result else 0)
                tokens = int(result[1] if result else 0)
            month_cost_raw = client.get(
                f"{FINOPS_KEY_PREFIX}{team}:month_to_date_cost_usd"
            )
            month_cost_parsed = _as_int(month_cost_raw)
            if month_cost_parsed is not None:
                month_cost = float(month_cost_parsed)
            elif isinstance(month_cost_raw, str):
                try:
                    month_cost = float(month_cost_raw)
                except ValueError:
                    month_cost = 0.0
            else:
                month_cost = 0.0
        finally:
            client.close()
    except Exception:  # noqa: BLE001
        return QuotaStateSnapshot(
            team=team,
            source="unavailable",
            unavailable=True,
        )

    return QuotaStateSnapshot(
        team=team,
        requests_last_minute=rpm,
        tokens_today=tokens,
        month_to_date_cost_usd=month_cost,
        source="redis",
        unavailable=False,
    )


def incr_quota_counters(
    team: str,
    *,
    tokens: int = 0,
) -> QuotaStateSnapshot | None:
    """Atomically increment RPM/token counters (INCR + EXPIRE via Lua)."""
    redis_url = get_quota_redis_url()
    if not redis_url:
        return None
    now = time.time()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    rpm_key = f"{REDIS_KEY_PREFIX}{team}:rpm:{_minute_bucket(now)}"
    tokens_key = f"{REDIS_KEY_PREFIX}{team}:tokens:{today}"
    hash_key = f"{REDIS_KEY_PREFIX}{team}"
    try:
        client = _redis_client(redis_url)
        try:
            result = client.eval(
                _INCR_QUOTA_LUA,
                3,
                rpm_key,
                tokens_key,
                hash_key,
                str(now),
                today,
                str(max(int(tokens), 0)),
                "120",
                "172800",
            )
            rpm = int(result[0] if result else 0)
            token_total = int(result[1] if result else 0)
        finally:
            client.close()
    except Exception:  # noqa: BLE001
        return QuotaStateSnapshot(
            team=team,
            source="unavailable",
            unavailable=True,
        )
    return QuotaStateSnapshot(
        team=team,
        requests_last_minute=rpm,
        tokens_today=token_total,
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
