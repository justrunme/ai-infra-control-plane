"""Tests for Redis-backed quota state reads."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.quota_state_service import incr_quota_counters, read_quota_state


def test_read_quota_state_from_redis(monkeypatch) -> None:
    import time

    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_client.eval.return_value = [7, 0]

    monkeypatch.setenv("QUOTA_REDIS_URL", "redis://localhost:6379/0")

    import redis

    monkeypatch.setattr(redis.Redis, "from_url", lambda *_args, **_kwargs: mock_client)

    snapshot = read_quota_state("finance")
    assert snapshot is not None
    assert snapshot.source == "redis"
    assert snapshot.requests_last_minute == 7
    assert snapshot.tokens_today == 0
    mock_client.eval.assert_called_once()
    mock_client.close.assert_called_once()
    # Legacy hash path receives window normalization inputs.
    args = mock_client.eval.call_args[0]
    assert args[2].startswith("ai:tenant:finance")
    assert abs(float(args[3]) - time.time()) < 5


def test_read_quota_state_prefers_atomic_counters(monkeypatch) -> None:
    mock_client = MagicMock()

    def _get(key: str):
        if key.endswith(":rpm:0") or ":rpm:" in key:
            return "11"
        if ":tokens:" in key:
            return "2200"
        if "month_to_date_cost_usd" in key:
            return "12.5"
        return None

    mock_client.get.side_effect = _get
    monkeypatch.setenv("QUOTA_REDIS_URL", "redis://localhost:6379/0")

    import redis

    monkeypatch.setattr(redis.Redis, "from_url", lambda *_args, **_kwargs: mock_client)

    snapshot = read_quota_state("finance")
    assert snapshot is not None
    assert snapshot.requests_last_minute == 11
    assert snapshot.tokens_today == 2200
    assert snapshot.month_to_date_cost_usd == 12.5
    mock_client.eval.assert_not_called()


def test_incr_quota_counters_uses_lua(monkeypatch) -> None:
    mock_client = MagicMock()
    mock_client.eval.return_value = [3, 450]
    monkeypatch.setenv("QUOTA_REDIS_URL", "redis://localhost:6379/0")

    import redis

    monkeypatch.setattr(redis.Redis, "from_url", lambda *_args, **_kwargs: mock_client)

    snapshot = incr_quota_counters("platform", tokens=50)
    assert snapshot is not None
    assert snapshot.requests_last_minute == 3
    assert snapshot.tokens_today == 450
