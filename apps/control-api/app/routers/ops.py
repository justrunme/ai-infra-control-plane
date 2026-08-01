"""Audit, secrets, FinOps, and incident runbook endpoints."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.audit_service import AUDIT_STORE, AuditEvent
from app.audit_sink import AUDIT_SINK, AuditSinkStatus
from app.decision_store import StoreUnavailableError, get_decision_store
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
from app.settings import get_settings
from app.topology_builder import get_platform_topology

router = APIRouter(tags=["ops"])


class RetentionPurgeResponse(BaseModel):
    retention_days: int
    cutoff: str
    dry_run: bool
    expired_approvals: int
    deleted_audit_meta: int
    deleted_approvals: int
    deleted_decisions: int


class RetentionStatusResponse(BaseModel):
    retention_days: int = Field(
        description="Configured RETENTION_DAYS (0 disables age-based deletes)"
    )
    approval_ttl_seconds: int


@router.get("/ops/retention", response_model=RetentionStatusResponse)
def retention_status() -> RetentionStatusResponse:
    settings = get_settings()
    return RetentionStatusResponse(
        retention_days=settings.retention_days,
        approval_ttl_seconds=settings.approval_ttl_seconds,
    )


@router.post("/ops/retention/purge", response_model=RetentionPurgeResponse)
def retention_purge(
    dry_run: bool = Query(
        default=True,
        description="When true, only report rows that would be deleted",
    ),
    retention_days: int | None = Query(
        default=None,
        ge=0,
        le=3650,
        description="Override RETENTION_DAYS for this call",
    ),
    limit: int = Query(default=5000, ge=1, le=50000),
) -> RetentionPurgeResponse:
    settings = get_settings()
    days = settings.retention_days if retention_days is None else retention_days
    try:
        result = get_decision_store().purge_retained(
            retention_days=days,
            dry_run=dry_run,
            limit=limit,
        )
    except StoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "authoritative store unavailable"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
    return RetentionPurgeResponse(
        retention_days=result.retention_days,
        cutoff=result.cutoff,
        dry_run=result.dry_run,
        expired_approvals=result.expired_approvals,
        deleted_audit_meta=result.deleted_audit_meta,
        deleted_approvals=result.deleted_approvals,
        deleted_decisions=result.deleted_decisions,
    )


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
