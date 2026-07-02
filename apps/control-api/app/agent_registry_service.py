"""Agent registry catalog and binding evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.governance_service import get_governance_root, load_module


class AgentRegistryEntry(BaseModel):
    name: str
    owner: str | None = None
    model: str | None = None
    policy_pack: str | None = None
    tools: list[str] = Field(default_factory=list)
    memory_ttl_days: int | None = None
    allowed_teams: list[str] = Field(default_factory=list)
    allowed_namespaces: list[str] = Field(default_factory=list)
    forbidden: bool = False


class AgentRegistryResponse(BaseModel):
    updated_at: str
    agent_count: int
    agents: list[AgentRegistryEntry] = Field(default_factory=list)


def build_agent_registry() -> AgentRegistryResponse:
    root = get_governance_root()
    registry_module = load_module("agent_registry_api", root / "agents" / "evaluate.py")
    registry = registry_module.parse_registry(root / "agents" / "agents.yaml")

    agents: list[AgentRegistryEntry] = []
    for name in sorted(registry):
        entry = registry[name]
        agents.append(
            AgentRegistryEntry(
                name=name,
                owner=entry.get("owner"),
                model=entry.get("model"),
                policy_pack=entry.get("policy_pack"),
                tools=list(entry.get("tools", [])),
                memory_ttl_days=entry.get("memory_ttl_days"),
                allowed_teams=list(entry.get("allowed_teams", [])),
                allowed_namespaces=list(entry.get("allowed_namespaces", [])),
                forbidden=bool(entry.get("forbidden", False)),
            )
        )

    return AgentRegistryResponse(
        updated_at=datetime.now(UTC).isoformat(),
        agent_count=len(agents),
        agents=agents,
    )


def get_agent_registry_entry(agent_name: str) -> AgentRegistryEntry | None:
    response = build_agent_registry()
    for entry in response.agents:
        if entry.name == agent_name:
            return entry
    return None


def evaluate_agent_binding(
    request: dict[str, Any],
    *,
    tools_registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    agent_name = str(request.get("agent", "")).strip()
    if not agent_name:
        return {
            "known_agent": False,
            "forbidden": False,
            "reasons": [],
            "tools": [],
        }

    root = get_governance_root()
    registry_module = load_module("agent_binding", root / "agents" / "evaluate.py")
    agent_registry = registry_module.parse_registry(root / "agents" / "agents.yaml")
    if tools_registry is None:
        tools_module = load_module("tool_binding", root / "tools" / "evaluate.py")
        tools_registry = tools_module.parse_registry(root / "tools" / "tools.yaml")
    return registry_module.evaluate_agent_policy(
        request,
        agent_registry,
        tool_registry=tools_registry,
    )
