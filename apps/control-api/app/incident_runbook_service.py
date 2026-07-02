"""Generate incident context from SLO alerts and live control-plane signals."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.audit_service import AuditEvent
from app.drift_service import DriftStatus
from app.finops_service import FinOpsRecommendationsResponse
from app.fleet_service import FleetClustersResponse
from app.topology import TopologyStatus

ALERT_CATALOG: dict[str, dict[str, Any]] = {
    "GatewayLatencyP95High": {
        "severity": "warning",
        "summary": "Gateway chat p95 latency exceeds 2.5s SLO",
        "runbook_actions": [
            "Check Ollama and vLLM latency probes on the control plane dashboard.",
            "Review recent canary promotions and fallback metrics in Grafana.",
            "Inspect fleet clusters with degraded backend health.",
        ],
    },
    "GatewayFallbackRateHigh": {
        "severity": "warning",
        "summary": "Gateway fallback rate exceeds 2% SLO",
        "runbook_actions": [
            "Identify primary models with elevated 5xx or timeout rates.",
            "Validate backend health stores and Redis-shared routing state.",
            "Pause canary traffic until primary backends recover.",
        ],
    },
    "ShadowFailureRateHigh": {
        "severity": "warning",
        "summary": "Shadow traffic failure rate exceeds 5% SLO",
        "runbook_actions": [
            "Compare shadow target health against the primary route.",
            "Review routing decision records for recent shadow errors.",
            "Hold promotion analysis until shadow error budget recovers.",
        ],
    },
    "GovernanceBlockRateHigh": {
        "severity": "info",
        "summary": "Governance block rate exceeds 10% SLO",
        "runbook_actions": [
            "Review recent governance audit blocks by tenant and model.",
            "Validate quota policies and policy packs for unintended denies.",
            "Coordinate with tenant owners if blocks are expected workload shifts.",
        ],
    },
    "InventoryDriftDetected": {
        "severity": "critical",
        "summary": "Model inventory drift detected for more than 15 minutes",
        "runbook_actions": [
            "Compare Helm ConfigMap inventory against live Ollama/vLLM model lists.",
            "Run GitOps reconcile or roll back the last inventory change.",
            "Block new model promotions until drift is cleared.",
        ],
    },
    "ModelAvailabilityLow": {
        "severity": "critical",
        "summary": "Model availability dropped below 99% SLO",
        "runbook_actions": [
            "Check backend probes and model pull/init jobs.",
            "Fail over traffic to healthy replicas or clusters.",
            "Open a change request if inventory or registry entries are stale.",
        ],
    },
}


class IncidentAlert(BaseModel):
    name: str
    severity: str
    summary: str


class RecentGovernanceBlock(BaseModel):
    timestamp: str
    team: str
    model: str
    subject: str
    blocking_stage: str | None = None
    reasons: list[str] = Field(default_factory=list)


class IncidentRunbookResponse(BaseModel):
    incident_id: str
    generated_at: str
    alert: IncidentAlert
    affected_models: list[str] = Field(default_factory=list)
    affected_tenants: list[str] = Field(default_factory=list)
    affected_clusters: list[str] = Field(default_factory=list)
    unhealthy_topology_nodes: list[str] = Field(default_factory=list)
    drift_in_sync: bool = True
    drift_summary: str | None = None
    recent_governance_blocks: list[RecentGovernanceBlock] = Field(default_factory=list)
    finops_actions: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    context_markdown: str = ""


def list_supported_alerts() -> list[str]:
    return sorted(ALERT_CATALOG)


def get_alert_definition(alert_name: str) -> dict[str, Any] | None:
    return ALERT_CATALOG.get(alert_name)


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _recent_blocks(
    events: list[AuditEvent],
    *,
    team: str | None,
    model: str | None,
    limit: int = 10,
) -> list[RecentGovernanceBlock]:
    blocks: list[RecentGovernanceBlock] = []
    for event in reversed(events):
        if event.final_verdict != "block":
            continue
        if team and event.team != team:
            continue
        if model and event.model != model:
            continue
        blocks.append(
            RecentGovernanceBlock(
                timestamp=event.timestamp,
                team=event.team,
                model=event.model,
                subject=event.subject,
                blocking_stage=event.blocking_stage,
                reasons=list(event.reasons),
            )
        )
        if len(blocks) >= limit:
            break
    return blocks


def _affected_models(
    drift: DriftStatus,
    blocks: list[RecentGovernanceBlock],
    model_filter: str | None,
) -> list[str]:
    models: list[str] = []
    for backend in drift.backends:
        models.extend(backend.missing_on_backend)
        models.extend(backend.unexpected_on_backend)
    models.extend(block.model for block in blocks)
    if model_filter:
        models.append(model_filter)
    return _unique_sorted(models)


def _affected_tenants(
    blocks: list[RecentGovernanceBlock], team_filter: str | None
) -> list[str]:
    tenants = [block.team for block in blocks]
    if team_filter:
        tenants.append(team_filter)
    return _unique_sorted(tenants)


def _affected_clusters(fleet: FleetClustersResponse) -> list[str]:
    return sorted(
        cluster.id
        for cluster in fleet.clusters
        if cluster.health in {"degraded", "unreachable"}
    )


def _unhealthy_topology_nodes(topology: TopologyStatus) -> list[str]:
    return sorted(
        node.id for node in topology.nodes if node.health in {"degraded", "unreachable"}
    )


def _finops_actions(
    finops: FinOpsRecommendationsResponse | None,
    *,
    team: str | None,
    model: str | None,
    limit: int = 5,
) -> list[str]:
    if finops is None:
        return []

    actions: list[str] = []
    for recommendation in finops.recommendations:
        if team and recommendation.team != team:
            continue
        if model and recommendation.model != model:
            continue
        actions.extend(recommendation.actions)
        if len(actions) >= limit:
            break
    return actions[:limit]


def _build_recommended_actions(
    alert_name: str,
    *,
    drift: DriftStatus,
    blocks: list[RecentGovernanceBlock],
    unhealthy_nodes: list[str],
    affected_clusters: list[str],
    finops_actions: list[str],
) -> list[str]:
    definition = ALERT_CATALOG[alert_name]
    actions = list(definition.get("runbook_actions", []))

    if not drift.in_sync:
        actions.append(
            f"Resolve inventory drift before closing the incident: {drift.summary}"
        )

    if unhealthy_nodes:
        actions.append(
            "Investigate unhealthy topology nodes: " + ", ".join(unhealthy_nodes)
        )

    if affected_clusters:
        actions.append("Review degraded fleet clusters: " + ", ".join(affected_clusters))

    if blocks:
        top_team = blocks[0].team
        actions.append(
            f"Recent governance blocks involve tenant '{top_team}' — "
            "review quota and policy packs."
        )

    actions.extend(finops_actions)
    return actions


def _render_markdown(
    response: IncidentRunbookResponse,
) -> str:
    lines = [
        f"# Incident {response.incident_id}",
        "",
        f"**Alert:** {response.alert.name} ({response.alert.severity})",
        f"**Summary:** {response.alert.summary}",
        f"**Generated:** {response.generated_at}",
        "",
        "## Affected scope",
        "",
    ]

    if response.affected_models:
        lines.append("- **Models:** " + ", ".join(response.affected_models))
    if response.affected_tenants:
        lines.append("- **Tenants:** " + ", ".join(response.affected_tenants))
    if response.affected_clusters:
        lines.append("- **Clusters:** " + ", ".join(response.affected_clusters))
    if response.unhealthy_topology_nodes:
        lines.append(
            "- **Unhealthy nodes:** " + ", ".join(response.unhealthy_topology_nodes)
        )
    if response.drift_summary:
        lines.append(f"- **Drift:** {response.drift_summary}")

    lines.extend(["", "## Recent governance blocks", ""])
    if response.recent_governance_blocks:
        for block in response.recent_governance_blocks[:5]:
            stage = block.blocking_stage or "unknown"
            lines.append(
                f"- `{block.timestamp}` tenant={block.team} model={block.model} "
                f"stage={stage} subject={block.subject}"
            )
    else:
        lines.append("- No recent governance blocks in the audit window.")

    lines.extend(["", "## Recommended actions", ""])
    for index, action in enumerate(response.recommended_actions, start=1):
        lines.append(f"{index}. {action}")

    return "\n".join(lines) + "\n"


def build_incident_runbook(
    alert_name: str,
    *,
    team: str | None = None,
    model: str | None = None,
    drift: DriftStatus,
    topology: TopologyStatus,
    audit_events: list[AuditEvent],
    fleet: FleetClustersResponse,
    finops: FinOpsRecommendationsResponse | None = None,
) -> IncidentRunbookResponse:
    definition = ALERT_CATALOG.get(alert_name)
    if definition is None:
        raise KeyError(alert_name)

    blocks = _recent_blocks(audit_events, team=team, model=model)
    affected_models = _affected_models(drift, blocks, model)
    affected_tenants = _affected_tenants(blocks, team)
    affected_clusters = _affected_clusters(fleet)
    unhealthy_nodes = _unhealthy_topology_nodes(topology)
    finops_actions = _finops_actions(finops, team=team, model=model)

    response = IncidentRunbookResponse(
        incident_id=str(uuid.uuid4()),
        generated_at=datetime.now(UTC).isoformat(),
        alert=IncidentAlert(
            name=alert_name,
            severity=str(definition["severity"]),
            summary=str(definition["summary"]),
        ),
        affected_models=affected_models,
        affected_tenants=affected_tenants,
        affected_clusters=affected_clusters,
        unhealthy_topology_nodes=unhealthy_nodes,
        drift_in_sync=drift.in_sync,
        drift_summary=drift.summary,
        recent_governance_blocks=blocks,
        finops_actions=finops_actions,
        recommended_actions=_build_recommended_actions(
            alert_name,
            drift=drift,
            blocks=blocks,
            unhealthy_nodes=unhealthy_nodes,
            affected_clusters=affected_clusters,
            finops_actions=finops_actions,
        ),
    )
    response.context_markdown = _render_markdown(response)
    return response
