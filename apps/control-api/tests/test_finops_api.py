"""API tests for FinOps recommendations."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main

client = TestClient(app_main.app)


def test_finops_recommendations_endpoint() -> None:
    response = client.get("/finops/recommendations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendation_count"] >= 3
    assert payload["estimated_monthly_savings_usd"] > 0
    assert payload["recommendations"][0]["title"]


def test_finops_recommendations_filter_by_team() -> None:
    response = client.get("/finops/recommendations", params={"team": "mlops"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendations"]
    assert all(item["team"] == "mlops" for item in payload["recommendations"])


def test_metrics_include_finops_recommendations() -> None:
    client.get("/finops/recommendations")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "ai_control_finops_recommendations_total" in response.text
