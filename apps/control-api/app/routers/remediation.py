"""RemediationProposal closed-loop API (GitOps; no direct prod mutation)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.decision_store import StoreUnavailableError, get_decision_store
from app.identity_service import (
    AuthenticationError,
    AuthorizationError,
    resolve_approver_identity,
    resolve_request_tenant,
)
from app.remediation_service import (
    RemediationError,
    create_from_drift,
    evaluate_policy,
    mark_applied,
    prepare_pr_draft,
    proposal_to_dict,
    resolve_proposal,
    verify_runtime,
)
from app.settings import get_settings

router = APIRouter(tags=["remediation"])

_STORE_UNAVAILABLE_DETAIL = {"error": "authoritative store unavailable"}


class CreateRemediationRequest(BaseModel):
    action_index: int | None = None
    action_kind: str | None = None
    environment: str = "production"
    tenant_id: str = ""


class ResolveRemediationRequest(BaseModel):
    reviewer: str = ""
    comment: str = ""


class PreparePrRequest(BaseModel):
    pr_url: str = ""


class MarkAppliedRequest(BaseModel):
    pr_url: str = ""


class RemediationProposalResponse(BaseModel):
    proposal_id: str
    tenant_id: str
    status: str
    source: str
    remediation_kind: str
    drift_snapshot: dict[str, Any] = Field(default_factory=dict)
    selected_action: dict[str, Any] = Field(default_factory=dict)
    decision_id: str | None = None
    approval_id: str | None = None
    policy_verdict: str | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    pr_url: str | None = None
    applied_at: str | None = None
    verification_snapshot: dict[str, Any] | None = None
    failure_reason: str | None = None
    created_at: str
    updated_at: str
    terminal: bool = False


class RemediationPageMeta(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int
    has_more: bool


class RemediationListResponse(BaseModel):
    proposals: list[RemediationProposalResponse]
    count: int
    total: int | None = None
    has_more: bool | None = None
    page: RemediationPageMeta | None = None


def _store_unavailable(exc: StoreUnavailableError) -> HTTPException:
    return HTTPException(status_code=503, detail=_STORE_UNAVAILABLE_DETAIL)


def _tenant_scope(request: Request, body_tenant: str = "") -> str | None:
    if not get_settings().tenant_isolation:
        return body_tenant.strip() or None
    try:
        tenant = resolve_request_tenant(dict(request.headers))
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401, detail={"error": str(exc)}
        ) from exc
    if not tenant:
        # Body tenant is ignored when TENANT_JWT_ONLY is on (resolve already JWT-only).
        tenant = body_tenant.strip()
    if not tenant:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "tenant required",
                "hint": (
                    "set JWT tenant/team claim "
                    "(or x-ai-tenant when TENANT_JWT_ONLY=false)"
                ),
            },
        )
    return tenant


def _to_response(payload: dict[str, Any]) -> RemediationProposalResponse:
    return RemediationProposalResponse.model_validate(payload)


def _resolve_reviewer(request: Request, payload: ResolveRemediationRequest) -> str:
    try:
        return resolve_approver_identity(
            dict(request.headers),
            body_reviewer=payload.reviewer,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": str(exc)},
        ) from exc
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=403,
            detail={"error": str(exc)},
        ) from exc


@router.post(
    "/remediation/proposals",
    response_model=RemediationProposalResponse,
)
def create_proposal(
    request: Request,
    payload: CreateRemediationRequest | None = None,
) -> RemediationProposalResponse:
    body = payload or CreateRemediationRequest()
    tenant = _tenant_scope(request, body.tenant_id) or body.tenant_id or "platform"
    try:
        record = create_from_drift(
            tenant_id=tenant,
            action_index=body.action_index,
            action_kind=body.action_kind,
            environment=body.environment,
        )
    except RemediationError as exc:
        raise HTTPException(
            status_code=400, detail={"error": str(exc)}
        ) from exc
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return _to_response(proposal_to_dict(record))


@router.get(
    "/remediation/proposals",
    response_model=RemediationListResponse,
)
def list_proposals(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> RemediationListResponse:
    tenant = _tenant_scope(request)
    try:
        page = get_decision_store().list_remediation_proposals(
            status=status,
            limit=limit,
            offset=offset,
            tenant_id=tenant,
        )
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    items = [_to_response(proposal_to_dict(item)) for item in page.items]
    return RemediationListResponse(
        proposals=items,
        count=len(items),
        total=page.total,
        has_more=page.has_more,
        page=RemediationPageMeta(
            limit=page.limit,
            offset=page.offset,
            returned=len(items),
            total=page.total,
            has_more=page.has_more,
        ),
    )


@router.get(
    "/remediation/proposals/{proposal_id}",
    response_model=RemediationProposalResponse,
)
def get_proposal(
    proposal_id: str,
    request: Request,
) -> RemediationProposalResponse:
    tenant = _tenant_scope(request)
    try:
        record = get_decision_store().get_remediation_proposal(
            proposal_id, tenant_id=tenant
        )
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    if record is None:
        raise HTTPException(
            status_code=404, detail={"error": "remediation proposal not found"}
        )
    return _to_response(proposal_to_dict(record))


@router.post(
    "/remediation/proposals/{proposal_id}/evaluate-policy",
    response_model=RemediationProposalResponse,
)
def evaluate_proposal_policy(
    proposal_id: str,
    request: Request,
    environment: str = Query(default="production"),
) -> RemediationProposalResponse:
    tenant = _tenant_scope(request)
    try:
        record = evaluate_policy(
            proposal_id,
            tenant_id=tenant,
            environment=environment,
            team=tenant,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "remediation proposal not found"}
        ) from exc
    except RemediationError as exc:
        raise HTTPException(
            status_code=409, detail={"error": str(exc)}
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail={"error": str(exc)}
        ) from exc
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return _to_response(proposal_to_dict(record))


@router.post(
    "/remediation/proposals/{proposal_id}/approve",
    response_model=RemediationProposalResponse,
)
def approve_proposal(
    proposal_id: str,
    request: Request,
    payload: ResolveRemediationRequest | None = None,
) -> RemediationProposalResponse:
    body = payload or ResolveRemediationRequest()
    tenant = _tenant_scope(request)
    reviewer = _resolve_reviewer(request, body)
    try:
        record = resolve_proposal(
            proposal_id,
            approved=True,
            reviewer=reviewer,
            comment=body.comment,
            tenant_id=tenant,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "remediation proposal not found"}
        ) from exc
    except RemediationError as exc:
        raise HTTPException(
            status_code=409, detail={"error": str(exc)}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail={"error": str(exc)}
        ) from exc
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return _to_response(proposal_to_dict(record))


@router.post(
    "/remediation/proposals/{proposal_id}/reject",
    response_model=RemediationProposalResponse,
)
def reject_proposal(
    proposal_id: str,
    request: Request,
    payload: ResolveRemediationRequest | None = None,
) -> RemediationProposalResponse:
    body = payload or ResolveRemediationRequest()
    tenant = _tenant_scope(request)
    reviewer = _resolve_reviewer(request, body)
    try:
        record = resolve_proposal(
            proposal_id,
            approved=False,
            reviewer=reviewer,
            comment=body.comment,
            tenant_id=tenant,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "remediation proposal not found"}
        ) from exc
    except RemediationError as exc:
        raise HTTPException(
            status_code=409, detail={"error": str(exc)}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail={"error": str(exc)}
        ) from exc
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return _to_response(proposal_to_dict(record))


@router.post(
    "/remediation/proposals/{proposal_id}/prepare-pr",
    response_model=RemediationProposalResponse,
)
def prepare_proposal_pr(
    proposal_id: str,
    request: Request,
    payload: PreparePrRequest | None = None,
) -> RemediationProposalResponse:
    body = payload or PreparePrRequest()
    tenant = _tenant_scope(request)
    try:
        record = prepare_pr_draft(
            proposal_id,
            tenant_id=tenant,
            pr_url=body.pr_url or None,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "remediation proposal not found"}
        ) from exc
    except RemediationError as exc:
        raise HTTPException(
            status_code=409, detail={"error": str(exc)}
        ) from exc
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return _to_response(proposal_to_dict(record))


@router.post(
    "/remediation/proposals/{proposal_id}/mark-applied",
    response_model=RemediationProposalResponse,
)
def mark_proposal_applied(
    proposal_id: str,
    request: Request,
    payload: MarkAppliedRequest | None = None,
) -> RemediationProposalResponse:
    body = payload or MarkAppliedRequest()
    tenant = _tenant_scope(request)
    try:
        record = mark_applied(
            proposal_id,
            tenant_id=tenant,
            pr_url=body.pr_url or None,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "remediation proposal not found"}
        ) from exc
    except RemediationError as exc:
        raise HTTPException(
            status_code=409, detail={"error": str(exc)}
        ) from exc
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return _to_response(proposal_to_dict(record))


@router.post(
    "/remediation/proposals/{proposal_id}/verify",
    response_model=RemediationProposalResponse,
)
def verify_proposal(
    proposal_id: str,
    request: Request,
) -> RemediationProposalResponse:
    tenant = _tenant_scope(request)
    try:
        record = verify_runtime(proposal_id, tenant_id=tenant)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "remediation proposal not found"}
        ) from exc
    except RemediationError as exc:
        raise HTTPException(
            status_code=409, detail={"error": str(exc)}
        ) from exc
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return _to_response(proposal_to_dict(record))
