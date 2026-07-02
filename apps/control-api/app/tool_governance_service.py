"""Narrow governance evaluation for MCP tool calls."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agent_registry_service import evaluate_agent_binding
from app.governance_service import get_governance_root, load_module
from app.identity_service import WorkloadIdentity


class ToolEvaluateRequest(BaseModel):
    subject: str = ""
    groups: list[str] = Field(default_factory=list)
    policy_pack: str = ""
    team: str = "platform"
    owner: str = "gateway"
    environment: str = "development"
    namespace: str = "ai-dev"
    agent: str = ""
    tool: str
    action: str = "invoke"
    mcp_server: str = ""
    write_permission: bool = False


class ToolEvaluateStageResult(BaseModel):
    decision: str
    reasons: list[str] = Field(default_factory=list)
    risk_tier: str | None = None
    known_tool: bool | None = None
    known_agent: bool | None = None


class ToolEvaluateResponse(BaseModel):
    final_verdict: str
    reasons: list[str]
    flow: list[str]
    stages: dict[str, ToolEvaluateStageResult]


def evaluate_tool_governance(
    payload: ToolEvaluateRequest,
    *,
    identity: WorkloadIdentity | None = None,
) -> ToolEvaluateResponse:
    root = get_governance_root()
    tools_module = load_module("tool_governance", root / "tools" / "evaluate.py")
    tools_registry = tools_module.parse_registry(root / "tools" / "tools.yaml")

    merged = (
        payload.model_copy(
            update={
                "subject": identity.subject,
                "team": identity.team,
                "owner": identity.owner,
                "groups": identity.groups,
                "policy_pack": identity.policy_pack,
                "environment": identity.environment,
                "namespace": identity.namespace,
            }
        )
        if identity
        else payload
    )
    row = merged.model_dump()
    tool_result = tools_module.evaluate_tool_policy(row, tools_registry)

    agent_result = evaluate_agent_binding(row, tools_registry=tools_registry)
    reasons = list(tool_result["reasons"]) + list(agent_result.get("reasons", []))
    forbidden = tool_result["forbidden"] or agent_result.get("forbidden", False)

    if forbidden:
        verdict = "block"
        if not reasons:
            reasons = ["tool governance blocked the request"]
    else:
        verdict = "allow"
        reasons = reasons or ["tool governance checks passed"]

    return ToolEvaluateResponse(
        final_verdict=verdict,
        reasons=reasons,
        flow=["request", "agent_registry", "tool_registry", "final_verdict"],
        stages={
            "agent": ToolEvaluateStageResult(
                decision="block" if agent_result.get("forbidden") else "allow",
                reasons=list(agent_result.get("reasons", [])),
                known_agent=agent_result.get("known_agent"),
            ),
            "tool": ToolEvaluateStageResult(
                decision="block" if tool_result["forbidden"] else "allow",
                reasons=tool_result["reasons"],
                risk_tier=tool_result.get("risk_tier"),
                known_tool=tool_result.get("known_tool"),
            ),
        },
    )
