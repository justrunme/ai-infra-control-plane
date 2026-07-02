#!/usr/bin/env python3
"""Resolve and evaluate named policy packs for governance requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

EXTERNAL_PROVIDERS = {
    "anthropic",
    "openai",
    "external",
}

RISK_ORDER = ("low", "medium", "high", "critical")


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


def parse_packs(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"policy pack file does not exist: {path}")

    config: dict[str, Any] = {
        "default_pack": "development",
        "environment_map": {},
        "packs": {},
    }
    section: str | None = None
    current_pack: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0:
            key, _, value = line.partition(":")
            if key == "default_pack":
                config["default_pack"] = value.strip()
                section = None
                continue
            if key == "environment_map":
                section = "environment_map"
                continue
            if key == "packs":
                section = "packs"
                continue
            raise ValueError(f"unsupported policy pack line: {raw_line}")

        if section == "environment_map" and indent == 2:
            key, _, value = line.partition(":")
            if not key or not value:
                raise ValueError(f"unsupported environment map entry: {raw_line}")
            config["environment_map"][key.strip()] = value.strip()
            continue

        if section == "packs":
            if indent == 2 and line.endswith(":"):
                current_pack = line[:-1]
                config["packs"][current_pack] = {}
                continue
            if indent == 4 and current_pack is not None:
                key, _, value = line.partition(":")
                if not key or not value:
                    raise ValueError(f"unsupported pack entry: {raw_line}")
                config["packs"][current_pack][key] = parse_scalar(value)
                continue

        raise ValueError(f"unsupported policy pack line: {raw_line}")

    return config


def resolve_pack_name(request: dict[str, Any], config: dict[str, Any]) -> str:
    explicit = str(request.get("policy_pack") or "").strip()
    if explicit:
        return explicit
    environment = str(request.get("environment") or "").strip().lower()
    mapped = config.get("environment_map", {}).get(environment)
    if mapped:
        return str(mapped)
    return str(config.get("default_pack", "development"))


def _risk_at_least(level: str, minimum: str) -> bool:
    try:
        return RISK_ORDER.index(level) >= RISK_ORDER.index(minimum)
    except ValueError:
        return False


def evaluate_pack(
    request: dict[str, Any],
    config: dict[str, Any],
    *,
    registry_models: set[str] | None = None,
    risk_level: str | None = None,
) -> dict[str, Any]:
    pack_name = resolve_pack_name(request, config)
    pack = config.get("packs", {}).get(pack_name)
    if pack is None:
        return {
            "pack": pack_name,
            "decision": "block",
            "reasons": [f"unknown policy pack {pack_name}"],
            "quota_multiplier": 1.0,
            "min_risk_for_approval": "high",
        }

    reasons: list[str] = []
    required_environment = pack.get("require_environment")
    if required_environment and request.get("environment") != required_environment:
        reasons.append(
            f"policy pack {pack_name} requires environment {required_environment}"
        )

    if pack.get("block_external_providers") and request.get("provider") in (
        EXTERNAL_PROVIDERS
    ):
        reasons.append(f"policy pack {pack_name} blocks external providers")

    if pack.get("block_unknown_models"):
        known_models = registry_models or set()
        if request.get("model") not in known_models:
            reasons.append(
                f"policy pack {pack_name} blocks unregistered model {request['model']}"
            )

    if pack.get("block_sensitive_data") and request.get("sensitive_data"):
        reasons.append(f"policy pack {pack_name} blocks sensitive data workloads")

    required_region = pack.get("require_region")
    request_region = str(request.get("region") or "").strip()
    if required_region and request_region != required_region:
        reasons.append(
            f"policy pack {pack_name} requires region {required_region}"
        )

    min_risk = str(pack.get("min_risk_for_approval", "high"))
    approval_required = bool(
        risk_level is not None and _risk_at_least(str(risk_level), min_risk)
    )

    if reasons:
        return {
            "pack": pack_name,
            "decision": "block",
            "reasons": reasons,
            "quota_multiplier": float(pack.get("quota_multiplier", 1.0)),
            "min_risk_for_approval": min_risk,
            "approval_required": False,
        }

    allow_reasons = [f"policy pack {pack_name} checks passed"]
    if approval_required:
        allow_reasons.append(
            f"policy pack {pack_name} requires approval for risk level {risk_level}"
        )

    return {
        "pack": pack_name,
        "decision": "approval_required" if approval_required else "allow",
        "reasons": allow_reasons,
        "quota_multiplier": float(pack.get("quota_multiplier", 1.0)),
        "min_risk_for_approval": min_risk,
        "approval_required": approval_required,
    }
