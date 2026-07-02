"""Unit tests for agent registry."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_PATH = REPO_ROOT / "governance/agents/agents.yaml"
TOOLS_PATH = REPO_ROOT / "governance/tools/tools.yaml"


def test_parse_agent_registry(agents_module) -> None:
    registry = agents_module.parse_registry(AGENTS_PATH)
    assert "platform-copilot" in registry
    assert "jira-read" in registry["platform-copilot"]["tools"]


def test_blocks_forbidden_agent(agents_module) -> None:
    registry = agents_module.parse_registry(AGENTS_PATH)
    result = agents_module.evaluate_agent_policy(
        {
            "agent": "rogue-agent",
            "team": "platform",
            "namespace": "ai-dev",
        },
        registry,
    )
    assert result["forbidden"] is True


def test_blocks_unbound_tool(agents_module, tools_module) -> None:
    agents = agents_module.parse_registry(AGENTS_PATH)
    tools = tools_module.parse_registry(TOOLS_PATH)
    result = agents_module.evaluate_agent_policy(
        {
            "agent": "platform-copilot",
            "team": "platform",
            "namespace": "ai-dev",
            "tool": "kubernetes-admin",
        },
        agents,
        tool_registry=tools,
    )
    assert result["forbidden"] is True
