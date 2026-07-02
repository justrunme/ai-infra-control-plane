#!/usr/bin/env python3
"""Parse and evaluate model risk registry entries."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_signing_path = Path(__file__).with_name("signing.py")
_signing_spec = importlib.util.spec_from_file_location("registry_signing", _signing_path)
if _signing_spec is None or _signing_spec.loader is None:
    raise ImportError(f"cannot load signing module from {_signing_path}")
_signing = importlib.util.module_from_spec(_signing_spec)
_signing_spec.loader.exec_module(_signing)


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
    current_list_key: str | None = None
    list_keys = {"allowed_namespaces", "allowed_teams"}

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
            current_list_key = None
            registry[current_model] = {}
            continue

        if indent == 4 and current_model is not None:
            if line.startswith("- "):
                if current_list_key:
                    registry[current_model].setdefault(current_list_key, []).append(
                        line[2:]
                    )
                continue
            key, _, value = line.partition(":")
            if not key:
                raise ValueError(f"unsupported registry entry: {raw_line}")
            if not value.strip():
                if key in list_keys:
                    registry[current_model][key] = []
                    current_list_key = key
                    continue
                raise ValueError(f"unsupported registry entry: {raw_line}")
            current_list_key = None
            registry[current_model][key] = parse_scalar(value)
            continue

        if indent == 6 and current_model is not None and line.startswith("- "):
            if current_list_key:
                registry[current_model].setdefault(current_list_key, []).append(line[2:])
                continue
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

    allowed_teams = entry.get("allowed_teams")
    team = str(request.get("team", "unknown"))
    if isinstance(allowed_teams, list) and allowed_teams and team not in allowed_teams:
        forbidden = True
        reasons.append(f"team {team} is not allowed to use model {request['model']}")

    expected_digest = str(entry.get("artifact_digest", "")).strip()
    provided_digest = str(request.get("model_artifact_digest", "")).strip()
    if expected_digest and provided_digest and provided_digest != expected_digest:
        forbidden = True
        reasons.append(
            f"model artifact digest mismatch for {request['model']} "
            f"(expected {expected_digest}, got {provided_digest})"
        )

    attestation = _signing.attestation_status(request["model"], entry)
    if _signing.is_registry_signature_verify_enabled():
        if expected_digest and not attestation["has_attestation_signature"]:
            forbidden = True
            reasons.append(
                f"model {request['model']} is missing a registry attestation signature"
            )
        elif (
            attestation["has_attestation_signature"]
            and not attestation["attestation_verified"]
        ):
            forbidden = True
            reasons.append(
                f"model {request['model']} has an invalid registry attestation signature"
            )

    forecast = float(request.get("forecast_monthly_cost_usd", 0))
    budget = entry.get("max_monthly_budget_usd")
    if budget is not None and forecast > float(budget):
        forbidden = True
        reasons.append(f"forecast monthly cost {forecast} exceeds model budget {budget}")

    return {
        "known_model": True,
        "forbidden": forbidden,
        "reasons": reasons,
        "risk_tier": entry.get("risk_tier"),
        "external_provider": entry.get("external_provider", False),
        "revision": entry.get("revision"),
        "artifact_digest": entry.get("artifact_digest"),
        "sbom_ref": entry.get("sbom_ref"),
        "license": entry.get("license"),
        "attestation_verified": attestation.get("attestation_verified"),
    }
