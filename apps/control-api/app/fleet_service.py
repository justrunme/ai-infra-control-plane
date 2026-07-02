"""Multi-cluster fleet registry and health probes."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

FLEET_PROBE_TIMEOUT_SECONDS = 2.0
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"
VLLM_DEFAULT_BASE_URL = "http://localhost:8000"


class FleetBackendStatus(BaseModel):
    healthy: bool | None = None
    latency_ms: int = 0
    error: str | None = None


class FleetClusterStatus(BaseModel):
    id: str
    label: str
    cloud: str
    region: str
    environment: str
    primary: bool = False
    probe_enabled: bool = False
    health: Literal["healthy", "degraded", "unknown", "unreachable"]
    node_count: int = 0
    healthy_models: int = 0
    ollama: FleetBackendStatus
    vllm: FleetBackendStatus


class FleetSummary(BaseModel):
    updated_at: str
    cluster_count: int
    healthy_clusters: int
    degraded_clusters: int
    unreachable_clusters: int
    primary_cluster: str | None = None


class FleetClustersResponse(BaseModel):
    summary: FleetSummary
    clusters: list[FleetClusterStatus] = Field(default_factory=list)


def get_fleet_root() -> Path:
    override = os.getenv("FLEET_ROOT")
    if override:
        return Path(override)

    bundled = Path(__file__).resolve().parent.parent / "fleet"
    if bundled.is_dir():
        return bundled

    return Path(__file__).resolve().parents[3] / "fleet"


def get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL).rstrip("/")


def get_vllm_base_url() -> str:
    return os.getenv("VLLM_BASE_URL", VLLM_DEFAULT_BASE_URL).rstrip("/")


def load_fleet_module():
    import importlib.util

    path = get_fleet_root() / "evaluate.py"
    spec = importlib.util.spec_from_file_location("fleet_evaluate", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load fleet module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe_url(base_url: str, path: str) -> tuple[bool, int, str | None]:
    started_at = perf_counter()
    try:
        response = httpx.get(
            f"{base_url.rstrip('/')}{path}",
            timeout=FLEET_PROBE_TIMEOUT_SECONDS,
        )
        latency_ms = round((perf_counter() - started_at) * 1000)
        response.raise_for_status()
        return True, latency_ms, None
    except httpx.HTTPError as exc:
        latency_ms = round((perf_counter() - started_at) * 1000)
        return False, latency_ms, str(exc)


def probe_ollama_for_fleet(base_url: str) -> tuple[bool, int, str | None]:
    return probe_url(base_url, "/api/tags")


def probe_vllm_for_fleet(base_url: str) -> tuple[bool, int, str | None]:
    return probe_url(base_url, "/v1/models")


def build_fleet_clusters() -> FleetClustersResponse:
    fleet_module = load_fleet_module()
    clusters = fleet_module.parse_clusters(get_fleet_root() / "clusters.yaml")
    evaluated = fleet_module.evaluate_fleet(
        clusters,
        probe_ollama=probe_ollama_for_fleet,
        probe_vllm=probe_vllm_for_fleet,
        primary_ollama_url=get_ollama_base_url(),
        primary_vllm_url=get_vllm_base_url(),
    )

    cluster_models = [FleetClusterStatus.model_validate(item) for item in evaluated]
    healthy_clusters = sum(1 for item in cluster_models if item.health == "healthy")
    degraded_clusters = sum(1 for item in cluster_models if item.health == "degraded")
    unreachable_clusters = sum(
        1 for item in cluster_models if item.health == "unreachable"
    )
    primary_cluster = next(
        (item.id for item in cluster_models if item.primary),
        cluster_models[0].id if cluster_models else None,
    )

    return FleetClustersResponse(
        summary=FleetSummary(
            updated_at=datetime.now(UTC).isoformat(),
            cluster_count=len(cluster_models),
            healthy_clusters=healthy_clusters,
            degraded_clusters=degraded_clusters,
            unreachable_clusters=unreachable_clusters,
            primary_cluster=primary_cluster,
        ),
        clusters=cluster_models,
    )


def fleet_cluster_metrics() -> list[dict[str, Any]]:
    fleet = build_fleet_clusters()
    return [
        {
            "cluster": cluster.id,
            "cloud": cluster.cloud,
            "region": cluster.region,
            "up": 0 if cluster.health == "unreachable" else 1,
        }
        for cluster in fleet.clusters
    ]
