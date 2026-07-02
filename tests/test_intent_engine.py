"""Unit tests for intent engine routing."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = REPO_ROOT / "governance/intent/routes.yaml"
AGENTS_PATH = REPO_ROOT / "governance/agents/agents.yaml"
MODELS_PATH = REPO_ROOT / "governance/registry/models.yaml"
CLUSTERS_PATH = REPO_ROOT / "fleet/clusters.yaml"


def test_resolve_finance_report_intent(intent_module) -> None:
    routes = intent_module.parse_routes(ROUTES_PATH)
    name, intent, confidence = intent_module.resolve_intent(
        "Generate the quarterly revenue report for finance",
        routes,
    )
    assert name == "finance_report"
    assert intent["agent"] == "finance-copilot"
    assert confidence > 0


def test_build_plan_selects_eu_cluster(
    intent_module,
    agents_module,
    registry_module,
    fleet_module,
) -> None:
    routes = intent_module.parse_routes(ROUTES_PATH)
    agents = agents_module.parse_registry(AGENTS_PATH)
    models = registry_module.parse_registry(MODELS_PATH)
    clusters = fleet_module.parse_clusters(CLUSTERS_PATH)
    result = intent_module.build_orchestration_plan(
        {
            "message": "Prepare quarterly revenue report",
            "team": "finance",
            "environment": "production",
            "namespace": "ai-prod",
        },
        routes=routes,
        agents=agents,
        models=models,
        clusters=clusters,
    )
    assert result["intent"] == "finance_report"
    assert result["plan"]["agent"] == "finance-copilot"
    assert result["plan"]["region"] == "eu-central"
    assert result["cluster"]["name"] == "eu-prod"
