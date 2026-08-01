"""Prove decision/approval records survive process restart (new store handle)."""

from __future__ import annotations

from pathlib import Path

from app.decision_store import DecisionStore


def test_decisions_survive_store_reopen(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'restart.db'}"
    store = DecisionStore(db_url)
    decision_id = store.create_decision(
        final_verdict="approval_required",
        policy_bundle_id="bundle-abc",
        policy_digest="digest-abc",
        team="platform",
        model="llama3.1:8b",
    )
    approval_id = store.create_approval(decision_id, ttl_seconds=3600)
    store.close()

    reopened = DecisionStore(db_url)
    decision = reopened.get_decision(decision_id)
    approval = reopened.get_approval(approval_id)
    assert decision is not None
    assert decision.final_verdict == "approval_required"
    assert decision.policy_bundle_id == "bundle-abc"
    assert approval is not None
    assert approval.status == "pending"
    reopened.close()
