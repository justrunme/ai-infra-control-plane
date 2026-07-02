"""FinOps recommendation API backed by usage and utilization signals."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.governance_service import get_governance_root, load_module


class FinOpsRecommendation(BaseModel):
    id: str
    category: Literal[
        "idle_capacity",
        "budget_pressure",
        "route_local",
        "rightsizing",
    ]
    severity: Literal["high", "medium", "low"]
    team: str
    model: str
    title: str
    summary: str
    estimated_monthly_savings_usd: float
    actions: list[str] = Field(default_factory=list)


class FinOpsRecommendationsResponse(BaseModel):
    updated_at: str
    currency: str
    recommendation_count: int
    estimated_monthly_savings_usd: float
    recommendations: list[FinOpsRecommendation] = Field(default_factory=list)


def get_finops_root() -> Path:
    override = os.getenv("FINOPS_ROOT")
    if override:
        return Path(override)

    bundled = Path(__file__).resolve().parent.parent / "finops"
    if bundled.is_dir():
        return bundled

    return Path(__file__).resolve().parents[3] / "finops"


def get_finops_experiment_root() -> Path:
    override = os.getenv("FINOPS_EXPERIMENT_ROOT")
    if override:
        return Path(override)

    bundled = (
        Path(__file__).resolve().parent.parent / "experiments/finops-recommendations"
    )
    if bundled.is_dir():
        return bundled

    return Path(__file__).resolve().parents[3] / "experiments/finops-recommendations"


def build_finops_recommendations(
    *,
    team: str | None = None,
    severity: str | None = None,
    limit: int = 20,
) -> FinOpsRecommendationsResponse:
    governance_root = get_governance_root()
    finops_module = load_module(
        "finops_recommendations",
        get_finops_experiment_root() / "analyze.py",
    )
    cost_module = load_module("cost_governance", governance_root / "cost" / "evaluate.py")

    usage_path = Path(
        os.getenv(
            "FINOPS_USAGE_PATH",
            str(governance_root / "cost" / "sample_usage.csv"),
        )
    )
    policy_path = governance_root / "cost" / "policies.yaml"
    utilization_path = Path(
        os.getenv(
            "FINOPS_UTILIZATION_PATH",
            str(get_finops_root() / "utilization.yaml"),
        )
    )

    result = finops_module.build_result(
        usage_path,
        policy_path,
        utilization_path,
        cost_module=cost_module,
    )

    recommendations = [
        FinOpsRecommendation.model_validate(item)
        for item in result["recommendations"]
    ]
    if team:
        recommendations = [item for item in recommendations if item.team == team]
    if severity:
        recommendations = [item for item in recommendations if item.severity == severity]

    return FinOpsRecommendationsResponse(
        updated_at=datetime.now(UTC).isoformat(),
        currency=str(result.get("currency", "USD")),
        recommendation_count=len(recommendations[:limit]),
        estimated_monthly_savings_usd=float(
            sum(item.estimated_monthly_savings_usd for item in recommendations[:limit])
        ),
        recommendations=recommendations[:limit],
    )
