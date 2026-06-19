from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class ModelStatus(BaseModel):
    name: str
    backend: Literal["mock", "ollama", "vllm"]
    healthy: bool
    latency_ms: int
    capacity_tokens_per_second: int
    estimated_hourly_cost_usd: float


app = FastAPI(
    title="AI Infrastructure Control Plane",
    version="0.1.0",
    description="Control API for private AI inference infrastructure.",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "checked_at": datetime.now(UTC).isoformat()}


@app.get("/models", response_model=list[ModelStatus])
def list_models() -> list[ModelStatus]:
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


@app.get("/summary")
def summary() -> dict[str, int | float | str]:
    models = list_models()
    healthy_models = sum(1 for model in models if model.healthy)
    total_capacity = sum(model.capacity_tokens_per_second for model in models)
    total_cost = sum(model.estimated_hourly_cost_usd for model in models)

    return {
        "status": "ready" if healthy_models else "degraded",
        "models": len(models),
        "healthy_models": healthy_models,
        "total_capacity_tokens_per_second": total_capacity,
        "estimated_hourly_cost_usd": round(total_cost, 2),
    }

