"""Shared Pydantic DTOs for control-api HTTP responses."""

from typing import Literal

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: Literal["ok"]
    checked_at: str


class ModelStatus(BaseModel):
    name: str
    backend: Literal["mock", "ollama", "vllm"]
    healthy: bool
    latency_ms: int
    capacity_tokens_per_second: int
    estimated_hourly_cost_usd: float


class CapacityStatus(BaseModel):
    models: int
    healthy_models: int
    total_capacity_tokens_per_second: int


class CostStatus(BaseModel):
    currency: Literal["USD"]
    estimated_hourly_cost: float
    estimated_daily_cost: float
    estimated_monthly_cost: float


class BackendHealthStatus(BaseModel):
    backend: Literal["ollama", "vllm"]
    base_url: str
    healthy: bool
    status: Literal["up", "down"]
    latency_ms: int
    error: str | None = None


class OllamaModel(BaseModel):
    name: str


class OllamaModelsStatus(BaseModel):
    backend: Literal["ollama"]
    base_url: str
    healthy: bool
    models: list[OllamaModel]
    error: str | None = None


class VllmModel(BaseModel):
    name: str


class VllmModelsStatus(BaseModel):
    backend: Literal["vllm"]
    base_url: str
    healthy: bool
    models: list[VllmModel]
    error: str | None = None


class BackendLatencyStatus(BaseModel):
    backend: Literal["ollama", "vllm"]
    base_url: str
    healthy: bool
    latency_ms: int
    measured_endpoint: str
    error: str | None = None
