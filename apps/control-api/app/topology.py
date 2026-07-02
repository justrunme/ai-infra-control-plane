"""Topology graph models for the digital twin and fleet federation views."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TopologySignal(BaseModel):
    name: str
    value: int | float | str
    unit: str
    description: str


class TopologyNode(BaseModel):
    id: str
    label: str
    kind: Literal[
        "api",
        "inference-backend",
        "ui",
        "observability",
        "gitops",
        "cluster",
        "package",
        "forecasting",
        "security",
    ]
    health: Literal["healthy", "degraded", "unknown", "unreachable"]
    signals: list[TopologySignal] = Field(default_factory=list)


class TopologyEdge(BaseModel):
    source: str
    target: str
    relationship: Literal[
        "probes",
        "serves",
        "scrapes",
        "visualizes",
        "collects",
        "deploys",
        "packages",
        "forecasts",
        "enforces",
        "runs-on",
    ]


class TopologyStatus(BaseModel):
    updated_at: str
    graph_version: str
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
