"""Durable approval lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.decision_store import StoreUnavailableError, get_decision_store
from app.durable_governance import decision_to_dict
from app.identity_service import (
    AuthenticationError,
    AuthorizationError,
    resolve_approver_identity,
)

router = APIRouter(tags=["approvals"])

_STORE_UNAVAILABLE_DETAIL = {"error": "authoritative store unavailable"}


class ApprovalResponse(BaseModel):
    approval_id: str
    decision_id: str
    status: str
    reviewer: str | None = None
    review_comment: str | None = None
    created_at: str
    expires_at: str
    resolved_at: str | None = None
    used_at: str | None = None


class ApprovalPageMeta(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int
    has_more: bool


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalResponse]
    # Page size for the current response (kept for v1 compatibility).
    count: int
    total: int | None = None
    has_more: bool | None = None
    page: ApprovalPageMeta | None = None


class ResolveApprovalRequest(BaseModel):
    # Demo mode only. When OIDC_JWT_VERIFY=true the reviewer comes from the JWT.
    reviewer: str = ""
    comment: str = ""


class PolicyBundleStatus(BaseModel):
    bundle_id: str
    git_revision: str
    content_digest: str
    loaded_at: str
    validation_status: str
    error: str | None = None


def _to_response(record) -> ApprovalResponse:
    return ApprovalResponse(
        approval_id=record.approval_id,
        decision_id=record.decision_id,
        status=record.status,
        reviewer=record.reviewer,
        review_comment=record.review_comment,
        created_at=record.created_at,
        expires_at=record.expires_at,
        resolved_at=record.resolved_at,
        used_at=record.used_at,
    )


def _store_unavailable(exc: StoreUnavailableError) -> HTTPException:
    return HTTPException(status_code=503, detail=_STORE_UNAVAILABLE_DETAIL)


def _resolve_reviewer(request: Request, payload: ResolveApprovalRequest) -> str:
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


@router.get("/approvals", response_model=ApprovalListResponse)
def list_approvals(
    status: str = "pending",
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ApprovalListResponse:
    try:
        store = get_decision_store()
        page = store.list_approvals(status=status, limit=limit, offset=offset)
        items = [_to_response(item) for item in page.items]
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return ApprovalListResponse(
        approvals=items,
        count=len(items),
        total=page.total,
        has_more=page.has_more,
        page=ApprovalPageMeta(
            limit=page.limit,
            offset=page.offset,
            returned=len(items),
            total=page.total,
            has_more=page.has_more,
        ),
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
def get_approval(approval_id: str) -> ApprovalResponse:
    try:
        store = get_decision_store()
        record = store.get_approval(approval_id)
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    if record is None:
        raise HTTPException(status_code=404, detail={"error": "approval not found"})
    return _to_response(record)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
def approve_request(
    approval_id: str,
    payload: ResolveApprovalRequest,
    request: Request,
) -> ApprovalResponse:
    reviewer = _resolve_reviewer(request, payload)
    try:
        store = get_decision_store()
        record = store.resolve_approval(
            approval_id,
            status="approved",
            reviewer=reviewer,
            comment=payload.comment,
        )
        store.append_audit_meta(
            decision_id=record.decision_id,
            event_type="approval_approved",
            actor=reviewer,
            payload={"approval_id": approval_id, "comment": payload.comment},
        )
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    return _to_response(record)


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
def reject_request(
    approval_id: str,
    payload: ResolveApprovalRequest,
    request: Request,
) -> ApprovalResponse:
    reviewer = _resolve_reviewer(request, payload)
    try:
        store = get_decision_store()
        record = store.resolve_approval(
            approval_id,
            status="rejected",
            reviewer=reviewer,
            comment=payload.comment,
        )
        store.append_audit_meta(
            decision_id=record.decision_id,
            event_type="approval_rejected",
            actor=reviewer,
            payload={"approval_id": approval_id, "comment": payload.comment},
        )
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    return _to_response(record)


@router.get("/governance/decisions/{decision_id}")
def get_decision(decision_id: str) -> dict:
    try:
        return decision_to_dict(decision_id)
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "decision not found"},
        ) from exc


@router.get("/governance/policy-bundle", response_model=PolicyBundleStatus)
def policy_bundle_status() -> PolicyBundleStatus:
    from app.policy_bundle import get_policy_bundle

    bundle = get_policy_bundle()
    return PolicyBundleStatus(
        bundle_id=bundle.bundle_id,
        git_revision=bundle.git_revision,
        content_digest=bundle.content_digest,
        loaded_at=bundle.loaded_at,
        validation_status=bundle.validation_status,
        error=bundle.error,
    )


@router.post("/governance/policy-bundle/reload", response_model=PolicyBundleStatus)
def policy_bundle_reload() -> PolicyBundleStatus:
    from app.policy_bundle import reload_policy_bundle

    bundle = reload_policy_bundle()
    return PolicyBundleStatus(
        bundle_id=bundle.bundle_id,
        git_revision=bundle.git_revision,
        content_digest=bundle.content_digest,
        loaded_at=bundle.loaded_at,
        validation_status=bundle.validation_status,
        error=bundle.error,
    )
