"""Tests for Redis-backed quota state reads."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.quota_state_service import read_quota_state


def test_read_quota_state_from_redis(monkeypatch) -> None:
    import time

    mock_client = MagicMock()
    mock_client.hgetall.return_value = {
        "window_start": str(time.time()),
        "requests_last_minute": "7",
        "tokens_today": "1200",
        "tokens_day": "2099-01-01",
    }

    monkeypatch.setenv("QUOTA_REDIS_URL", "redis://localhost:6379/0")

    import redis

    monkeypatch.setattr(redis.Redis, "from_url", lambda *_args, **_kwargs: mock_client)

    snapshot = read_quota_state("finance")
    assert snapshot is not None
    assert snapshot.source == "redis"
    assert snapshot.requests_last_minute == 7
    assert snapshot.tokens_today == 0
    mock_client.close.assert_called_once()
