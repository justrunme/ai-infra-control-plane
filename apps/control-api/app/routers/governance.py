"""Governance evaluate, inputs, evaluations, and intent endpoints."""

from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request

from app.audit_service import AUDIT_STORE
from app.decision_store import StoreUnavailableError
from app.durable_governance import approval_grants_allow, persist_evaluation
from app.evaluation_service import (
    EVALUATION_STORE,
    EvaluationListResponse,
    EvaluationRecord,
    ResponseEvaluateRequest,
    evaluate_model_response,
)
from app.governance_inputs import (
    GovernanceInputsStatus,
    build_telemetry_stage,
    enrich_governance_request,
    governance_inputs_status,
)
from app.governance_service import (
    GovernanceEvaluateRequest,
    GovernanceEvaluateResponse,
    evaluate_governance_request,
)
from app.identity_service import apply_identity, resolve_workload_identity
from app.intent_service import (
    IntentResolveRequest,
    IntentResolveResponse,
    resolve_intent_plan,
)
from app.metrics_util import (
    GOVERNANCE_DECISIONS_TOTAL,
    inc_governance_eval_errors,
    observe_governance_latency_ms,
)
from app.tool_governance_service import (
    ToolEvaluateRequest,
    ToolEvaluateResponse,
    evaluate_tool_governance,
)

router = APIRouter(tags=["governance"])

_STORE_UNAVAILABLE_DETAIL = {"error": "authoritative store unavailable"}


def apply_supply_chain_headers(
    payload: GovernanceEvaluateRequest,
    headers: dict[str, str],
) -> GovernanceEvaluateRequest:
    updates: dict[str, str] = {}
    digest = headers.get("x-ai-model-digest", "").strip()
    revision = headers.get("x-ai-model-revision", "").strip()
    region = headers.get("x-ai-region", "").strip()
    if digest:
        updates["model_artifact_digest"] = digest
    if revision:
        updates["model_revision"] = revision
    if region:
        updates["region"] = region
    return payload.model_copy(update=updates) if updates else payload


def _raise_store_unavailable() -> None:
    inc_governance_eval_errors("store_unavailable")
    raise HTTPException(status_code=503, detail=_STORE_UNAVAILABLE_DETAIL)


@router.post("/governance/evaluate", response_model=GovernanceEvaluateResponse)
def governance_evaluate(
    payload: GovernanceEvaluateRequest,
    request: Request,
) -> GovernanceEvaluateResponse:
    started_at = perf_counter()
    try:
        header_map = dict(request.headers)
        payload = apply_supply_chain_headers(payload, header_map)
        identity = resolve_workload_identity(header_map, payload)
        merged = apply_identity(payload, identity)
        request_id = request.headers.get("x-request-id") or str(uuid4())
        prior_approval = header_map.get("x-ai-approval-id", "").strip()
        try:
            if prior_approval and approval_grants_allow(prior_approval):
                from app.policy_bundle import get_policy_bundle

                bundle = get_policy_bundle()
                result = GovernanceEvaluateResponse(
                    final_verdict="allow",
                    policy_pack=merged.policy_pack or "default",
                    reasons=["durable approval grants allow"],
                    flow=["request", "durable_approval", "final_verdict"],
                    stages={},
                    approval_id=prior_approval,
                    policy_bundle_id=bundle.bundle_id,
                    policy_digest=bundle.content_digest,
                )
                result = persist_evaluation(
                    result=result, request=merged, request_id=request_id
                )
                AUDIT_STORE.record_governance_evaluate(
                    identity=identity,
                    request=merged,
                    response=result,
                    request_id=request_id,
                )
                GOVERNANCE_DECISIONS_TOTAL[
                    (result.final_verdict, merged.team, merged.environment)
                ] += 1
                return result

            enriched, quota_snapshot, signals = enrich_governance_request(merged)
            telemetry = build_telemetry_stage(enriched, quota_snapshot, signals)
            result = evaluate_governance_request(enriched, telemetry=telemetry)
            result = persist_evaluation(
                result=result, request=enriched, request_id=request_id
            )
        except StoreUnavailableError:
            _raise_store_unavailable()

        AUDIT_STORE.record_governance_evaluate(
            identity=identity,
            request=enriched,
            response=result,
            request_id=request_id,
        )
        GOVERNANCE_DECISIONS_TOTAL[
            (result.final_verdict, merged.team, merged.environment)
        ] += 1
        return result
    finally:
        observe_governance_latency_ms((perf_counter() - started_at) * 1000)


@router.get(
    "/governance/inputs/status",
    response_model=GovernanceInputsStatus,
)
def governance_inputs_status_endpoint() -> GovernanceInputsStatus:
    return governance_inputs_status()


@router.post(
    "/governance/evaluate-tool",
    response_model=ToolEvaluateResponse,
)
def governance_evaluate_tool(
    payload: ToolEvaluateRequest,
    request: Request,
) -> ToolEvaluateResponse:
    header_map = dict(request.headers)
    identity = resolve_workload_identity(header_map, payload)
    return evaluate_tool_governance(payload, identity=identity)


@router.post(
    "/governance/evaluate-response",
    response_model=EvaluationRecord,
)
def governance_evaluate_response(
    payload: ResponseEvaluateRequest,
) -> EvaluationRecord:
    return evaluate_model_response(payload)


@router.get("/evaluations/recent", response_model=EvaluationListResponse)
def evaluations_recent(
    limit: int = Query(default=50, ge=1, le=500),
    team: str | None = None,
    model: str | None = None,
) -> EvaluationListResponse:
    evaluations = EVALUATION_STORE.list_evaluations(
        limit=limit, team=team, model=model
    )
    return EvaluationListResponse(
        evaluation_count=len(evaluations),
        evaluations=evaluations,
    )


@router.post("/intent/resolve", response_model=IntentResolveResponse)
def intent_resolve(
    payload: IntentResolveRequest,
    request: Request,
) -> IntentResolveResponse:
    header_map = dict(request.headers)
    identity = resolve_workload_identity(
        header_map,
        GovernanceEvaluateRequest(
            team=payload.team,
            owner=payload.owner,
            subject=payload.subject,
            groups=payload.groups,
            policy_pack=payload.policy_pack,
            environment=payload.environment,
            namespace=payload.namespace,
        ),
    )
    region = header_map.get("x-ai-region", "").strip() or payload.region
    merged = payload.model_copy(
        update={
            "subject": identity.subject,
            "team": identity.team,
            "owner": identity.owner,
            "groups": identity.groups,
            "policy_pack": identity.policy_pack or payload.policy_pack,
            "environment": identity.environment,
            "namespace": identity.namespace,
            "region": region,
        }
    )
    return resolve_intent_plan(merged)
