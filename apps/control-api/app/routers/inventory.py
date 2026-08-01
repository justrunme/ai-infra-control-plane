"""Model inventory, capacity, and cost endpoints."""

from fastapi import APIRouter

from app.inventory import (
    get_capacity_status,
    get_cost_status,
    get_model_inventory,
)
from app.models import CapacityStatus, CostStatus, ModelStatus

router = APIRouter(tags=["inventory"])


@router.get("/models", response_model=list[ModelStatus])
def list_models() -> list[ModelStatus]:
    return get_model_inventory()


@router.get("/capacity", response_model=CapacityStatus)
def capacity() -> CapacityStatus:
    return get_capacity_status(get_model_inventory())


@router.get("/cost", response_model=CostStatus)
def cost() -> CostStatus:
    return get_cost_status(get_model_inventory())
