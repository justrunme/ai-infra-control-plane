import os
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal

import httpx
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_SECONDS = 2.0


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
    backend: Literal["ollama"]
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


class BackendLatencyStatus(BaseModel):
    backend: Literal["ollama"]
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


def get_model_inventory() -> list[ModelStatus]:
    return [
        ModelStatus(
            name="llama-3.1-8b-instruct",
            backend="mock",
            healthy=True,
            latency_ms=42,
            capacity_tokens_per_second=320,
            estimated_hourly_cost_usd=0.18,
        )
    ]


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


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    models = get_model_inventory()
    capacity_status = get_capacity_status(models)
    cost_status = get_cost_status(models)
    healthy_model_count = capacity_status.healthy_models
    unhealthy_model_count = capacity_status.models - healthy_model_count

    lines = [
        "# HELP ai_control_plane_models_total Total configured AI models.",
        "# TYPE ai_control_plane_models_total gauge",
        f"ai_control_plane_models_total {capacity_status.models}",
        "# HELP ai_control_plane_models_healthy Healthy AI models.",
        "# TYPE ai_control_plane_models_healthy gauge",
        f"ai_control_plane_models_healthy {healthy_model_count}",
        "# HELP ai_control_plane_models_unhealthy Unhealthy AI models.",
        "# TYPE ai_control_plane_models_unhealthy gauge",
        f"ai_control_plane_models_unhealthy {unhealthy_model_count}",
        "# HELP ai_control_plane_capacity_tokens_per_second Total model capacity.",
        "# TYPE ai_control_plane_capacity_tokens_per_second gauge",
        "ai_control_plane_capacity_tokens_per_second "
        f"{capacity_status.total_capacity_tokens_per_second}",
        "# HELP ai_control_plane_estimated_hourly_cost_usd Estimated hourly cost.",
        "# TYPE ai_control_plane_estimated_hourly_cost_usd gauge",
        f"ai_control_plane_estimated_hourly_cost_usd {cost_status.estimated_hourly_cost}",
    ]
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
