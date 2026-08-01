"""Tests for SQLite DecisionStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.decision_store import (
    DecisionStore,
    reset_decision_store,
    sqlite_path_from_url,
)
from app.settings import clear_settings_cache


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DecisionStore:
    db_path = tmp_path / "nested" / "decisions.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    reset_decision_store(None)
    instance = DecisionStore.from_env()
    yield instance
    instance.close()
    reset_decision_store(None)
    clear_settings_cache()


def test_sqlite_path_from_url() -> None:
    assert sqlite_path_from_url("sqlite:///:memory:") == ":memory:"
    assert sqlite_path_from_url("sqlite:///./data/control-plane.db") == (
        "./data/control-plane.db"
    )
    assert sqlite_path_from_url("sqlite:////tmp/control.db") == "/tmp/control.db"


def test_create_and_get_decision(store: DecisionStore) -> None:
    decision_id = store.create_decision(
        final_verdict="allow",
        request_id="req-1",
        policy_bundle_id="bundle-1",
        policy_digest="digest-1",
        team="platform",
        environment="development",
        model="llama3.1:8b",
        subject="alice",
        reasons=["ok"],
        stages={"quota": {"decision": "allow"}},
        request={"model": "llama3.1:8b"},
    )
    record = store.get_decision(decision_id)
    assert record is not None
    assert record.final_verdict == "allow"
    assert record.team == "platform"
    assert record.reasons == ["ok"]
    assert record.stages["quota"]["decision"] == "allow"
    assert store.get_decision("missing") is None


def test_create_approval_and_list_pending(store: DecisionStore) -> None:
    decision_id = store.create_decision(final_verdict="approval_required")
    approval_id = store.create_approval(decision_id, ttl_seconds=3600)
    approval = store.get_approval(approval_id)
    assert approval is not None
    assert approval.status == "pending"
    assert approval.decision_id == decision_id

    pending = store.list_approvals(status="pending")
    assert len(pending) == 1
    assert pending[0].approval_id == approval_id


def test_parent_dirs_created_for_sqlite(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "a" / "b" / "store.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    store = DecisionStore.from_env()
    try:
        assert db_path.parent.is_dir()
        store.create_decision(final_verdict="allow")
        assert db_path.is_file()
    finally:
        store.close()
        clear_settings_cache()
