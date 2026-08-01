"""Durable approval lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.decision_store import StoreUnavailableError, get_decision_store
from app.durable_governance import decision_to_dict

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


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalResponse]
    count: int


class ResolveApprovalRequest(BaseModel):
    reviewer: str = Field(min_length=1)
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
    )


def _store_unavailable(exc: StoreUnavailableError) -> HTTPException:
    return HTTPException(status_code=503, detail=_STORE_UNAVAILABLE_DETAIL)


@router.get("/approvals", response_model=ApprovalListResponse)
def list_approvals(status: str = "pending") -> ApprovalListResponse:
    try:
        store = get_decision_store()
        items = [_to_response(item) for item in store.list_approvals(status=status)]
    except StoreUnavailableError as exc:
        raise _store_unavailable(exc) from exc
    return ApprovalListResponse(approvals=items, count=len(items))


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
) -> ApprovalResponse:
    try:
        store = get_decision_store()
        record = store.resolve_approval(
            approval_id,
            status="approved",
            reviewer=payload.reviewer,
            comment=payload.comment,
        )
        store.append_audit_meta(
            decision_id=record.decision_id,
            event_type="approval_approved",
            actor=payload.reviewer,
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
def reject_request(approval_id: str, payload: ResolveApprovalRequest) -> ApprovalResponse:
    try:
        store = get_decision_store()
        record = store.resolve_approval(
            approval_id,
            status="rejected",
            reviewer=payload.reviewer,
            comment=payload.comment,
        )
        store.append_audit_meta(
            decision_id=record.decision_id,
            event_type="approval_rejected",
            actor=payload.reviewer,
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
