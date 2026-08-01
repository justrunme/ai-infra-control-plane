"""Topology, fleet, and inventory drift endpoints."""

from fastapi import APIRouter

from app.drift_actions import DriftActionsResponse, build_drift_actions
from app.drift_service import DriftStatus
from app.fleet_service import FleetClustersResponse, build_fleet_clusters
from app.probes import get_inventory_drift
from app.topology import TopologyStatus
from app.topology_builder import get_fleet_topology, get_platform_topology

router = APIRouter(tags=["topology"])


@router.get("/topology", response_model=TopologyStatus)
def topology() -> TopologyStatus:
    return get_platform_topology()


@router.get("/fleet/clusters", response_model=FleetClustersResponse)
def fleet_clusters() -> FleetClustersResponse:
    return build_fleet_clusters()


@router.get("/fleet/topology", response_model=TopologyStatus)
def fleet_topology() -> TopologyStatus:
    return get_fleet_topology()


@router.get("/drift", response_model=DriftStatus)
def drift() -> DriftStatus:
    return get_inventory_drift()


@router.get("/drift/actions", response_model=DriftActionsResponse)
def drift_actions() -> DriftActionsResponse:
    """Suggested remediation for inventory drift (never auto-applies)."""
    return build_drift_actions(get_inventory_drift())
