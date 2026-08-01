"""Liveness, readiness, and operator health endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.decision_store import StoreUnavailableError, get_decision_store
from app.models import HealthStatus
from app.policy_lifecycle import get_policy_lifecycle
from app.policy_source import get_policy_failure_mode

router = APIRouter(tags=["health"])


class ReadyStatus(BaseModel):
    status: str = "ready"
    checked_at: str
    store_ok: bool = True
    policy_bundle_ok: bool = True
    policy_digest: str = ""
    policy_fallback: bool = False
    policy_expected_digest: str = ""
    details: list[str] = Field(default_factory=list)


class OperatorHealthStatus(BaseModel):
    status: str
    checked_at: str
    live: bool = True
    ready: bool = True
    store_ok: bool = True
    policy_bundle_ok: bool = True
    backends: dict[str, str] = Field(default_factory=dict)


def _policy_bundle_ready() -> tuple[bool, str, str | None, bool, str]:
    from app.policy_bundle import get_policy_bundle

    bundle = get_policy_bundle()
    status = get_policy_lifecycle().bootstrap_status()
    ok = bundle.validation_status == "ok" and status["error"] is None
    if get_policy_failure_mode() == "fail_closed" and status["error"]:
        ok = False
    if status.get("fallback_active") and get_policy_failure_mode() == "fail_closed":
        ok = False
    error = status.get("error") or bundle.error
    return (
        ok,
        bundle.content_digest,
        error,
        bool(status.get("fallback_active")),
        str(status.get("expected_digest") or ""),
    )


@router.get("/livez", response_model=HealthStatus)
def livez() -> HealthStatus:
    """Process liveness — does not depend on the decision store."""
    return HealthStatus(status="ok", checked_at=datetime.now(UTC).isoformat())


@router.get("/healthz", response_model=HealthStatus)
def healthz() -> HealthStatus:
    """Kubernetes-compatible liveness alias (process alive)."""
    return livez()


@router.get("/readyz", response_model=ReadyStatus)
def readyz() -> ReadyStatus:
    """Readiness: authoritative store ping + valid policy bundle."""
    checked_at = datetime.now(UTC).isoformat()
    details: list[str] = []
    store_ok = False
    try:
        store_ok = get_decision_store().ping()
    except StoreUnavailableError:
        store_ok = False
    if not store_ok:
        details.append("authoritative store unavailable")

    policy_ok, digest, policy_error, fallback, expected = _policy_bundle_ready()
    if not policy_ok:
        details.append(policy_error or "policy bundle invalid")
    if fallback:
        details.append("policy source using last-known-good fallback")

    if not store_ok or not policy_ok:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "not ready",
                "store_ok": store_ok,
                "policy_bundle_ok": policy_ok,
                "policy_fallback": fallback,
                "policy_expected_digest": expected,
                "details": details,
            },
        )

    return ReadyStatus(
        status="ready",
        checked_at=checked_at,
        store_ok=True,
        policy_bundle_ok=True,
        policy_digest=digest,
        policy_fallback=fallback,
        policy_expected_digest=expected,
    )


@router.get("/health", response_model=OperatorHealthStatus)
def health() -> OperatorHealthStatus:
    """Operator-facing status including store readiness (always 200 when live)."""
    checked_at = datetime.now(UTC).isoformat()
    store_ok = False
    try:
        store_ok = get_decision_store().ping()
    except StoreUnavailableError:
        store_ok = False
    policy_ok, _, _, _, _ = _policy_bundle_ready()
    ready = store_ok and policy_ok
    return OperatorHealthStatus(
        status="ok" if ready else "degraded",
        checked_at=checked_at,
        live=True,
        ready=ready,
        store_ok=store_ok,
        policy_bundle_ok=policy_ok,
    )
