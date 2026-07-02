"""MCP tool registry catalog API."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.governance_service import get_governance_root, load_module


class ToolRegistryEntry(BaseModel):
    name: str
    owner: str | None = None
    risk_tier: str | None = None
    mcp_server: str | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    allowed_teams: list[str] = Field(default_factory=list)
    allowed_namespaces: list[str] = Field(default_factory=list)
    forbidden: bool = False


class ToolRegistryResponse(BaseModel):
    updated_at: str
    tool_count: int
    tools: list[ToolRegistryEntry] = Field(default_factory=list)


def build_tool_registry() -> ToolRegistryResponse:
    root = get_governance_root()
    registry_module = load_module("tool_registry_api", root / "tools" / "evaluate.py")
    registry = registry_module.parse_registry(root / "tools" / "tools.yaml")

    tools: list[ToolRegistryEntry] = []
    for name in sorted(registry):
        entry = registry[name]
        tools.append(
            ToolRegistryEntry(
                name=name,
                owner=entry.get("owner"),
                risk_tier=entry.get("risk_tier"),
                mcp_server=entry.get("mcp_server"),
                allowed_actions=list(entry.get("allowed_actions", [])),
                forbidden_actions=list(entry.get("forbidden_actions", [])),
                allowed_teams=list(entry.get("allowed_teams", [])),
                allowed_namespaces=list(entry.get("allowed_namespaces", [])),
                forbidden=bool(entry.get("forbidden", False)),
            )
        )

    return ToolRegistryResponse(
        updated_at=datetime.now(UTC).isoformat(),
        tool_count=len(tools),
        tools=tools,
    )


def get_tool_registry_entry(tool_name: str) -> ToolRegistryEntry | None:
    response = build_tool_registry()
    for entry in response.tools:
        if entry.name == tool_name:
            return entry
    return None
