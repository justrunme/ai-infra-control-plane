"""Model inventory loading and capacity/cost aggregation."""

import json
import os
from pathlib import Path

from pydantic import ValidationError

from app.models import CapacityStatus, CostStatus, ModelStatus

MODEL_INVENTORY_ENV = "MODEL_INVENTORY_PATH"
DEFAULT_MODEL_INVENTORY_PATH = Path(__file__).with_name("model_inventory.json")

BUILTIN_MODEL_INVENTORY: list[ModelStatus] = [
    ModelStatus(
        name="llama-3.1-8b-instruct",
        backend="mock",
        healthy=True,
        latency_ms=42,
        capacity_tokens_per_second=320,
        estimated_hourly_cost_usd=0.18,
    )
]


def get_model_inventory_path() -> Path:
    override = os.getenv(MODEL_INVENTORY_ENV)
    return Path(override) if override else DEFAULT_MODEL_INVENTORY_PATH


def load_model_inventory(path: Path) -> list[ModelStatus]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("model inventory must be a JSON array")
    return [ModelStatus.model_validate(item) for item in payload]


def get_model_inventory() -> list[ModelStatus]:
    path = get_model_inventory_path()
    if not path.exists():
        return list(BUILTIN_MODEL_INVENTORY)

    try:
        return load_model_inventory(path)
    except (OSError, ValueError, ValidationError):
        # Fall back to the built-in inventory so the control plane stays
        # observable even with a malformed or unreadable inventory file.
        return list(BUILTIN_MODEL_INVENTORY)


def get_capacity_status(models: list[ModelStatus]) -> CapacityStatus:
    healthy_models = sum(1 for model in models if model.healthy)
    return CapacityStatus(
        models=len(models),
        healthy_models=healthy_models,
        total_capacity_tokens_per_second=sum(
            model.capacity_tokens_per_second for model in models
        ),
    )


def get_cost_status(models: list[ModelStatus]) -> CostStatus:
    hourly_cost = round(
        sum(model.estimated_hourly_cost_usd for model in models), 2
    )
    return CostStatus(
        currency="USD",
        estimated_hourly_cost=hourly_cost,
        estimated_daily_cost=round(hourly_cost * 24, 2),
        estimated_monthly_cost=round(hourly_cost * 24 * 30, 2),
    )
