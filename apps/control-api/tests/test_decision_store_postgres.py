"""Optional Postgres backend tests (skipped without Postgres URL)."""

from __future__ import annotations

import os

import pytest

from app.decision_store import DecisionStore

POSTGRES_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", ""),
)


@pytest.mark.skipif(
    not POSTGRES_URL.startswith(("postgres://", "postgresql://")),
    reason="Postgres TEST_DATABASE_URL/DATABASE_URL not configured",
)
def test_postgres_decision_and_approval_roundtrip() -> None:
    store = DecisionStore(POSTGRES_URL)
    try:
        decision_id = store.create_decision(
            final_verdict="approval_required",
            policy_bundle_id="pg-bundle",
            team="platform",
            model="llama3.1:8b",
        )
        approval_id = store.create_approval(decision_id, ttl_seconds=600)
        approval = store.resolve_approval(
            approval_id,
            status="approved",
            reviewer="ci",
            comment="postgres path",
        )
        assert store.get_decision(decision_id) is not None
        assert approval.status == "approved"
    finally:
        store.close()
