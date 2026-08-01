"""Capability-bound execution digests for approval reuse (v2.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.capability_service import resolve_execution_capability_digests
from app.decision_store import DecisionStore, reset_decision_store
from app.durable_governance import approval_grants_allow, persist_evaluation
from app.governance_service import (
    GovernanceEvaluateRequest,
    GovernanceEvaluateResponse,
)
from app.settings import clear_settings_cache


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'cap.db'}")
    clear_settings_cache()
    reset_decision_store(None)
    decision_store = DecisionStore.from_env()
    reset_decision_store(decision_store)
    yield decision_store
    reset_decision_store(None)
    decision_store.close()
    clear_settings_cache()


def _activate_agent(store: DecisionStore, *, name: str, digest: str, tools: list[str]):
    record = store.upsert_capability_contract(
        kind="agent",
        name=name,
        tenant_id="platform",
        version="v1",
        content_digest=digest,
        capabilities={"name": name, "tools": tools},
        status="draft",
    )
    return store.set_capability_contract_status(record.contract_id, "active")


def _activate_tool(store: DecisionStore, *, name: str, digest: str):
    record = store.upsert_capability_contract(
        kind="tool",
        name=name,
        tenant_id="platform",
        version="v1",
        content_digest=digest,
        capabilities={"name": name},
        status="draft",
    )
    return store.set_capability_contract_status(record.contract_id, "active")


def test_resolve_execution_capability_digests(store: DecisionStore) -> None:
    _activate_tool(store, name="search", digest="sha256:tool1")
    _activate_agent(
        store, name="ops-agent", digest="sha256:agent1", tools=["search"]
    )
    agent_digest, tools_digest = resolve_execution_capability_digests(
        agent="ops-agent",
        tenant_id="platform",
        store=store,
    )
    assert agent_digest == "sha256:agent1"
    assert tools_digest.startswith("sha256:")


def test_approval_rejects_when_agent_digest_changes(store: DecisionStore) -> None:
    _activate_tool(store, name="search", digest="sha256:tool1")
    _activate_agent(
        store, name="ops-agent", digest="sha256:agent1", tools=["search"]
    )
    request = GovernanceEvaluateRequest(
        team="platform",
        owner="alice",
        environment="development",
        namespace="ai-dev",
        action="invoke_model",
        model="llama3.1:8b",
        provider="ollama",
        agent="ops-agent",
    )
    result = GovernanceEvaluateResponse(
        final_verdict="approval_required",
        policy_pack="default",
        reasons=["needs approval"],
        flow=["request", "final_verdict"],
        stages={},
        policy_digest="policy-1",
    )
    persisted = persist_evaluation(
        result=result, request=request, request_id="r1", store=store
    )
    assert persisted.approval_id
    assert persisted.agent_capability_digest == "sha256:agent1"
    store.resolve_approval(
        persisted.approval_id,
        status="approved",
        reviewer="bob",
    )
    assert approval_grants_allow(
        persisted.approval_id,
        request,
        policy_digest="policy-1",
        store=store,
    )

    # New decision/approval pinned to agent1; then rotate active agent digest.
    persisted2 = persist_evaluation(
        result=result, request=request, request_id="r2", store=store
    )
    store.resolve_approval(
        persisted2.approval_id,
        status="approved",
        reviewer="bob",
    )
    _activate_agent(
        store, name="ops-agent", digest="sha256:agent2", tools=["search"]
    )
    assert not approval_grants_allow(
        persisted2.approval_id,
        request,
        policy_digest="policy-1",
        store=store,
    )


def test_migration_010_present(store: DecisionStore) -> None:
    assert "010_capability_execution_digests" in store.list_schema_migrations()
