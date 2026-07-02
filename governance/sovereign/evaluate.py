#!/usr/bin/env python3
"""Evaluate data residency and sovereign AI routing constraints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

EXTERNAL_PROVIDERS = {
    "anthropic",
    "openai",
    "external",
}


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


def parse_residency(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"residency file does not exist: {path}")

    config: dict[str, Any] = {"default_region": "local", "regions": {}}
    section: str | None = None
    current_region: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0:
            key, _, value = line.partition(":")
            if key == "default_region":
                config["default_region"] = value.strip()
                section = None
                continue
            if key == "regions":
                section = "regions"
                continue
            raise ValueError(f"unsupported residency line: {raw_line}")

        if section == "regions":
            if indent == 2 and line.endswith(":"):
                current_region = line[:-1]
                config["regions"][current_region] = {}
                continue
            if indent == 4 and current_region is not None:
                key, _, value = line.partition(":")
                if not key or not value:
                    raise ValueError(f"unsupported region entry: {raw_line}")
                config["regions"][current_region][key] = parse_scalar(value)
                continue

        raise ValueError(f"unsupported residency line: {raw_line}")

    return config


def evaluate_residency(
    request: dict[str, Any],
    residency: dict[str, Any],
    model_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    region = str(request.get("region") or "").strip() or str(
        residency.get("default_region", "local")
    )
    region_rules = residency.get("regions", {}).get(region, {})
    reasons: list[str] = []
    forbidden = False

    provider = str(request.get("provider", "")).strip().lower()
    external_model = (
        bool(model_entry.get("external_provider", False)) if model_entry else False
    )
    external_provider = provider in EXTERNAL_PROVIDERS or external_model

    if region_rules.get("block_external_providers") and external_provider:
        forbidden = True
        reasons.append(
            f"region {region} blocks external model providers for data residency"
        )

    if region_rules.get("require_local_model") and external_provider:
        forbidden = True
        reasons.append(f"region {region} requires local/on-prem models only")

    allowed_regions = model_entry.get("allowed_regions") if model_entry else None
    if (
        isinstance(allowed_regions, list)
        and allowed_regions
        and region not in allowed_regions
    ):
        forbidden = True
        reasons.append(
            f"model {request.get('model')} is not approved for region {region}"
        )

    return {
        "region": region,
        "forbidden": forbidden,
        "reasons": reasons,
        "external_provider": external_provider,
    }
