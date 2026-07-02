"""Tests for fleet cluster registry parsing and evaluation."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
CLUSTERS_PATH = REPO_ROOT / "fleet/clusters.yaml"


def test_parse_fleet_clusters(fleet_module: ModuleType) -> None:
    fleet_clusters = fleet_module.parse_clusters(CLUSTERS_PATH)
    assert "local-demo" in fleet_clusters
    assert fleet_clusters["eu-prod"]["cloud"] == "hetzner"


def test_evaluate_static_cluster(fleet_module: ModuleType) -> None:
    fleet_clusters = fleet_module.parse_clusters(CLUSTERS_PATH)
    result = fleet_module.evaluate_cluster(
        "eu-prod",
        fleet_clusters["eu-prod"],
        probe_ollama=lambda _url: (True, 10, None),
        probe_vllm=lambda _url: (True, 20, None),
        primary_ollama_url="http://ollama:11434",
        primary_vllm_url="http://vllm:8000",
    )

    assert result["health"] == "healthy"
    assert result["probe_enabled"] is False


def test_evaluate_probed_cluster_marks_degraded_when_vllm_down(
    fleet_module: ModuleType,
) -> None:
    fleet_clusters = fleet_module.parse_clusters(CLUSTERS_PATH)
    result = fleet_module.evaluate_cluster(
        "local-demo",
        fleet_clusters["local-demo"],
        probe_ollama=lambda _url: (True, 12, None),
        probe_vllm=lambda _url: (False, 40, "connection refused"),
        primary_ollama_url="http://ollama:11434",
        primary_vllm_url="http://vllm:8000",
    )

    assert result["health"] == "degraded"
