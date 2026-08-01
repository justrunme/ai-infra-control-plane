"""Request-bound approval digests for durable evaluate reuse."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from app.governance_service import GovernanceEvaluateRequest

# Fields that define what an approval authorizes.
# Live telemetry (requests_last_minute / tokens_today) is excluded so Redis
# enrichment cannot invalidate a bound approval.
_BINDING_FIELDS: tuple[str, ...] = (
    "subject",
    "groups",
    "policy_pack",
    "team",
    "tenant_id",
    "owner",
    "environment",
    "namespace",
    "action",
    "model",
    "provider",
    "input_tokens",
    "output_tokens",
    "cost_per_request_usd",
    "cost_per_hour_usd",
    "month_to_date_cost_usd",
    "forecast_monthly_cost_usd",
    "sensitive_data",
    "tool_access",
    "write_permission",
    "model_revision",
    "model_artifact_digest",
    "agent",
    "region",
)


def _as_mapping(
    request: GovernanceEvaluateRequest | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(request, GovernanceEvaluateRequest):
        return request.model_dump()
    return dict(request)


def binding_payload(
    request: GovernanceEvaluateRequest | Mapping[str, Any],
) -> dict[str, Any]:
    """Return the normalized subset of fields used for approval binding."""
    raw = _as_mapping(request)
    payload: dict[str, Any] = {}
    for key in _BINDING_FIELDS:
        value = raw.get(key)
        if key == "groups":
            payload[key] = sorted(str(item) for item in (value or []))
        elif key == "tenant_id":
            payload[key] = str(value or raw.get("team") or "")
        elif isinstance(value, bool):
            payload[key] = value
        elif value is None:
            payload[key] = ""
        else:
            payload[key] = value
    return payload


def compute_request_digest(
    request: GovernanceEvaluateRequest | Mapping[str, Any],
) -> str:
    """SHA-256 digest of the canonical approval-binding payload."""
    canonical = json.dumps(
        binding_payload(request),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
