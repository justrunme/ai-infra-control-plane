"""Shared fixtures for control-api tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Isolate durable state before app modules create singletons.
_TEST_DB = Path(__file__).resolve().parent / ".testdata" / "control-plane-test.db"
_TEST_DB.parent.mkdir(parents=True, exist_ok=True)
if _TEST_DB.exists():
    _TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ.setdefault("HTTP_TRUST_ENV", "false")
os.environ.setdefault("PROBE_CACHE_TTL_SECONDS", "0")


@pytest.fixture(autouse=True)
def _reset_durable_singletons(tmp_path, monkeypatch):
    """Give each test a fresh SQLite decision store."""
    db_path = tmp_path / "decisions.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    from app.decision_store import reset_decision_store
    from app.policy_bundle import clear_policy_bundle
    from app.probe_cache import clear_probe_cache
    from app.settings import clear_settings_cache

    clear_settings_cache()
    reset_decision_store(None)
    clear_policy_bundle()
    clear_probe_cache()
    yield
    reset_decision_store(None)
    clear_policy_bundle()
    clear_probe_cache()
    clear_settings_cache()
