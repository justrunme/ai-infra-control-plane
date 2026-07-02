"""API tests for multi-cluster fleet endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main

client = TestClient(app_main.app)


def test_fleet_clusters_lists_registered_clusters() -> None:
    response = client.get("/fleet/clusters")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["cluster_count"] >= 3
    cluster_ids = {cluster["id"] for cluster in payload["clusters"]}
    assert {"local-demo", "eu-prod", "us-research"}.issubset(cluster_ids)


def test_fleet_topology_uses_federation_graph() -> None:
    response = client.get("/fleet/topology")

    assert response.status_code == 200
    payload = response.json()
    assert payload["graph_version"] == "v2-fleet"
    node_ids = {node["id"] for node in payload["nodes"]}
    assert "control-api" in node_ids
    assert "cluster-local-demo" in node_ids
    assert "cluster-eu-prod" in node_ids


def test_metrics_include_fleet_cluster_gauges() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "ai_control_fleet_cluster_up" in response.text
