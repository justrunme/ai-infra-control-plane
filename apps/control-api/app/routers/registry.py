"""Model, tool, and agent registry endpoints."""

from fastapi import APIRouter, HTTPException

from app.agent_registry_service import (
    AgentRegistryEntry,
    AgentRegistryResponse,
    build_agent_registry,
    get_agent_registry_entry,
)
from app.model_registry_service import (
    ModelRegistryEntry,
    ModelRegistryResponse,
    build_model_registry,
    get_model_registry_entry,
)
from app.tool_registry_service import (
    ToolRegistryEntry,
    ToolRegistryResponse,
    build_tool_registry,
    get_tool_registry_entry,
)

router = APIRouter(tags=["registry"])


@router.get("/registry/models", response_model=ModelRegistryResponse)
def registry_models() -> ModelRegistryResponse:
    return build_model_registry()


@router.get("/registry/models/{model_name}", response_model=ModelRegistryEntry)
def registry_model(model_name: str) -> ModelRegistryEntry:
    entry = get_model_registry_entry(model_name)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "model not registered", "model": model_name},
        )
    return entry


@router.get("/registry/tools", response_model=ToolRegistryResponse)
def registry_tools() -> ToolRegistryResponse:
    return build_tool_registry()


@router.get("/registry/tools/{tool_name}", response_model=ToolRegistryEntry)
def registry_tool(tool_name: str) -> ToolRegistryEntry:
    entry = get_tool_registry_entry(tool_name)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "tool not registered", "tool": tool_name},
        )
    return entry


@router.get("/registry/agents", response_model=AgentRegistryResponse)
def registry_agents() -> AgentRegistryResponse:
    return build_agent_registry()


@router.get("/registry/agents/{agent_name}", response_model=AgentRegistryEntry)
def registry_agent(agent_name: str) -> AgentRegistryEntry:
    entry = get_agent_registry_entry(agent_name)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "agent not registered", "agent": agent_name},
        )
    return entry
