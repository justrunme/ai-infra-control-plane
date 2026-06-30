#!/usr/bin/env python3
"""Parse and evaluate model risk registry entries."""

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
        raise FileNotFoundError(f"registry file does not exist: {path}")

    registry: dict[str, dict[str, Any]] = {}
    section: str | None = None
    current_model: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line == "models:":
            section = "models"
            continue

        if section != "models":
            raise ValueError(f"unsupported registry format line: {raw_line}")

        if indent == 2 and line.endswith(":"):
            current_model = line[:-1]
            registry[current_model] = {}
            continue

        if indent == 4 and current_model is not None:
            if line.startswith("- "):
                allowed = registry[current_model].setdefault("allowed_namespaces", [])
                allowed.append(line[2:])
                continue
            key, _, value = line.partition(":")
            if not key:
                raise ValueError(f"unsupported registry entry: {raw_line}")
            if not value.strip():
                if key == "allowed_namespaces":
                    registry[current_model][key] = []
                    continue
                raise ValueError(f"unsupported registry entry: {raw_line}")
            registry[current_model][key] = parse_scalar(value)
            continue

        if indent == 6 and current_model is not None and line.startswith("- "):
            allowed = registry[current_model].setdefault("allowed_namespaces", [])
            allowed.append(line[2:])
            continue

        raise ValueError(f"unsupported registry format line: {raw_line}")

    return registry


def lookup_model(
    registry: dict[str, dict[str, Any]], model: str
) -> dict[str, Any] | None:
    return registry.get(model)


def evaluate_model_policy(
    request: dict[str, Any], registry: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    entry = lookup_model(registry, request["model"])
    if entry is None:
        return {
            "known_model": False,
            "forbidden": False,
            "reasons": [f"model {request['model']} is not registered"],
            "risk_tier": None,
        }

    reasons: list[str] = []
    forbidden = bool(entry.get("forbidden", False))
    if forbidden:
        reasons.append(f"model {request['model']} is forbidden in the risk registry")

    allowed_namespaces = entry.get("allowed_namespaces")
    if (
        isinstance(allowed_namespaces, list)
        and request["namespace"] not in allowed_namespaces
    ):
        forbidden = True
        reasons.append(
            f"namespace {request['namespace']} is not allowed "
            f"for model {request['model']}"
        )

    if request.get("sensitive_data") and not entry.get("pii_allowed", False):
        forbidden = True
        reasons.append(f"model {request['model']} does not allow sensitive data")

    forecast = float(request.get("forecast_monthly_cost_usd", 0))
    budget = entry.get("max_monthly_budget_usd")
    if budget is not None and forecast > float(budget):
        forbidden = True
        reasons.append(
            f"forecast monthly cost {forecast} exceeds model budget {budget}"
        )

    return {
        "known_model": True,
        "forbidden": forbidden,
        "reasons": reasons,
        "risk_tier": entry.get("risk_tier"),
        "external_provider": entry.get("external_provider", False),
    }
