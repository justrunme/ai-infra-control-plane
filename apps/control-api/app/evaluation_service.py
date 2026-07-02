"""Post-response evaluation API and in-memory result store."""

from __future__ import annotations

import uuid
from collections import deque
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from pydantic import BaseModel, Field

from app.governance_service import get_governance_root, load_module


class ResponseEvaluateRequest(BaseModel):
    team: str = "platform"
    model: str = "llama3.1:8b"
    request_id: str = ""
    prompt_text: str = ""
    response_text: str
    reference_context: str = ""
    latency_ms: float = Field(default=0.0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)
    latency_budget_ms: float = Field(default=5000.0, gt=0)
    cost_budget_usd: float = Field(default=0.05, ge=0)


class EvaluationScores(BaseModel):
    groundedness: float | None = None
    faithfulness: float | None = None
    hallucination_risk: float | None = None
    safety: float | None = None
    latency_ms: float | None = None
    latency_ok: bool | None = None
    cost_usd: float | None = None
    cost_ok: bool | None = None


class EvaluationRecord(BaseModel):
    evaluation_id: str
    timestamp: str
    team: str
    model: str
    request_id: str
    decision: str
    reasons: list[str] = Field(default_factory=list)
    scores: EvaluationScores


class EvaluationListResponse(BaseModel):
    evaluation_count: int
    evaluations: list[EvaluationRecord] = Field(default_factory=list)


class EvaluationStore:
    def __init__(self, *, max_events: int = 500) -> None:
        self._events: deque[EvaluationRecord] = deque(maxlen=max_events)
        self._lock = Lock()

    def record(
        self,
        payload: ResponseEvaluateRequest,
        result: dict[str, Any],
    ) -> EvaluationRecord:
        scores_raw = result.get("scores", {})
        record = EvaluationRecord(
            evaluation_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            team=payload.team,
            model=payload.model,
            request_id=payload.request_id,
            decision=str(result.get("decision", "unknown")),
            reasons=list(result.get("reasons", [])),
            scores=EvaluationScores(**scores_raw),
        )
        with self._lock:
            self._events.appendleft(record)
        return record

    def list_evaluations(
        self,
        *,
        limit: int = 50,
        team: str | None = None,
        model: str | None = None,
    ) -> list[EvaluationRecord]:
        with self._lock:
            items = list(self._events)
        if team:
            items = [item for item in items if item.team == team]
        if model:
            items = [item for item in items if item.model == model]
        return items[:limit]


EVALUATION_STORE = EvaluationStore()


def evaluate_model_response(payload: ResponseEvaluateRequest) -> EvaluationRecord:
    root = get_governance_root()
    module = load_module("response_evaluation", root / "evaluations" / "evaluate.py")
    result = module.evaluate_response(payload.model_dump())
    return EVALUATION_STORE.record(payload, result)
