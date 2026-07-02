"""Tests for AI incident runbook generation."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app import main as app_main
from app.audit_service import AuditEvent
from app.drift_service import BackendDrift, DriftStatus
from app.finops_service import FinOpsRecommendation, FinOpsRecommendationsResponse
from app.fleet_service import (
    FleetBackendStatus,
    FleetClustersResponse,
    FleetClusterStatus,
    FleetSummary,
)
from app.incident_runbook_service import build_incident_runbook
from app.topology import TopologyNode, TopologyStatus

client = TestClient(app_main.app)


def _drift(*, in_sync: bool = False) -> DriftStatus:
    return DriftStatus(
        updated_at=datetime.now(UTC).isoformat(),
        in_sync=in_sync,
        summary="ollama inventory drift detected" if not in_sync else "inventory in sync",
        backends=[
            BackendDrift(
                backend="ollama",
                probe_healthy=True,
                desired_models=["llama3.1:8b"],
                actual_models=[],
                missing_on_backend=["llama3.1:8b"] if not in_sync else [],
                unexpected_on_backend=[],
                in_sync=in_sync,
            )
        ],
    )


def _topology(*, ollama_health: str = "healthy") -> TopologyStatus:
    return TopologyStatus(
        updated_at=datetime.now(UTC).isoformat(),
        graph_version="v1",
        nodes=[
            TopologyNode(
                id="ollama",
                label="Ollama",
                kind="inference-backend",
                health=ollama_health,  # type: ignore[arg-type]
            ),
            TopologyNode(
                id="control-api",
                label="Control API",
                kind="api",
                health="healthy",
            ),
        ],
        edges=[],
    )


def _fleet() -> FleetClustersResponse:
    return FleetClustersResponse(
        summary=FleetSummary(
            updated_at=datetime.now(UTC).isoformat(),
            cluster_count=2,
            healthy_clusters=1,
            degraded_clusters=1,
            unreachable_clusters=0,
            primary_cluster="local-demo",
        ),
        clusters=[
            FleetClusterStatus(
                id="eu-prod",
                label="EU Production",
                cloud="hetzner",
                region="eu-central",
                environment="production",
                health="degraded",
                ollama=FleetBackendStatus(healthy=False, latency_ms=0),
                vllm=FleetBackendStatus(healthy=True, latency_ms=0),
            )
        ],
    )


def _audit_block() -> AuditEvent:
    return AuditEvent(
        event_id="evt-1",
        timestamp=datetime.now(UTC).isoformat(),
        subject="bob",
        team="finance",
        owner="bob",
        environment="development",
        namespace="ai-dev",
        model="llama3.1:8b",
        action="invoke_model",
        final_verdict="block",
        blocking_stage="quota",
        reasons=["team finance exceeded requests_per_minute"],
    )


def test_build_incident_runbook_includes_drift_and_blocks() -> None:
    runbook = build_incident_runbook(
        "InventoryDriftDetected",
        drift=_drift(in_sync=False),
        topology=_topology(ollama_health="degraded"),
        audit_events=[_audit_block()],
        fleet=_fleet(),
        finops=FinOpsRecommendationsResponse(
            updated_at=datetime.now(UTC).isoformat(),
            currency="USD",
            recommendation_count=1,
            estimated_monthly_savings_usd=120.0,
            recommendations=[
                FinOpsRecommendation(
                    id="rec-1",
                    category="idle_capacity",
                    severity="medium",
                    team="finance",
                    model="llama3.1:8b",
                    title="Scale down idle replicas",
                    summary="Low utilization detected",
                    estimated_monthly_savings_usd=120.0,
                    actions=["Reduce vLLM replicas from 3 to 2"],
                )
            ],
        ),
    )

    assert runbook.alert.name == "InventoryDriftDetected"
    assert "llama3.1:8b" in runbook.affected_models
    assert "finance" in runbook.affected_tenants
    assert "eu-prod" in runbook.affected_clusters
    assert "ollama" in runbook.unhealthy_topology_nodes
    assert runbook.recent_governance_blocks
    assert runbook.recommended_actions
    assert "# Incident" in runbook.context_markdown


def test_incident_runbook_endpoint_returns_markdown_context() -> None:
    client.post(
        "/governance/evaluate",
        json={
            "team": "finance",
            "owner": "bob",
            "model": "llama3.1:8b",
            "provider": "ollama",
            "requests_last_minute": 30,
            "sensitive_data": True,
        },
    )

    response = client.get(
        "/incidents/runbook",
        params={"alert": "GovernanceBlockRateHigh", "team": "finance"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["alert"]["name"] == "GovernanceBlockRateHigh"
    assert payload["context_markdown"]
    assert payload["recommended_actions"]


def test_incident_runbook_endpoint_rejects_unknown_alert() -> None:
    response = client.get("/incidents/runbook", params={"alert": "NotARealAlert"})

    assert response.status_code == 404
    assert "supported_alerts" in response.json()["detail"]
