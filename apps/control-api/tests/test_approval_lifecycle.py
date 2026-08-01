"""Tests for approval create / expire / resolve lifecycle on DecisionStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.decision_store import DecisionStore, reset_decision_store
from app.settings import clear_settings_cache


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DecisionStore:
    db_path = tmp_path / "approvals.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    reset_decision_store(None)
    instance = DecisionStore.from_env()
    yield instance
    instance.close()
    reset_decision_store(None)
    clear_settings_cache()


def test_resolve_approval_approved(store: DecisionStore) -> None:
    decision_id = store.create_decision(final_verdict="approval_required")
    approval_id = store.create_approval(decision_id, ttl_seconds=3600)

    resolved = store.resolve_approval(
        approval_id,
        status="approved",
        reviewer="bob",
        comment="looks good",
    )
    assert resolved.status == "approved"
    assert resolved.reviewer == "bob"
    assert resolved.review_comment == "looks good"
    assert resolved.resolved_at

    with pytest.raises(ValueError, match="not pending"):
        store.resolve_approval(
            approval_id, status="rejected", reviewer="carol", comment="late"
        )


def test_expire_stale_and_lazy_expire(store: DecisionStore) -> None:
    decision_id = store.create_decision(final_verdict="approval_required")
    approval_id = store.create_approval(decision_id, ttl_seconds=3600)

    past = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    with store._session() as conn:
        store._execute(
            conn,
            "UPDATE approvals SET expires_at = ? WHERE approval_id = ?",
            (past, approval_id),
        )
        store._commit(conn)

    expired_count = store.expire_stale_approvals()
    assert expired_count == 1
    approval = store.get_approval(approval_id)
    assert approval is not None
    assert approval.status == "expired"

    with pytest.raises(ValueError, match="expired"):
        store.resolve_approval(
            approval_id, status="approved", reviewer="bob", comment=""
        )


def test_lazy_expire_on_get(store: DecisionStore) -> None:
    decision_id = store.create_decision(final_verdict="approval_required")
    approval_id = store.create_approval(decision_id, ttl_seconds=1)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with store._session() as conn:
        store._execute(
            conn,
            "UPDATE approvals SET expires_at = ? WHERE approval_id = ?",
            (past, approval_id),
        )
        store._commit(conn)

    approval = store.get_approval(approval_id)
    assert approval is not None
    assert approval.status == "expired"
