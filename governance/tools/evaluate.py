#!/usr/bin/env python3
"""Parse and evaluate MCP tool registry entries."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized == "":
        return ""
    if normalized.lower() in {"true", "yes"}:
        return True
    if normalized.lower() in {"false", "no"}:
        return False
    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except ValueError:
        return normalized


def parse_registry(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"tool registry file does not exist: {path}")

    registry: dict[str, dict[str, Any]] = {}
    section: str | None = None
    current_tool: str | None = None
    current_list_key: str | None = None
    list_keys = {
        "allowed_actions",
        "forbidden_actions",
        "allowed_teams",
        "allowed_namespaces",
    }

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line == "tools:":
            section = "tools"
            continue

        if section != "tools":
            raise ValueError(f"unsupported tool registry format line: {raw_line}")

        if indent == 2 and line.endswith(":"):
            current_tool = line[:-1]
            current_list_key = None
            registry[current_tool] = {}
            continue

        if indent == 4 and current_tool is not None:
            if line.startswith("- "):
                if current_list_key:
                    registry[current_tool].setdefault(current_list_key, []).append(
                        line[2:]
                    )
                continue
            key, _, value = line.partition(":")
            if not key:
                raise ValueError(f"unsupported tool registry entry: {raw_line}")
            if not value.strip():
                if key in list_keys:
                    registry[current_tool][key] = []
                    current_list_key = key
                    continue
                raise ValueError(f"unsupported tool registry entry: {raw_line}")
            current_list_key = None
            registry[current_tool][key] = parse_scalar(value)
            continue

        if indent == 6 and current_tool is not None and line.startswith("- "):
            if current_list_key:
                registry[current_tool].setdefault(current_list_key, []).append(line[2:])
                continue
            raise ValueError(f"unsupported tool registry entry: {raw_line}")

        raise ValueError(f"unsupported tool registry format line: {raw_line}")

    return registry


def lookup_tool(registry: dict[str, dict[str, Any]], tool: str) -> dict[str, Any] | None:
    return registry.get(tool)


def _action_allowed(action: str, entry: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    normalized = action.strip().lower()
    if not normalized:
        return False, ["tool action is required"]

    forbidden_actions = entry.get("forbidden_actions", [])
    if isinstance(forbidden_actions, list) and normalized in {
        str(item).lower() for item in forbidden_actions
    }:
        return False, [f"action {action} is forbidden for tool"]

    allowed_actions = entry.get("allowed_actions", [])
    if isinstance(allowed_actions, list) and allowed_actions:
        allowed = {str(item).lower() for item in allowed_actions}
        if normalized not in allowed:
            return False, [f"action {action} is not in the tool allowlist"]
    return True, reasons


def evaluate_tool_policy(
    request: dict[str, Any], registry: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    tool_name = str(request.get("tool", "")).strip()
    if not tool_name:
        return {
            "known_tool": False,
            "forbidden": True,
            "reasons": ["tool name is required"],
            "risk_tier": None,
        }

    entry = lookup_tool(registry, tool_name)
    if entry is None:
        return {
            "known_tool": False,
            "forbidden": True,
            "reasons": [f"tool {tool_name} is not registered"],
            "risk_tier": None,
        }

    reasons: list[str] = []
    forbidden = bool(entry.get("forbidden", False))
    if forbidden:
        reasons.append(f"tool {tool_name} is forbidden in the tool registry")

    team = str(request.get("team", "unknown"))
    allowed_teams = entry.get("allowed_teams")
    if isinstance(allowed_teams, list) and allowed_teams and team not in allowed_teams:
        forbidden = True
        reasons.append(f"team {team} is not allowed to use tool {tool_name}")

    namespace = str(request.get("namespace", ""))
    allowed_namespaces = entry.get("allowed_namespaces")
    if (
        isinstance(allowed_namespaces, list)
        and allowed_namespaces
        and namespace not in allowed_namespaces
    ):
        forbidden = True
        reasons.append(
            f"namespace {namespace} is not allowed for tool {tool_name}"
        )

    action = str(request.get("action", "invoke")).strip()
    allowed, action_reasons = _action_allowed(action, entry)
    if not allowed:
        forbidden = True
        reasons.extend(action_reasons)

    write_actions = {"write", "delete", "patch", "apply", "create", "update"}
    if action.lower() in write_actions and not request.get("write_permission", False):
        forbidden = True
        reasons.append(
            f"action {action} requires explicit write permission for tool {tool_name}"
        )

    return {
        "known_tool": True,
        "forbidden": forbidden,
        "reasons": reasons,
        "risk_tier": entry.get("risk_tier"),
        "owner": entry.get("owner"),
        "mcp_server": entry.get("mcp_server"),
    }
