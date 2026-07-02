"""Unit tests for MCP tool registry."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_PATH = REPO_ROOT / "governance/tools/tools.yaml"


def test_parse_tool_registry(tools_module) -> None:
    registry = tools_module.parse_registry(TOOLS_PATH)
    assert "jira-read" in registry
    assert registry["kubernetes-admin"]["forbidden_actions"] == [
        "delete",
        "patch",
        "apply",
    ]


def test_blocks_forbidden_tool(tools_module) -> None:
    registry = tools_module.parse_registry(TOOLS_PATH)
    result = tools_module.evaluate_tool_policy(
        {
            "tool": "github-write",
            "team": "platform",
            "namespace": "ai-dev",
            "action": "read",
        },
        registry,
    )
    assert result["forbidden"] is True


def test_blocks_disallowed_action(tools_module) -> None:
    registry = tools_module.parse_registry(TOOLS_PATH)
    result = tools_module.evaluate_tool_policy(
        {
            "tool": "kubernetes-admin",
            "team": "platform",
            "namespace": "ai-dev",
            "action": "delete",
        },
        registry,
    )
    assert result["forbidden"] is True
    assert "forbidden" in " ".join(result["reasons"]).lower()


def test_allows_read_action(tools_module) -> None:
    registry = tools_module.parse_registry(TOOLS_PATH)
    result = tools_module.evaluate_tool_policy(
        {
            "tool": "jira-read",
            "team": "platform",
            "namespace": "ai-dev",
            "action": "read",
        },
        registry,
    )
    assert result["forbidden"] is False
