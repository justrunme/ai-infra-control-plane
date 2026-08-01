"""Policy bundle lifecycle: validate, simulate, activate, rollback."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.authz import require_roles
from app.policy_lifecycle import get_policy_lifecycle
from app.policy_source import PolicySource

router = APIRouter(prefix="/governance/policy-bundles", tags=["policy-bundles"])


class PolicySourceRequest(BaseModel):
    type: str = "filesystem"
    path: str = ""
    reference: str = ""
    digest: str = ""
    verify_signature: bool = False


class PolicyBundleInfo(BaseModel):
    bundle_id: str
    content_digest: str
    git_revision: str
    loaded_at: str
    validation_status: str
    error: str | None = None
    role: str = "candidate"  # active | previous | candidate


class ValidateResponse(BaseModel):
    bundle: PolicyBundleInfo


class ImpactResponse(BaseModel):
    bundle_id: str
    content_digest: str
    evaluated_decisions: int
    unchanged: int
    allow_to_block: int
    allow_to_approval: int
    block_to_allow: int
    approval_to_allow: int
    approval_to_block: int
    other_changes: int
    sample_changes: list[dict] = Field(default_factory=list)


def _info(bundle, *, role: str) -> PolicyBundleInfo:
    return PolicyBundleInfo(
        bundle_id=bundle.bundle_id,
        content_digest=bundle.content_digest,
        git_revision=bundle.git_revision,
        loaded_at=bundle.loaded_at,
        validation_status=bundle.validation_status,
        error=bundle.error,
        role=role,
    )


@router.get("", response_model=list[PolicyBundleInfo])
def list_bundles(request: Request) -> list[PolicyBundleInfo]:
    require_roles(request, "platform-admin", "auditor", "viewer")
    life = get_policy_lifecycle()
    items = [_info(life.active(), role="active")]
    previous = life.previous()
    if previous is not None:
        items.append(_info(previous, role="previous"))
    for candidate in life.list_candidates():
        if candidate.bundle_id in {item.bundle_id for item in items}:
            continue
        items.append(_info(candidate, role="candidate"))
    return items


@router.post("/validate", response_model=ValidateResponse)
def validate_bundle(
    request: Request, payload: PolicySourceRequest
) -> ValidateResponse:
    require_roles(request, "platform-admin")
    life = get_policy_lifecycle()
    source = PolicySource(
        type=payload.type,
        path=payload.path,
        reference=payload.reference,
        digest=payload.digest,
        verify_signature=payload.verify_signature,
    )
    try:
        if source.type in {"", "filesystem"} and source.path:
            bundle = life.validate_from_path(Path(source.path).expanduser())
        else:
            bundle = life.validate_from_source(source)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
    if bundle.validation_status != "ok":
        raise HTTPException(
            status_code=422,
            detail={
                "error": bundle.error or "validation failed",
                "bundle_id": bundle.bundle_id,
            },
        )
    return ValidateResponse(bundle=_info(bundle, role="candidate"))


@router.post("/{bundle_id}/simulate", response_model=ImpactResponse)
def simulate_bundle(
    bundle_id: str,
    request: Request,
    limit: int = Query(default=200, ge=1, le=5000),
) -> ImpactResponse:
    require_roles(request, "platform-admin")
    life = get_policy_lifecycle()
    try:
        impact = life.simulate(bundle_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail={"error": str(exc)}) from exc
    return ImpactResponse(**impact.to_dict())


@router.get("/{bundle_id}/impact", response_model=ImpactResponse)
def get_impact(bundle_id: str, request: Request) -> ImpactResponse:
    require_roles(request, "platform-admin", "auditor", "viewer")
    life = get_policy_lifecycle()
    impact = life.impact(bundle_id)
    if impact is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "no simulation impact cached; run simulate first"},
        )
    return ImpactResponse(**impact.to_dict())


@router.post("/{bundle_id}/activate", response_model=PolicyBundleInfo)
def activate_bundle(bundle_id: str, request: Request) -> PolicyBundleInfo:
    require_roles(request, "platform-admin")
    life = get_policy_lifecycle()
    try:
        bundle = life.activate(bundle_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    return _info(bundle, role="active")


@router.post("/rollback", response_model=PolicyBundleInfo)
def rollback_bundle(request: Request) -> PolicyBundleInfo:
    require_roles(request, "platform-admin")
    life = get_policy_lifecycle()
    try:
        bundle = life.rollback()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    return _info(bundle, role="active")
