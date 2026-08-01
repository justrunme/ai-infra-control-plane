"""Liveness and readiness health endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app.models import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok", checked_at=datetime.now(UTC).isoformat())


@router.get("/healthz", response_model=HealthStatus)
def healthz() -> HealthStatus:
    return health()
