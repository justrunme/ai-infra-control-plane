#!/usr/bin/env python3
"""Parse and evaluate agent registry entries."""

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
        raise FileNotFoundError(f"agent registry file does not exist: {path}")

    registry: dict[str, dict[str, Any]] = {}
    section: str | None = None
    current_agent: str | None = None
    current_list_key: str | None = None
    list_keys = {"tools", "allowed_teams", "allowed_namespaces"}

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line == "agents:":
            section = "agents"
            continue

        if section != "agents":
            raise ValueError(f"unsupported agent registry format line: {raw_line}")

        if indent == 2 and line.endswith(":"):
            current_agent = line[:-1]
            current_list_key = None
            registry[current_agent] = {}
            continue

        if indent == 4 and current_agent is not None:
            if line.startswith("- "):
                if current_list_key:
                    registry[current_agent].setdefault(current_list_key, []).append(
                        line[2:]
                    )
                continue
            key, _, value = line.partition(":")
            if not key:
                raise ValueError(f"unsupported agent registry entry: {raw_line}")
            if not value.strip():
                if key in list_keys:
                    registry[current_agent][key] = []
                    current_list_key = key
                    continue
                raise ValueError(f"unsupported agent registry entry: {raw_line}")
            current_list_key = None
            registry[current_agent][key] = parse_scalar(value)
            continue

        if indent == 6 and current_agent is not None and line.startswith("- "):
            if current_list_key:
                registry[current_agent].setdefault(current_list_key, []).append(line[2:])
                continue
            raise ValueError(f"unsupported agent registry entry: {raw_line}")

        raise ValueError(f"unsupported agent registry format line: {raw_line}")

    return registry


def lookup_agent(
    registry: dict[str, dict[str, Any]], agent: str
) -> dict[str, Any] | None:
    return registry.get(agent)


def evaluate_agent_policy(
    request: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    *,
    tool_registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    agent_name = str(request.get("agent", "")).strip()
    if not agent_name:
        return {
            "known_agent": False,
            "forbidden": False,
            "reasons": [],
            "tools": [],
        }

    entry = lookup_agent(registry, agent_name)
    if entry is None:
        return {
            "known_agent": False,
            "forbidden": True,
            "reasons": [f"agent {agent_name} is not registered"],
            "tools": [],
        }

    reasons: list[str] = []
    forbidden = bool(entry.get("forbidden", False))
    if forbidden:
        reasons.append(f"agent {agent_name} is forbidden in the agent registry")

    team = str(request.get("team", "unknown"))
    allowed_teams = entry.get("allowed_teams")
    if isinstance(allowed_teams, list) and allowed_teams and team not in allowed_teams:
        forbidden = True
        reasons.append(f"team {team} is not allowed to use agent {agent_name}")

    namespace = str(request.get("namespace", ""))
    allowed_namespaces = entry.get("allowed_namespaces")
    if (
        isinstance(allowed_namespaces, list)
        and allowed_namespaces
        and namespace not in allowed_namespaces
    ):
        forbidden = True
        reasons.append(
            f"namespace {namespace} is not allowed for agent {agent_name}"
        )

    tools = list(entry.get("tools", []))
    requested_tool = str(request.get("tool", "")).strip()
    if requested_tool and tools and requested_tool not in tools:
        forbidden = True
        reasons.append(
            f"tool {requested_tool} is not bound to agent {agent_name}"
        )

    if tool_registry and requested_tool and requested_tool in tool_registry:
        if tool_registry[requested_tool].get("forbidden", False):
            forbidden = True
            reasons.append(f"bound tool {requested_tool} is forbidden")

    model = str(request.get("model", "")).strip()
    bound_model = str(entry.get("model", "")).strip()
    if model and bound_model and model != bound_model:
        forbidden = True
        reasons.append(
            f"model {model} does not match agent binding {bound_model}"
        )

    return {
        "known_agent": True,
        "forbidden": forbidden,
        "reasons": reasons,
        "tools": tools,
        "model": bound_model,
        "policy_pack": entry.get("policy_pack"),
        "owner": entry.get("owner"),
        "memory_ttl_days": entry.get("memory_ttl_days"),
    }
