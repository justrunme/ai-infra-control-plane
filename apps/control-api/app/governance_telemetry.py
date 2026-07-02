"""Live governance telemetry attached to evaluate responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GovernanceTelemetryStage(BaseModel):
    quota_source: str = "request"
    requests_last_minute: int = 0
    tokens_today: int = 0
    prometheus_enabled: bool = False
    gateway_p95_latency_ms: float | None = None
    gateway_error_rate: float | None = None
    governance_block_rate: float | None = None
    tenant_request_rate: float | None = None
    prometheus_errors: list[str] = Field(default_factory=list)
    block_reasons: list[str] = Field(default_factory=list)
