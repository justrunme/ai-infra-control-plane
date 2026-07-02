"""Intent engine — resolve user messages into governed orchestration plans."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.fleet_service import get_fleet_root
from app.governance_service import (
    GovernanceEvaluateRequest,
    GovernanceEvaluateResponse,
    evaluate_governance_request,
    get_governance_root,
    load_module,
)


class IntentResolveRequest(BaseModel):
    message: str
    subject: str = ""
    groups: list[str] = Field(default_factory=list)
    policy_pack: str = ""
    team: str = "platform"
    owner: str = "alice"
    environment: str = "development"
    namespace: str = "ai-dev"
    region: str = ""
    model: str = ""
    provider: str = ""
    run_governance: bool = True


class OrchestrationPlan(BaseModel):
    agent: str
    model: str
    tools: list[str] = Field(default_factory=list)
    region: str
    runtime: str
    cluster: str | None = None
    policy_pack: str = ""
    namespace: str
    team: str


class IntentClusterHint(BaseModel):
    name: str | None = None
    region: str | None = None
    cloud: str | None = None
    environment: str | None = None


class IntentResolveResponse(BaseModel):
    intent: str
    description: str | None = None
    confidence: float
    forbidden: bool = False
    reasons: list[str] = Field(default_factory=list)
    plan: OrchestrationPlan | None = None
    cluster: IntentClusterHint | None = None
    governance: GovernanceEvaluateResponse | None = None


def resolve_intent_plan(payload: IntentResolveRequest) -> IntentResolveResponse:
    root = get_governance_root()
    intent_module = load_module("intent_engine", root / "intent" / "evaluate.py")
    agent_module = load_module("intent_agents", root / "agents" / "evaluate.py")
    registry_module = load_module("intent_models", root / "registry" / "evaluate.py")
    fleet_module = load_module("intent_fleet", get_fleet_root() / "evaluate.py")

    routes = intent_module.parse_routes(root / "intent" / "routes.yaml")
    agents = agent_module.parse_registry(root / "agents" / "agents.yaml")
    models = registry_module.parse_registry(root / "registry" / "models.yaml")
    clusters = fleet_module.parse_clusters(get_fleet_root() / "clusters.yaml")

    result = intent_module.build_orchestration_plan(
        payload.model_dump(),
        routes=routes,
        agents=agents,
        models=models,
        clusters=clusters,
    )

    plan_data = result.get("plan", {})
    plan = OrchestrationPlan(**plan_data) if plan_data else None
    cluster = IntentClusterHint(**result.get("cluster", {}))

    governance: GovernanceEvaluateResponse | None = None
    if payload.run_governance and plan and not result.get("forbidden"):
        governance = evaluate_governance_request(
            GovernanceEvaluateRequest(
                subject=payload.subject,
                groups=payload.groups,
                policy_pack=plan.policy_pack or payload.policy_pack,
                team=plan.team,
                owner=payload.owner,
                environment=payload.environment,
                namespace=plan.namespace,
                model=plan.model,
                provider=plan.runtime,
                region=plan.region,
                agent=plan.agent,
                prompt_text=payload.message,
            )
        )
        if governance.final_verdict == "block":
            result["forbidden"] = True
            result["reasons"] = list(result.get("reasons", [])) + list(
                governance.reasons
            )

    return IntentResolveResponse(
        intent=str(result.get("intent", "")),
        description=result.get("description"),
        confidence=float(result.get("confidence", 0.0)),
        forbidden=bool(result.get("forbidden")),
        reasons=list(result.get("reasons", [])),
        plan=plan,
        cluster=cluster,
        governance=governance,
    )
