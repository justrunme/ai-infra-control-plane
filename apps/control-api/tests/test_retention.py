"""Retention purge and foreign-key integrity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.decision_store import DecisionStore, reset_decision_store
from app.settings import clear_settings_cache


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DecisionStore:
    db_path = tmp_path / "retention.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    clear_settings_cache()
    reset_decision_store(None)
    instance = DecisionStore.from_env()
    reset_decision_store(instance)
    yield instance
    reset_decision_store(None)
    instance.close()
    clear_settings_cache()


def test_purge_retained_dry_run_and_delete(store: DecisionStore) -> None:
    old_id = store.create_decision(final_verdict="allow", team="platform")
    store.create_approval(old_id, ttl_seconds=60)
    store.append_audit_meta(
        decision_id=old_id, event_type="decision_recorded", actor="alice"
    )
    keep_id = store.create_decision(final_verdict="allow", team="platform")

    old_ts = (datetime.now(UTC) - timedelta(days=120)).isoformat()
    with store._session() as conn:
        store._execute(
            conn,
            "UPDATE decisions SET created_at = ? WHERE decision_id = ?",
            (old_ts, old_id),
        )
        store._commit(conn)

    preview = store.purge_retained(retention_days=90, dry_run=True, limit=100)
    assert preview.dry_run is True
    assert preview.deleted_decisions == 1
    assert preview.deleted_approvals == 1
    assert preview.deleted_audit_meta == 1
    assert store.get_decision(old_id) is not None

    applied = store.purge_retained(retention_days=90, dry_run=False, limit=100)
    assert applied.dry_run is False
    assert applied.deleted_decisions == 1
    assert store.get_decision(old_id) is None
    assert store.get_decision(keep_id) is not None


def test_sqlite_rejects_orphan_approval(store: DecisionStore) -> None:
    from app.decision_store import StoreUnavailableError

    with pytest.raises(StoreUnavailableError):
        store.create_approval("missing-decision", ttl_seconds=60)


def test_retention_api(store: DecisionStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETENTION_DAYS", "30")
    clear_settings_cache()
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    status = client.get("/ops/retention")
    assert status.status_code == 200
    assert status.json()["retention_days"] == 30

    decision_id = store.create_decision(final_verdict="block", team="secops")
    old_ts = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    with store._session() as conn:
        store._execute(
            conn,
            "UPDATE decisions SET created_at = ? WHERE decision_id = ?",
            (old_ts, decision_id),
        )
        store._commit(conn)

    dry = client.post("/ops/retention/purge?dry_run=true&limit=100")
    assert dry.status_code == 200
    body = dry.json()
    assert body["dry_run"] is True
    assert body["deleted_decisions"] >= 1
    assert store.get_decision(decision_id) is not None

    real = client.post("/ops/retention/purge?dry_run=false&limit=100")
    assert real.status_code == 200
    assert real.json()["deleted_decisions"] >= 1
    assert store.get_decision(decision_id) is None
