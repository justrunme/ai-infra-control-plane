import json
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, ValidationError

from app.agent_registry_service import (
    AgentRegistryEntry,
    AgentRegistryResponse,
    build_agent_registry,
    get_agent_registry_entry,
)
from app.audit_service import AUDIT_STORE, AuditEvent
from app.audit_sink import AUDIT_SINK, AuditSinkStatus
from app.drift_service import DriftStatus, build_drift_status
from app.evaluation_service import (
    EVALUATION_STORE,
    EvaluationListResponse,
    EvaluationRecord,
    ResponseEvaluateRequest,
    evaluate_model_response,
)
from app.finops_service import (
    FinOpsRecommendationsResponse,
    build_finops_recommendations,
)
from app.fleet_service import (
    FleetClustersResponse,
    build_fleet_clusters,
    fleet_cluster_metrics,
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
from app.incident_runbook_service import (
    IncidentRunbookResponse,
    build_incident_runbook,
    get_alert_definition,
    list_supported_alerts,
)
from app.model_registry_service import (
    ModelRegistryEntry,
    ModelRegistryResponse,
    build_model_registry,
    get_model_registry_entry,
)
from app.secrets_service import SecretsStatusResponse, build_secrets_status
from app.tool_governance_service import (
    ToolEvaluateRequest,
    ToolEvaluateResponse,
    evaluate_tool_governance,
)
from app.tool_registry_service import (
    ToolRegistryEntry,
    ToolRegistryResponse,
    build_tool_registry,
    get_tool_registry_entry,
)
from app.topology import (
    TopologyEdge,
    TopologyNode,
    TopologySignal,
    TopologyStatus,
)

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_SECONDS = 2.0

STATIC_DIR = Path(__file__).with_name("static")
DASHBOARD_HTML_PATH = STATIC_DIR / "index.html"

VLLM_DEFAULT_BASE_URL = "http://localhost:8000"
VLLM_TIMEOUT_SECONDS = 2.0

MODEL_INVENTORY_ENV = "MODEL_INVENTORY_PATH"
DEFAULT_MODEL_INVENTORY_PATH = Path(__file__).with_name("model_inventory.json")

HTTP_REQUESTS_TOTAL: dict[tuple[str, str, int], int] = defaultdict(int)
HTTP_REQUEST_LATENCY_MS_TOTAL: dict[tuple[str, str, int], float] = defaultdict(float)
GOVERNANCE_DECISIONS_TOTAL: dict[tuple[str, str, str], int] = defaultdict(int)


class HealthStatus(BaseModel):
    status: Literal["ok"]
    checked_at: str


class ModelStatus(BaseModel):
    name: str
    backend: Literal["mock", "ollama", "vllm"]
    healthy: bool
    latency_ms: int
    capacity_tokens_per_second: int
    estimated_hourly_cost_usd: float


class CapacityStatus(BaseModel):
    models: int
    healthy_models: int
    total_capacity_tokens_per_second: int


class CostStatus(BaseModel):
    currency: Literal["USD"]
    estimated_hourly_cost: float
    estimated_daily_cost: float
    estimated_monthly_cost: float


class BackendHealthStatus(BaseModel):
    backend: Literal["ollama", "vllm"]
    base_url: str
    healthy: bool
    status: Literal["up", "down"]
    latency_ms: int
    error: str | None = None


class OllamaModel(BaseModel):
    name: str


class OllamaModelsStatus(BaseModel):
    backend: Literal["ollama"]
    base_url: str
    healthy: bool
    models: list[OllamaModel]
    error: str | None = None


class VllmModel(BaseModel):
    name: str


class VllmModelsStatus(BaseModel):
    backend: Literal["vllm"]
    base_url: str
    healthy: bool
    models: list[VllmModel]
    error: str | None = None


class BackendLatencyStatus(BaseModel):
    backend: Literal["ollama", "vllm"]
    base_url: str
    healthy: bool
    latency_ms: int
    measured_endpoint: str
    error: str | None = None


app = FastAPI(
    title="AI Infrastructure Control Plane",
    version="0.1.0",
    description="Control API for private AI inference infrastructure.",
)


BUILTIN_MODEL_INVENTORY: list[ModelStatus] = [
    ModelStatus(
        name="llama-3.1-8b-instruct",
        backend="mock",
        healthy=True,
        latency_ms=42,
        capacity_tokens_per_second=320,
        estimated_hourly_cost_usd=0.18,
    )
]


def get_model_inventory_path() -> Path:
    override = os.getenv(MODEL_INVENTORY_ENV)
    return Path(override) if override else DEFAULT_MODEL_INVENTORY_PATH


def load_model_inventory(path: Path) -> list[ModelStatus]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("model inventory must be a JSON array")
    return [ModelStatus.model_validate(item) for item in payload]


def get_model_inventory() -> list[ModelStatus]:
    path = get_model_inventory_path()
    if not path.exists():
        return list(BUILTIN_MODEL_INVENTORY)

    try:
        return load_model_inventory(path)
    except (OSError, ValueError, ValidationError):
        # Fall back to the built-in inventory so the control plane stays
        # observable even with a malformed or unreadable inventory file.
        return list(BUILTIN_MODEL_INVENTORY)


def get_capacity_status(models: list[ModelStatus]) -> CapacityStatus:
    healthy_models = sum(1 for model in models if model.healthy)
    return CapacityStatus(
        models=len(models),
        healthy_models=healthy_models,
        total_capacity_tokens_per_second=sum(
            model.capacity_tokens_per_second for model in models
        ),
    )


def get_cost_status(models: list[ModelStatus]) -> CostStatus:
    hourly_cost = round(sum(model.estimated_hourly_cost_usd for model in models), 2)
    return CostStatus(
        currency="USD",
        estimated_hourly_cost=hourly_cost,
        estimated_daily_cost=round(hourly_cost * 24, 2),
        estimated_monthly_cost=round(hourly_cost * 24 * 30, 2),
    )


def get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL).rstrip("/")


def fetch_ollama_tags() -> tuple[dict, int, str | None]:
    base_url = get_ollama_base_url()
    started_at = perf_counter()

    try:
        response = httpx.get(
            f"{base_url}/api/tags",
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        latency_ms = round((perf_counter() - started_at) * 1000)
        response.raise_for_status()
        return response.json(), latency_ms, None
    except httpx.HTTPError as exc:
        latency_ms = round((perf_counter() - started_at) * 1000)
        return {}, latency_ms, str(exc)


def extract_ollama_models(payload: dict) -> list[OllamaModel]:
    models = payload.get("models", [])
    if not isinstance(models, list):
        return []

    return [
        OllamaModel(name=model["name"])
        for model in models
        if isinstance(model, dict) and isinstance(model.get("name"), str)
    ]


def get_vllm_base_url() -> str:
    return os.getenv("VLLM_BASE_URL", VLLM_DEFAULT_BASE_URL).rstrip("/")


def fetch_vllm_models() -> tuple[dict, int, str | None]:
    base_url = get_vllm_base_url()
    started_at = perf_counter()

    try:
        response = httpx.get(
            f"{base_url}/v1/models",
            timeout=VLLM_TIMEOUT_SECONDS,
        )
        latency_ms = round((perf_counter() - started_at) * 1000)
        response.raise_for_status()
        return response.json(), latency_ms, None
    except httpx.HTTPError as exc:
        latency_ms = round((perf_counter() - started_at) * 1000)
        return {}, latency_ms, str(exc)


def extract_vllm_models(payload: dict) -> list[VllmModel]:
    models = payload.get("data", [])
    if not isinstance(models, list):
        return []

    return [
        VllmModel(name=model["id"])
        for model in models
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    ]


def probe_ollama_model_names() -> tuple[list[str], bool, str | None]:
    payload, _, error = fetch_ollama_tags()
    if error is not None:
        return [], False, error
    return [model.name for model in extract_ollama_models(payload)], True, None


def probe_vllm_model_names() -> tuple[list[str], bool, str | None]:
    payload, _, error = fetch_vllm_models()
    if error is not None:
        return [], False, error
    return [model.name for model in extract_vllm_models(payload)], True, None


def get_inventory_drift() -> DriftStatus:
    return build_drift_status(
        get_model_inventory(),
        probe_ollama_model_names,
        probe_vllm_model_names,
    )


def metric_label_value(value: str | int) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def metric_labels(**labels: str | int) -> str:
    rendered = ",".join(
        f'{key}="{metric_label_value(value)}"' for key, value in labels.items()
    )
    return f"{{{rendered}}}" if rendered else ""


def metric_line(name: str, value: int | float, **labels: str | int) -> str:
    return f"{name}{metric_labels(**labels)} {value}"


def get_platform_topology() -> TopologyStatus:
    models = get_model_inventory()
    capacity_status = get_capacity_status(models)
    cost_status = get_cost_status(models)

    _, ollama_latency_ms, ollama_error = fetch_ollama_tags()
    ollama_health = "healthy" if ollama_error is None else "degraded"
    _, vllm_latency_ms, vllm_error = fetch_vllm_models()
    vllm_health = "healthy" if vllm_error is None else "degraded"

    return TopologyStatus(
        updated_at=datetime.now(UTC).isoformat(),
        graph_version="v1",
        nodes=[
            TopologyNode(
                id="k3s",
                label="k3s cluster",
                kind="cluster",
                health="unknown",
                signals=[
                    TopologySignal(
                        name="node_count",
                        value=1,
                        unit="nodes",
                        description="Bootstrap target from the Terraform k3s example.",
                    )
                ],
            ),
            TopologyNode(
                id="control-api",
                label="Control API",
                kind="api",
                health="healthy" if capacity_status.healthy_models else "degraded",
                signals=[
                    TopologySignal(
                        name="models",
                        value=capacity_status.models,
                        unit="count",
                        description="Models known by the control plane.",
                    ),
                    TopologySignal(
                        name="capacity",
                        value=capacity_status.total_capacity_tokens_per_second,
                        unit="tokens_per_second",
                        description="Aggregate serving capacity.",
                    ),
                    TopologySignal(
                        name="estimated_cost",
                        value=cost_status.estimated_hourly_cost,
                        unit="USD_per_hour",
                        description="Estimated hourly model serving cost.",
                    ),
                ],
            ),
            TopologyNode(
                id="ollama",
                label="Ollama",
                kind="inference-backend",
                health=ollama_health,
                signals=[
                    TopologySignal(
                        name="probe_endpoint",
                        value="/api/tags",
                        unit="http_path",
                        description="Endpoint used by the Ollama backend probe.",
                    ),
                    TopologySignal(
                        name="latency",
                        value=ollama_latency_ms,
                        unit="ms",
                        description="Live latency from the Ollama backend probe.",
                    ),
                ],
            ),
            TopologyNode(
                id="vllm",
                label="vLLM",
                kind="inference-backend",
                health=vllm_health,
                signals=[
                    TopologySignal(
                        name="probe_endpoint",
                        value="/v1/models",
                        unit="http_path",
                        description="OpenAI-compatible endpoint used by the vLLM probe.",
                    ),
                    TopologySignal(
                        name="latency",
                        value=vllm_latency_ms,
                        unit="ms",
                        description="Live latency from the vLLM backend probe.",
                    ),
                ],
            ),
            TopologyNode(
                id="openwebui",
                label="OpenWebUI",
                kind="ui",
                health="unknown",
                signals=[
                    TopologySignal(
                        name="role",
                        value="operator-ui",
                        unit="component",
                        description="Planned private AI user interface.",
                    )
                ],
            ),
            TopologyNode(
                id="prometheus",
                label="Prometheus",
                kind="observability",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="scrape_target",
                        value="/metrics",
                        unit="http_path",
                        description="Control API metrics endpoint.",
                    )
                ],
            ),
            TopologyNode(
                id="grafana",
                label="Grafana",
                kind="observability",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="dashboards",
                        value=3,
                        unit="count",
                        description="Control plane, logs, and topology dashboards.",
                    )
                ],
            ),
            TopologyNode(
                id="loki",
                label="Loki",
                kind="observability",
                health="unknown",
                signals=[
                    TopologySignal(
                        name="retention",
                        value=168,
                        unit="hours",
                        description="Example Loki retention window.",
                    )
                ],
            ),
            TopologyNode(
                id="argocd",
                label="Argo CD",
                kind="gitops",
                health="unknown",
                signals=[
                    TopologySignal(
                        name="sync_target",
                        value="helm-chart",
                        unit="component",
                        description="GitOps deployment target.",
                    )
                ],
            ),
            TopologyNode(
                id="helm-chart",
                label="AI Control Plane Helm chart",
                kind="package",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="autoscaling",
                        value="enabled",
                        unit="feature",
                        description="Horizontal Pod Autoscaler support.",
                    )
                ],
            ),
            TopologyNode(
                id="forecasting",
                label="Forecasting layer",
                kind="forecasting",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="predicted_saturation",
                        value=15,
                        unit="minutes",
                        description="Example lead time from autoscaling simulator.",
                    )
                ],
            ),
            TopologyNode(
                id="opa",
                label="OPA policy gates",
                kind="security",
                health="healthy",
                signals=[
                    TopologySignal(
                        name="policy_gate",
                        value="enabled",
                        unit="feature",
                        description="Rendered Kubernetes manifest checks.",
                    )
                ],
            ),
        ],
        edges=[
            TopologyEdge(source="control-api", target="ollama", relationship="probes"),
            TopologyEdge(source="control-api", target="vllm", relationship="probes"),
            TopologyEdge(source="openwebui", target="control-api", relationship="serves"),
            TopologyEdge(
                source="prometheus", target="control-api", relationship="scrapes"
            ),
            TopologyEdge(
                source="grafana", target="prometheus", relationship="visualizes"
            ),
            TopologyEdge(source="grafana", target="loki", relationship="visualizes"),
            TopologyEdge(source="loki", target="control-api", relationship="collects"),
            TopologyEdge(source="argocd", target="helm-chart", relationship="deploys"),
            TopologyEdge(
                source="helm-chart", target="control-api", relationship="packages"
            ),
            TopologyEdge(source="control-api", target="k3s", relationship="runs-on"),
            TopologyEdge(
                source="forecasting", target="control-api", relationship="forecasts"
            ),
            TopologyEdge(source="opa", target="helm-chart", relationship="enforces"),
        ],
    )


def get_fleet_topology() -> TopologyStatus:
    fleet = build_fleet_clusters()
    capacity_status = get_capacity_status(get_model_inventory())
    cost_status = get_cost_status(get_model_inventory())

    nodes: list[TopologyNode] = [
        TopologyNode(
            id="control-api",
            label="Control Plane",
            kind="api",
            health="healthy" if capacity_status.healthy_models else "degraded",
            signals=[
                TopologySignal(
                    name="fleet_clusters",
                    value=fleet.summary.cluster_count,
                    unit="count",
                    description="Clusters registered in the fleet registry.",
                ),
                TopologySignal(
                    name="healthy_clusters",
                    value=fleet.summary.healthy_clusters,
                    unit="count",
                    description="Clusters with healthy inference backends.",
                ),
                TopologySignal(
                    name="capacity",
                    value=capacity_status.total_capacity_tokens_per_second,
                    unit="tokens_per_second",
                    description="Aggregate serving capacity on the primary cluster.",
                ),
                TopologySignal(
                    name="estimated_cost",
                    value=cost_status.estimated_hourly_cost,
                    unit="USD_per_hour",
                    description="Estimated hourly model serving cost.",
                ),
            ],
        )
    ]
    edges: list[TopologyEdge] = []

    for cluster in fleet.clusters:
        node_id = f"cluster-{cluster.id}"
        nodes.append(
            TopologyNode(
                id=node_id,
                label=cluster.label,
                kind="cluster",
                health=cluster.health,
                signals=[
                    TopologySignal(
                        name="cloud",
                        value=cluster.cloud,
                        unit="provider",
                        description="Cloud or site label for placement policy.",
                    ),
                    TopologySignal(
                        name="region",
                        value=cluster.region,
                        unit="region",
                        description="Geographic or logical region.",
                    ),
                    TopologySignal(
                        name="environment",
                        value=cluster.environment,
                        unit="environment",
                        description="Mapped policy pack environment.",
                    ),
                    TopologySignal(
                        name="node_count",
                        value=cluster.node_count,
                        unit="nodes",
                        description="Worker nodes in the cluster.",
                    ),
                    TopologySignal(
                        name="healthy_models",
                        value=cluster.healthy_models,
                        unit="count",
                        description="Healthy models reported for the cluster.",
                    ),
                ],
            )
        )
        edges.append(
            TopologyEdge(
                source="control-api",
                target=node_id,
                relationship="runs-on" if cluster.primary else "probes",
            )
        )

    return TopologyStatus(
        updated_at=fleet.summary.updated_at,
        graph_version="v2-fleet",
        nodes=nodes,
        edges=edges,
    )


@app.middleware("http")
async def record_http_metrics(request: Request, call_next):
    started_at = perf_counter()
    response = await call_next(request)
    latency_ms = (perf_counter() - started_at) * 1000
    metric_key = (request.method, request.url.path, response.status_code)

    HTTP_REQUESTS_TOTAL[metric_key] += 1
    HTTP_REQUEST_LATENCY_MS_TOTAL[metric_key] += latency_ms

    return response


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    return DASHBOARD_HTML_PATH.read_text()


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(status="ok", checked_at=datetime.now(UTC).isoformat())


@app.get("/healthz", response_model=HealthStatus)
def healthz() -> HealthStatus:
    return health()


@app.get("/models", response_model=list[ModelStatus])
def list_models() -> list[ModelStatus]:
    return get_model_inventory()


@app.get("/capacity", response_model=CapacityStatus)
def capacity() -> CapacityStatus:
    return get_capacity_status(get_model_inventory())


@app.get("/cost", response_model=CostStatus)
def cost() -> CostStatus:
    return get_cost_status(get_model_inventory())


@app.get("/topology", response_model=TopologyStatus)
def topology() -> TopologyStatus:
    return get_platform_topology()


@app.get("/fleet/clusters", response_model=FleetClustersResponse)
def fleet_clusters() -> FleetClustersResponse:
    return build_fleet_clusters()


@app.get("/fleet/topology", response_model=TopologyStatus)
def fleet_topology() -> TopologyStatus:
    return get_fleet_topology()


@app.get("/drift", response_model=DriftStatus)
def drift() -> DriftStatus:
    return get_inventory_drift()


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


@app.post("/governance/evaluate", response_model=GovernanceEvaluateResponse)
def governance_evaluate(
    payload: GovernanceEvaluateRequest,
    request: Request,
) -> GovernanceEvaluateResponse:
    header_map = dict(request.headers)
    payload = apply_supply_chain_headers(payload, header_map)
    identity = resolve_workload_identity(header_map, payload)
    merged = apply_identity(payload, identity)
    enriched, quota_snapshot, signals = enrich_governance_request(merged)
    telemetry = build_telemetry_stage(enriched, quota_snapshot, signals)
    result = evaluate_governance_request(enriched, telemetry=telemetry)
    request_id = request.headers.get("x-request-id") or str(uuid4())
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


@app.get("/governance/inputs/status", response_model=GovernanceInputsStatus)
def governance_inputs_status_endpoint() -> GovernanceInputsStatus:
    return governance_inputs_status()


@app.get("/registry/models", response_model=ModelRegistryResponse)
def registry_models() -> ModelRegistryResponse:
    return build_model_registry()


@app.get("/registry/models/{model_name}", response_model=ModelRegistryEntry)
def registry_model(model_name: str) -> ModelRegistryEntry:
    entry = get_model_registry_entry(model_name)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "model not registered", "model": model_name},
        )
    return entry


@app.get("/registry/tools", response_model=ToolRegistryResponse)
def registry_tools() -> ToolRegistryResponse:
    return build_tool_registry()


@app.get("/registry/tools/{tool_name}", response_model=ToolRegistryEntry)
def registry_tool(tool_name: str) -> ToolRegistryEntry:
    entry = get_tool_registry_entry(tool_name)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "tool not registered", "tool": tool_name},
        )
    return entry


@app.get("/registry/agents", response_model=AgentRegistryResponse)
def registry_agents() -> AgentRegistryResponse:
    return build_agent_registry()


@app.get("/registry/agents/{agent_name}", response_model=AgentRegistryEntry)
def registry_agent(agent_name: str) -> AgentRegistryEntry:
    entry = get_agent_registry_entry(agent_name)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "agent not registered", "agent": agent_name},
        )
    return entry


@app.post("/governance/evaluate-tool", response_model=ToolEvaluateResponse)
def governance_evaluate_tool(
    payload: ToolEvaluateRequest,
    request: Request,
) -> ToolEvaluateResponse:
    header_map = dict(request.headers)
    identity = resolve_workload_identity(header_map, payload)
    return evaluate_tool_governance(payload, identity=identity)


@app.post("/governance/evaluate-response", response_model=EvaluationRecord)
def governance_evaluate_response(payload: ResponseEvaluateRequest) -> EvaluationRecord:
    return evaluate_model_response(payload)


@app.get("/evaluations/recent", response_model=EvaluationListResponse)
def evaluations_recent(
    limit: int = Query(default=50, ge=1, le=500),
    team: str | None = None,
    model: str | None = None,
) -> EvaluationListResponse:
    evaluations = EVALUATION_STORE.list_evaluations(limit=limit, team=team, model=model)
    return EvaluationListResponse(
        evaluation_count=len(evaluations),
        evaluations=evaluations,
    )


@app.get("/audit/events", response_model=list[AuditEvent])
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


@app.get("/audit/status", response_model=AuditSinkStatus)
def audit_status() -> AuditSinkStatus:
    return AUDIT_SINK.status()


@app.get("/secrets/status", response_model=SecretsStatusResponse)
def secrets_status() -> SecretsStatusResponse:
    return build_secrets_status()


@app.get("/finops/recommendations", response_model=FinOpsRecommendationsResponse)
def finops_recommendations(
    team: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> FinOpsRecommendationsResponse:
    return build_finops_recommendations(team=team, severity=severity, limit=limit)


@app.get("/incidents/alerts")
def incident_alerts() -> dict[str, list[str]]:
    return {"alerts": list_supported_alerts()}


@app.get("/incidents/runbook", response_model=IncidentRunbookResponse)
def incident_runbook(
    alert: str = Query(..., description="Prometheus alert name from the SLO catalog"),
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


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    models = get_model_inventory()
    capacity_status = get_capacity_status(models)
    cost_status = get_cost_status(models)
    ollama_payload, ollama_latency_ms, ollama_error = fetch_ollama_tags()
    ollama_models = extract_ollama_models(ollama_payload) if ollama_error is None else []
    ollama_up = 1 if ollama_error is None else 0
    vllm_payload, vllm_latency_ms, vllm_error = fetch_vllm_models()
    vllm_models = extract_vllm_models(vllm_payload) if vllm_error is None else []
    vllm_up = 1 if vllm_error is None else 0
    drift_status = get_inventory_drift()
    secrets_status = build_secrets_status()
    finops_status = build_finops_recommendations(limit=100)

    lines = [
        "# HELP ai_control_http_requests_total Total HTTP requests.",
        "# TYPE ai_control_http_requests_total counter",
    ]

    for (method, path, status), count in sorted(HTTP_REQUESTS_TOTAL.items()):
        lines.append(
            metric_line(
                "ai_control_http_requests_total",
                count,
                method=method,
                path=path,
                status=status,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_governance_decisions_total "
            "Governance verdicts from evaluate.",
            "# TYPE ai_control_governance_decisions_total counter",
        ]
    )
    for (verdict, team, environment), count in sorted(GOVERNANCE_DECISIONS_TOTAL.items()):
        lines.append(
            metric_line(
                "ai_control_governance_decisions_total",
                count,
                verdict=verdict,
                team=team,
                environment=environment,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_http_request_latency_ms Request latency in milliseconds.",
            "# TYPE ai_control_http_request_latency_ms summary",
        ]
    )
    for (method, path, status), latency_sum in sorted(
        HTTP_REQUEST_LATENCY_MS_TOTAL.items()
    ):
        count = HTTP_REQUESTS_TOTAL[(method, path, status)]
        lines.append(
            metric_line(
                "ai_control_http_request_latency_ms_sum",
                round(latency_sum, 3),
                method=method,
                path=path,
                status=status,
            )
        )
        lines.append(
            metric_line(
                "ai_control_http_request_latency_ms_count",
                count,
                method=method,
                path=path,
                status=status,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_backend_up Backend health status.",
            "# TYPE ai_control_backend_up gauge",
            metric_line("ai_control_backend_up", ollama_up, backend="ollama"),
            metric_line("ai_control_backend_up", vllm_up, backend="vllm"),
            "# HELP ai_control_backend_latency_ms Backend probe latency in milliseconds.",
            "# TYPE ai_control_backend_latency_ms gauge",
            metric_line(
                "ai_control_backend_latency_ms",
                ollama_latency_ms,
                backend="ollama",
            ),
            metric_line(
                "ai_control_backend_latency_ms",
                vllm_latency_ms,
                backend="vllm",
            ),
            "# HELP ai_control_model_available Model availability by backend.",
            "# TYPE ai_control_model_available gauge",
        ]
    )

    for model in models:
        lines.append(
            metric_line(
                "ai_control_model_available",
                1 if model.healthy else 0,
                backend=model.backend,
                model=model.name,
            )
        )

    for model in ollama_models:
        lines.append(
            metric_line(
                "ai_control_model_available",
                1,
                backend="ollama",
                model=model.name,
            )
        )

    for model in vllm_models:
        lines.append(
            metric_line(
                "ai_control_model_available",
                1,
                backend="vllm",
                model=model.name,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_capacity_available Total available model capacity.",
            "# TYPE ai_control_capacity_available gauge",
            metric_line(
                "ai_control_capacity_available",
                capacity_status.total_capacity_tokens_per_second,
                unit="tokens_per_second",
            ),
            "# HELP ai_control_estimated_hourly_cost_usd Estimated hourly cost.",
            "# TYPE ai_control_estimated_hourly_cost_usd gauge",
            metric_line(
                "ai_control_estimated_hourly_cost_usd",
                cost_status.estimated_hourly_cost,
            ),
            "# HELP ai_control_inventory_in_sync Inventory drift status.",
            "# TYPE ai_control_inventory_in_sync gauge",
            metric_line(
                "ai_control_inventory_in_sync",
                1 if drift_status.in_sync else 0,
            ),
            "# HELP ai_control_inventory_drift Backend inventory drift flag.",
            "# TYPE ai_control_inventory_drift gauge",
        ]
    )

    for backend in drift_status.backends:
        lines.append(
            metric_line(
                "ai_control_inventory_drift",
                0 if backend.in_sync else 1,
                backend=backend.backend,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_secret_configured Secret reference availability.",
            "# TYPE ai_control_secret_configured gauge",
        ]
    )
    for item in secrets_status.items:
        lines.append(
            metric_line(
                "ai_control_secret_configured",
                1 if item.status == "configured" else 0,
                secret=item.name,
                component=item.component,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_fleet_cluster_up Fleet cluster reachability.",
            "# TYPE ai_control_fleet_cluster_up gauge",
        ]
    )
    for item in fleet_cluster_metrics():
        lines.append(
            metric_line(
                "ai_control_fleet_cluster_up",
                item["up"],
                cluster=item["cluster"],
                cloud=item["cloud"],
                region=item["region"],
            )
        )

    lines.extend(
        [
            "# HELP ai_control_finops_recommendations_total FinOps recommendations.",
            "# TYPE ai_control_finops_recommendations_total gauge",
        ]
    )
    category_counts: dict[tuple[str, str], int] = {}
    for item in finops_status.recommendations:
        key = (item.category, item.severity)
        category_counts[key] = category_counts.get(key, 0) + 1
    for (category, severity), count in sorted(category_counts.items()):
        lines.append(
            metric_line(
                "ai_control_finops_recommendations_total",
                count,
                category=category,
                severity=severity,
            )
        )

    return "\n".join(lines) + "\n"


@app.get("/backends/ollama/health", response_model=BackendHealthStatus)
def ollama_health() -> BackendHealthStatus:
    _, latency_ms, error = fetch_ollama_tags()
    healthy = error is None
    return BackendHealthStatus(
        backend="ollama",
        base_url=get_ollama_base_url(),
        healthy=healthy,
        status="up" if healthy else "down",
        latency_ms=latency_ms,
        error=error,
    )


@app.get("/backends/ollama/models", response_model=OllamaModelsStatus)
def ollama_models() -> OllamaModelsStatus:
    payload, _, error = fetch_ollama_tags()
    return OllamaModelsStatus(
        backend="ollama",
        base_url=get_ollama_base_url(),
        healthy=error is None,
        models=extract_ollama_models(payload) if error is None else [],
        error=error,
    )


@app.get("/backends/ollama/latency", response_model=BackendLatencyStatus)
def ollama_latency() -> BackendLatencyStatus:
    _, latency_ms, error = fetch_ollama_tags()
    return BackendLatencyStatus(
        backend="ollama",
        base_url=get_ollama_base_url(),
        healthy=error is None,
        latency_ms=latency_ms,
        measured_endpoint="/api/tags",
        error=error,
    )


@app.get("/backends/vllm/health", response_model=BackendHealthStatus)
def vllm_health() -> BackendHealthStatus:
    _, latency_ms, error = fetch_vllm_models()
    healthy = error is None
    return BackendHealthStatus(
        backend="vllm",
        base_url=get_vllm_base_url(),
        healthy=healthy,
        status="up" if healthy else "down",
        latency_ms=latency_ms,
        error=error,
    )


@app.get("/backends/vllm/models", response_model=VllmModelsStatus)
def vllm_models() -> VllmModelsStatus:
    payload, _, error = fetch_vllm_models()
    return VllmModelsStatus(
        backend="vllm",
        base_url=get_vllm_base_url(),
        healthy=error is None,
        models=extract_vllm_models(payload) if error is None else [],
        error=error,
    )


@app.get("/backends/vllm/latency", response_model=BackendLatencyStatus)
def vllm_latency() -> BackendLatencyStatus:
    _, latency_ms, error = fetch_vllm_models()
    return BackendLatencyStatus(
        backend="vllm",
        base_url=get_vllm_base_url(),
        healthy=error is None,
        latency_ms=latency_ms,
        measured_endpoint="/v1/models",
        error=error,
    )


@app.get("/summary")
def summary() -> dict[str, int | float | str]:
    models = get_model_inventory()
    capacity_status = get_capacity_status(models)
    cost_status = get_cost_status(models)

    return {
        "status": "ready" if capacity_status.healthy_models else "degraded",
        "models": capacity_status.models,
        "healthy_models": capacity_status.healthy_models,
        "total_capacity_tokens_per_second": (
            capacity_status.total_capacity_tokens_per_second
        ),
        "estimated_hourly_cost_usd": cost_status.estimated_hourly_cost,
    }
