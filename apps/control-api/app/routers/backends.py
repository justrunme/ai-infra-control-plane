"""Ollama and vLLM backend probe endpoints."""

from fastapi import APIRouter

from app.models import (
    BackendHealthStatus,
    BackendLatencyStatus,
    OllamaModelsStatus,
    VllmModelsStatus,
)
from app.probes import (
    extract_ollama_models,
    extract_vllm_models,
    fetch_ollama_tags,
    fetch_vllm_models,
    get_ollama_base_url,
    get_vllm_base_url,
)

router = APIRouter(tags=["backends"])


@router.get("/backends/ollama/health", response_model=BackendHealthStatus)
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


@router.get("/backends/ollama/models", response_model=OllamaModelsStatus)
def ollama_models() -> OllamaModelsStatus:
    payload, _, error = fetch_ollama_tags()
    return OllamaModelsStatus(
        backend="ollama",
        base_url=get_ollama_base_url(),
        healthy=error is None,
        models=extract_ollama_models(payload) if error is None else [],
        error=error,
    )


@router.get("/backends/ollama/latency", response_model=BackendLatencyStatus)
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


@router.get("/backends/vllm/health", response_model=BackendHealthStatus)
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


@router.get("/backends/vllm/models", response_model=VllmModelsStatus)
def vllm_models() -> VllmModelsStatus:
    payload, _, error = fetch_vllm_models()
    return VllmModelsStatus(
        backend="vllm",
        base_url=get_vllm_base_url(),
        healthy=error is None,
        models=extract_vllm_models(payload) if error is None else [],
        error=error,
    )


@router.get("/backends/vllm/latency", response_model=BackendLatencyStatus)
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
