"""Durable agent/tool capability contract API."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.capability_service import (
    contract_to_dict,
    get_active_capabilities,
    sync_from_filesystem,
)
from app.decision_store import StoreUnavailableError, get_decision_store
from app.identity_service import AuthenticationError, AuthorizationError
from app.rbac import require_any_role

router = APIRouter(tags=["capabilities"])


class CapabilityContractResponse(BaseModel):
    contract_id: str
    kind: str
    name: str
    tenant_id: str
    status: str
    version: str
    content_digest: str
    capabilities: dict[str, Any] = Field(default_factory=dict)
    source: str
    created_at: str
    updated_at: str
    activated_at: str | None = None


class CapabilityPageMeta(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int
    has_more: bool


class CapabilityListResponse(BaseModel):
    contracts: list[CapabilityContractResponse]
    count: int
    total: int | None = None
    has_more: bool | None = None
    page: CapabilityPageMeta | None = None


class SyncCapabilitiesRequest(BaseModel):
    tenant_id: str = "platform"
    activate: bool = False


class SyncCapabilitiesResponse(BaseModel):
    synced: int
    contracts: list[CapabilityContractResponse]


def _require_platform_admin(request: Request) -> None:
    try:
        require_any_role(dict(request.headers), "platform-admin")
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401, detail={"error": str(exc)}
        ) from exc
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=403, detail={"error": str(exc)}
        ) from exc


def _to_response(payload: dict[str, Any]) -> CapabilityContractResponse:
    return CapabilityContractResponse.model_validate(payload)


@router.post(
    "/registry/capabilities/sync",
    response_model=SyncCapabilitiesResponse,
)
def sync_capabilities(
    request: Request,
    payload: SyncCapabilitiesRequest | None = None,
) -> SyncCapabilitiesResponse:
    _require_platform_admin(request)
    body = payload or SyncCapabilitiesRequest()
    try:
        records = sync_from_filesystem(
            tenant_id=body.tenant_id or "platform",
            activate=body.activate,
        )
    except StoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "authoritative store unavailable"},
        ) from exc
    items = [_to_response(contract_to_dict(item)) for item in records]
    return SyncCapabilitiesResponse(synced=len(items), contracts=items)


@router.get(
    "/registry/capabilities",
    response_model=CapabilityListResponse,
)
def list_capabilities(
    kind: Literal["agent", "tool"] | None = Query(default=None),
    status: str | None = Query(default=None),
    name: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> CapabilityListResponse:
    try:
        page = get_decision_store().list_capability_contracts(
            kind=kind,
            status=status,
            name=name,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )
    except StoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "authoritative store unavailable"},
        ) from exc
    items = [_to_response(contract_to_dict(item)) for item in page.items]
    return CapabilityListResponse(
        contracts=items,
        count=len(items),
        total=page.total,
        has_more=page.has_more,
        page=CapabilityPageMeta(
            limit=page.limit,
            offset=page.offset,
            returned=len(items),
            total=page.total,
            has_more=page.has_more,
        ),
    )


@router.get(
    "/registry/capabilities/active/{kind}",
    response_model=list[CapabilityContractResponse],
)
def list_active_capabilities(
    kind: Literal["agent", "tool"],
    tenant_id: str | None = Query(default=None),
) -> list[CapabilityContractResponse]:
    try:
        records = get_active_capabilities(kind, tenant_id=tenant_id)
    except StoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "authoritative store unavailable"},
        ) from exc
    return [_to_response(contract_to_dict(item)) for item in records]


@router.get(
    "/registry/capabilities/{contract_id}",
    response_model=CapabilityContractResponse,
)
def get_capability(contract_id: str) -> CapabilityContractResponse:
    try:
        record = get_decision_store().get_capability_contract(contract_id)
    except StoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "authoritative store unavailable"},
        ) from exc
    if record is None:
        raise HTTPException(
            status_code=404, detail={"error": "capability contract not found"}
        )
    return _to_response(contract_to_dict(record))


@router.post(
    "/registry/capabilities/{contract_id}/activate",
    response_model=CapabilityContractResponse,
)
def activate_capability(
    contract_id: str, request: Request
) -> CapabilityContractResponse:
    _require_platform_admin(request)
    try:
        record = get_decision_store().set_capability_contract_status(
            contract_id, "active"
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "capability contract not found"}
        ) from exc
    except StoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "authoritative store unavailable"},
        ) from exc
    return _to_response(contract_to_dict(record))


@router.post(
    "/registry/capabilities/{contract_id}/retire",
    response_model=CapabilityContractResponse,
)
def retire_capability(
    contract_id: str, request: Request
) -> CapabilityContractResponse:
    _require_platform_admin(request)
    try:
        record = get_decision_store().set_capability_contract_status(
            contract_id, "retired"
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "capability contract not found"}
        ) from exc
    except StoreUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "authoritative store unavailable"},
        ) from exc
    return _to_response(contract_to_dict(record))
