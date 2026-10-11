"""Derive governance signals from server-side config (not the request body)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.governance_service import get_governance_root
from app.jwt_verify import is_jwt_verify_enabled


def allow_client_governance_signals(headers: dict[str, str] | None = None) -> bool:
    """Return True when the caller may supply playground/simulate counters.

    Production evaluate ignores client quota/cost/sensitivity fields. Local demo
    (OIDC verify off) and principals with the ``governance-simulate`` role may
    still inject values for the playground.
    """
    if os.getenv("GOVERNANCE_ALLOW_CLIENT_SIGNALS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    if not is_jwt_verify_enabled():
        return True
    headers = headers or {}
    from app.identity_service import extract_bearer_claims
    from app.rbac import roles_from_claims

    claims = extract_bearer_claims(headers)
    if not claims:
        return False
    roles = roles_from_claims(claims)
    claimed: set[str] = set()
    for key in ("groups", "roles"):
        raw = claims.get(key)
        if isinstance(raw, list):
            claimed.update(str(x) for x in raw)
        elif isinstance(raw, str):
            claimed.update(part.strip() for part in raw.split(",") if part.strip())
    return bool(
        roles.intersection({"governance-simulate", "platform-admin"})
        or claimed.intersection({"governance-simulate", "governance:simulate"})
    )


def _parse_scalar(value: str) -> Any:
    normalized = value.strip().strip('"').strip("'")
    if normalized == "":
        return ""
    lowered = normalized.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    try:
        if "." in normalized:
            return float(normalized)
        return int(normalized)
    except ValueError:
        return normalized


def _parse_pricing_file(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"default": {}, "models": {}}
    section: str | None = None
    current_model: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0:
            key, _, value = line.partition(":")
            if key.strip() == "currency" and value.strip():
                result["currency"] = _parse_scalar(value)
                section = None
                continue
            if key.strip() in {"default", "models"} and not value.strip():
                section = key.strip()
                current_model = None
                continue
            section = None
            continue
        if section == "default" and indent == 2:
            key, _, value = line.partition(":")
            result["default"][key.strip()] = _parse_scalar(value)
            continue
        if section == "models" and indent == 2 and line.endswith(":"):
            current_model = line[:-1]
            result["models"][current_model] = {}
            continue
        if section == "models" and indent == 4 and current_model is not None:
            key, _, value = line.partition(":")
            result["models"][current_model][key.strip()] = _parse_scalar(value)
            continue
    return result


def _parse_classification_file(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tenants": {},
        "namespaces": {},
        "sensitive_classifications": [],
    }
    section: str | None = None
    current_name: str | None = None
    list_key: str | None = None

    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and line.endswith(":"):
            section = line[:-1]
            current_name = None
            list_key = None
            continue
        if section == "sensitive_classifications" and line.startswith("- "):
            result["sensitive_classifications"].append(line[2:].strip())
            continue
        if section in {"tenants", "namespaces"} and indent == 2 and line.endswith(":"):
            current_name = line[:-1]
            result[section][current_name] = {}
            list_key = None
            continue
        if (
            section in {"tenants", "namespaces"}
            and indent == 4
            and current_name is not None
        ):
            if line.startswith("- ") and list_key:
                result[section][current_name].setdefault(list_key, []).append(
                    line[2:].strip()
                )
                continue
            key, _, value = line.partition(":")
            if not value.strip():
                list_key = key.strip()
                result[section][current_name][list_key] = []
                continue
            list_key = None
            result[section][current_name][key.strip()] = _parse_scalar(value)
            continue
    return result


@lru_cache(maxsize=4)
def load_pricing_config(root: str | None = None) -> dict[str, Any]:
    governance_root = Path(root) if root else get_governance_root()
    path = governance_root / "cost" / "pricing.yaml"
    if not path.is_file():
        return {
            "default": {
                "input_usd_per_1k_tokens": 0.001,
                "output_usd_per_1k_tokens": 0.002,
                "cost_per_hour_usd": 0.50,
            },
            "models": {},
        }
    return _parse_pricing_file(path)


@lru_cache(maxsize=4)
def load_classification_config(root: str | None = None) -> dict[str, Any]:
    governance_root = Path(root) if root else get_governance_root()
    path = governance_root / "classification" / "tenants.yaml"
    if not path.is_file():
        return {
            "tenants": {},
            "namespaces": {},
            "sensitive_classifications": [
                "pii",
                "confidential",
                "restricted",
                "sensitive",
            ],
        }
    return _parse_classification_file(path)


def clear_server_signal_caches() -> None:
    load_pricing_config.cache_clear()
    load_classification_config.cache_clear()


def derive_request_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    month_to_date_cost_usd: float | None = None,
) -> dict[str, float]:
    """Compute cost fields from server pricing + optional FinOps spend."""
    pricing = load_pricing_config()
    models = pricing.get("models") or {}
    rates = dict(pricing.get("default") or {})
    if isinstance(models, dict) and model in models and isinstance(models[model], dict):
        rates.update(models[model])
    input_rate = float(rates.get("input_usd_per_1k_tokens") or 0.0)
    output_rate = float(rates.get("output_usd_per_1k_tokens") or 0.0)
    cost_per_request = (
        (max(input_tokens, 0) / 1000.0) * input_rate
        + (max(output_tokens, 0) / 1000.0) * output_rate
    )
    cost_per_hour = float(rates.get("cost_per_hour_usd") or 0.0)
    month_cost = (
        float(month_to_date_cost_usd)
        if month_to_date_cost_usd is not None
        else 0.0
    )
    forecast = max(month_cost * 1.25, cost_per_hour * 24 * 30 * 0.1)
    return {
        "cost_per_request_usd": round(cost_per_request, 8),
        "cost_per_hour_usd": cost_per_hour,
        "month_to_date_cost_usd": month_cost,
        "forecast_monthly_cost_usd": round(forecast, 4),
    }


def derive_sensitivity(
    *,
    team: str,
    namespace: str,
    headers: dict[str, str] | None = None,
) -> dict[str, bool]:
    """Derive sensitive_data / write_permission from classification + claims."""
    config = load_classification_config()
    tenants = config.get("tenants") or {}
    namespaces = config.get("namespaces") or {}
    sensitive_labels = {
        str(item).strip().lower()
        for item in (config.get("sensitive_classifications") or [])
    }

    tenant_cfg = tenants.get(team) if isinstance(tenants, dict) else None
    ns_cfg = namespaces.get(namespace) if isinstance(namespaces, dict) else None
    sensitive = False
    write_permission = False
    if isinstance(tenant_cfg, dict):
        sensitive = bool(tenant_cfg.get("default_sensitive", False))
        write_permission = bool(tenant_cfg.get("write_allowed", False))
    if isinstance(ns_cfg, dict) and ns_cfg.get("sensitive"):
        sensitive = True

    headers = headers or {}
    claim_value = (
        headers.get("x-ai-data-classification", "")
        or headers.get("x-ai-classification", "")
    ).strip().lower()
    if claim_value and claim_value in sensitive_labels:
        sensitive = True

    from app.identity_service import extract_bearer_claims, normalize_groups

    claims = extract_bearer_claims(headers)
    if claims:
        classification = str(
            claims.get("data_classification")
            or claims.get("classification")
            or ""
        ).strip().lower()
        if classification in sensitive_labels:
            sensitive = True
        roles = normalize_groups(claims.get("groups"))
        roles.extend(normalize_groups(claims.get("roles")))
        write_groups = {"ai-writers", "writers", "deployers", "ai-deployers"}
        if write_groups.intersection(roles):
            write_permission = True
        if str(claims.get("write_permission") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            write_permission = True

    return {
        "sensitive_data": sensitive,
        "write_permission": write_permission,
    }
