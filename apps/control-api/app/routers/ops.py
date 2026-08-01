"""Audit, secrets, FinOps, and incident runbook endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.audit_service import AUDIT_STORE, AuditEvent
from app.audit_sink import AUDIT_SINK, AuditSinkStatus
from app.finops_service import (
    FinOpsRecommendationsResponse,
    build_finops_recommendations,
)
from app.fleet_service import build_fleet_clusters
from app.incident_runbook_service import (
    IncidentRunbookResponse,
    build_incident_runbook,
    get_alert_definition,
    list_supported_alerts,
)
from app.probes import get_inventory_drift
from app.secrets_service import SecretsStatusResponse, build_secrets_status
from app.topology_builder import get_platform_topology

router = APIRouter(tags=["ops"])


@router.get("/audit/events", response_model=list[AuditEvent])
def audit_events(
    limit: int = Query(default=50, ge=1, le=500),
    team: str | None = None,
    subject: str | None = None,
    verdict: str | None = None,
) -> list[AuditEvent]:
    return AUDIT_STORE.list_events(
        limit=limit,
        team=team,
        subject=subject,
        verdict=verdict,
    )


@router.get("/audit/status", response_model=AuditSinkStatus)
def audit_status() -> AuditSinkStatus:
    return AUDIT_SINK.status()


@router.get("/secrets/status", response_model=SecretsStatusResponse)
def secrets_status() -> SecretsStatusResponse:
    return build_secrets_status()


@router.get(
    "/finops/recommendations",
    response_model=FinOpsRecommendationsResponse,
)
def finops_recommendations(
    team: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> FinOpsRecommendationsResponse:
    return build_finops_recommendations(
        team=team, severity=severity, limit=limit
    )


@router.get("/incidents/alerts")
def incident_alerts() -> dict[str, list[str]]:
    return {"alerts": list_supported_alerts()}


@router.get("/incidents/runbook", response_model=IncidentRunbookResponse)
def incident_runbook(
    alert: str = Query(
        ..., description="Prometheus alert name from the SLO catalog"
    ),
    team: str | None = None,
    model: str | None = None,
) -> IncidentRunbookResponse:
    if get_alert_definition(alert) is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unsupported alert",
                "alert": alert,
                "supported_alerts": list_supported_alerts(),
            },
        )

    return build_incident_runbook(
        alert,
        team=team,
        model=model,
        drift=get_inventory_drift(),
        topology=get_platform_topology(),
        audit_events=AUDIT_STORE.list_events(limit=100),
        fleet=build_fleet_clusters(),
        finops=build_finops_recommendations(limit=10),
    )
