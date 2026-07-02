"""Evaluate a single AI request through the governance pipeline."""

from __future__ import annotations

import importlib.util
import os
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import BaseModel, Field


class GovernanceEvaluateRequest(BaseModel):
    subject: str = ""
    groups: list[str] = Field(default_factory=list)
    policy_pack: str = ""
    team: str = "platform"
    owner: str = "alice"
    environment: str = "development"
    namespace: str = "ai-dev"
    action: str = "invoke_model"
    model: str = "llama3.1:8b"
    provider: str = "ollama"
    input_tokens: int = Field(default=1000, ge=0)
    output_tokens: int = Field(default=500, ge=0)
    cost_per_request_usd: float = Field(default=0.01, ge=0)
    cost_per_hour_usd: float = Field(default=0.18, ge=0)
    month_to_date_cost_usd: float = Field(default=100.0, ge=0)
    forecast_monthly_cost_usd: float = Field(default=400.0, ge=0)
    sensitive_data: bool = False
    tool_access: bool = False
    write_permission: bool = False
    requests_last_minute: int = Field(default=0, ge=0)
    tokens_today: int = Field(default=0, ge=0)


class GovernanceStageResult(BaseModel):
    decision: str | None = None
    reasons: list[str] = Field(default_factory=list)
    score: int | None = None
    level: str | None = None
    pack: str | None = None
    factors: list[dict[str, Any]] = Field(default_factory=list)
    risk_tier: str | None = None
    known_model: bool | None = None


class GovernanceEvaluateResponse(BaseModel):
    final_verdict: str
    policy_pack: str
    reasons: list[str]
    flow: list[str]
    stages: dict[str, GovernanceStageResult]


def get_governance_root() -> Path:
    override = os.getenv("GOVERNANCE_ROOT")
    if override:
        return Path(override)

    bundled = Path(__file__).resolve().parent.parent / "governance"
    if bundled.is_dir():
        return bundled

    return Path(__file__).resolve().parents[3] / "governance"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_approval_request(
    request: dict[str, Any],
    cost_decision: str,
    risk_level: str,
) -> dict[str, Any]:
    return {
        "id": request["id"],
        "team": request["team"],
        "owner": request["owner"] or None,
        "environment": request["environment"],
        "namespace": request["namespace"],
        "action": request["action"],
        "model": request["model"],
        "provider": request["provider"],
        "cost_decision": cost_decision,
        "cost_per_hour_usd": request["cost_per_hour_usd"],
        "forecast_monthly_cost_usd": request["forecast_monthly_cost_usd"],
        "risk": risk_level,
    }


def final_verdict(
    pack_pre_result: dict[str, Any],
    pack_post_result: dict[str, Any],
    quota_result: dict[str, Any],
    registry_result: dict[str, Any],
    cost_result: dict[str, Any],
    risk_result: dict[str, Any],
    approval_result: dict[str, Any],
) -> tuple[str, list[str]]:
    if pack_pre_result["decision"] == "block":
        return "block", pack_pre_result["reasons"]
    if quota_result["decision"] == "block":
        return "block", quota_result["reasons"]
    if registry_result["forbidden"]:
        return "block", registry_result["reasons"]
    if cost_result["decision"] == "block":
        return "block", ["cost governance blocked the request"]
    if approval_result["decision"] == "block":
        return "block", ["approval workflow blocked the request"]
    if pack_post_result["decision"] == "approval_required":
        return "approval_required", pack_post_result["reasons"]
    if risk_result["level"] == "critical":
        return "approval_required", ["critical risk score requires human approval"]
    if approval_result["decision"] == "approval_required":
        return "approval_required", ["approval workflow requires human review"]
    if cost_result["decision"] == "warn":
        return "approval_required", ["cost governance warning requires review"]
    return "allow", ["all governance stages allow the request"]


def to_pipeline_row(payload: GovernanceEvaluateRequest) -> dict[str, Any]:
    return {
        "id": "playground",
        "timestamp": datetime.now(UTC).isoformat(),
        "subject": payload.subject or payload.owner,
        "team": payload.team,
        "owner": payload.owner,
        "policy_pack": payload.policy_pack,
        "environment": payload.environment,
        "namespace": payload.namespace,
        "action": payload.action,
        "model": payload.model,
        "provider": payload.provider,
        "input_tokens": payload.input_tokens,
        "output_tokens": payload.output_tokens,
        "cost_per_request_usd": payload.cost_per_request_usd,
        "cost_per_hour_usd": payload.cost_per_hour_usd,
        "month_to_date_cost_usd": payload.month_to_date_cost_usd,
        "forecast_monthly_cost_usd": payload.forecast_monthly_cost_usd,
        "sensitive_data": payload.sensitive_data,
        "tool_access": payload.tool_access,
        "write_permission": payload.write_permission,
        "requests_last_minute": payload.requests_last_minute,
        "tokens_today": payload.tokens_today,
    }


def evaluate_governance_request(
    payload: GovernanceEvaluateRequest,
) -> GovernanceEvaluateResponse:
    root = get_governance_root()
    pack_module = load_module(
        "policy_packs", root / "policy-packs" / "evaluate.py"
    )
    quota_module = load_module("quota_governance", root / "quota" / "evaluate.py")
    registry_module = load_module("model_registry", root / "registry" / "evaluate.py")
    cost_module = load_module("cost_governance", root / "cost" / "evaluate.py")
    risk_module = load_module("risk_governance", root / "risk" / "evaluate.py")
    approval_module = load_module(
        "approval_governance", root / "approval" / "evaluate.py"
    )

    quota_policies = quota_module.parse_policies(root / "quota" / "policies.yaml")
    pack_config = pack_module.parse_packs(root / "policy-packs" / "packs.yaml")
    registry = registry_module.parse_registry(root / "registry" / "models.yaml")
    policies = cost_module.parse_policy_file(root / "cost" / "policies.yaml")
    rules = risk_module.parse_rules(root / "risk" / "rules.yaml")
    row = to_pipeline_row(payload)
    registry_models = set(registry.keys())

    pack_pre = pack_module.evaluate_pack(
        row,
        pack_config,
        registry_models=registry_models,
    )
    if pack_pre["decision"] == "block":
        pack_post = pack_pre
        quota_result = {
            "decision": "allow",
            "reasons": ["skipped after policy pack block"],
        }
        registry_result = {
            "forbidden": False,
            "reasons": [],
            "known_model": None,
            "risk_tier": None,
        }
        cost_result = {"decision": "allow", "reasons": []}
        risk_result = {"score": 0, "level": "low", "factors": []}
        approval_result = {"decision": "allow", "reasons": []}
    else:
        row["_pack_quota_multiplier"] = pack_pre["quota_multiplier"]
        quota_result = quota_module.evaluate_request(row, quota_policies)
        registry_result = registry_module.evaluate_model_policy(row, registry)
        cost_result = cost_module.evaluate_row(row, policies)
        risk_result = risk_module.evaluate_request(row, rules, registry)
        approval_request = build_approval_request(
            row, cost_result["decision"], risk_result["level"]
        )
        approval_result = approval_module.evaluate_request(approval_request, registry)
        pack_post = pack_module.evaluate_pack(
            row,
            pack_config,
            registry_models=registry_models,
            risk_level=risk_result["level"],
        )

    verdict, reasons = final_verdict(
        pack_pre,
        pack_post,
        quota_result,
        registry_result,
        cost_result,
        risk_result,
        approval_result,
    )

    pack_stage_decision = pack_pre["decision"]
    pack_stage_reasons = list(pack_pre["reasons"])
    if pack_pre["decision"] != "block" and pack_post["decision"] == "approval_required":
        pack_stage_decision = "approval_required"
        pack_stage_reasons = list(pack_post["reasons"])

    return GovernanceEvaluateResponse(
        final_verdict=verdict,
        policy_pack=str(pack_pre["pack"]),
        reasons=reasons,
        flow=[
            "request",
            "policy_pack",
            "tenant_quota",
            "model_registry",
            "cost_decision",
            "risk_score",
            "approval_decision",
            "policy_pack_approval",
            "final_verdict",
        ],
        stages={
            "policy_pack": GovernanceStageResult(
                decision=pack_stage_decision,
                reasons=pack_stage_reasons,
                pack=str(pack_pre["pack"]),
            ),
            "quota": GovernanceStageResult(
                decision=quota_result["decision"],
                reasons=quota_result["reasons"],
            ),
            "registry": GovernanceStageResult(
                decision="block" if registry_result["forbidden"] else "allow",
                reasons=registry_result["reasons"],
                risk_tier=registry_result.get("risk_tier"),
                known_model=registry_result.get("known_model"),
            ),
            "cost": GovernanceStageResult(
                decision=cost_result["decision"],
                reasons=cost_result["reasons"],
            ),
            "risk": GovernanceStageResult(
                score=risk_result["score"],
                level=risk_result["level"],
                factors=risk_result["factors"],
            ),
            "approval": GovernanceStageResult(
                decision=approval_result["decision"],
                reasons=approval_result["reasons"],
            ),
        },
    )
