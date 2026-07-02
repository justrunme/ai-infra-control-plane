"""Durable audit sinks for JSONL files and Grafana Loki."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.audit_service import AuditEvent


class AuditSinkStatus(BaseModel):
    jsonl_path: str | None = None
    jsonl_enabled: bool = False
    jsonl_written: int = 0
    loki_url: str | None = None
    loki_enabled: bool = False
    loki_pushed: int = 0
    loki_errors: int = 0
    sinks: list[str] = []


class AuditSink:
    def __init__(self) -> None:
        self.jsonl_path = os.getenv("AUDIT_JSONL_PATH", "").strip()
        self.loki_url = os.getenv("AUDIT_LOKI_URL", "").strip().rstrip("/")
        self.loki_enabled = os.getenv("AUDIT_LOKI_ENABLED", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        self._jsonl_written = 0
        self._loki_pushed = 0
        self._loki_errors = 0

    @property
    def enabled_sinks(self) -> list[str]:
        sinks: list[str] = []
        if self.jsonl_path:
            sinks.append("jsonl")
        if self.loki_enabled and self.loki_url:
            sinks.append("loki")
        return sinks

    def persist(self, event: AuditEvent) -> None:
        payload = event.model_dump()
        if self.jsonl_path:
            self._append_jsonl(payload)
        if self.loki_enabled and self.loki_url:
            self._push_loki(payload)

    def _append_jsonl(self, payload: dict) -> None:
        path = Path(self.jsonl_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self._jsonl_written += 1

    def _push_loki(self, payload: dict) -> None:
        timestamp_ns = str(int(time.time() * 1_000_000_000))
        body = {
            "streams": [
                {
                    "stream": {
                        "app": "ai-control-plane",
                        "event_type": payload.get("event_type", "governance_evaluate"),
                        "team": payload.get("team", "unknown"),
                        "verdict": payload.get("final_verdict", "unknown"),
                    },
                    "values": [
                        [timestamp_ns, json.dumps(payload, separators=(",", ":"))]
                    ],
                }
            ]
        }
        try:
            response = httpx.post(
                f"{self.loki_url}/loki/api/v1/push",
                json=body,
                timeout=float(os.getenv("AUDIT_LOKI_TIMEOUT_SECONDS", "2.0")),
            )
            response.raise_for_status()
            self._loki_pushed += 1
        except (httpx.HTTPError, OSError):
            self._loki_errors += 1

    def status(self) -> AuditSinkStatus:
        return AuditSinkStatus(
            jsonl_path=self.jsonl_path or None,
            jsonl_enabled=bool(self.jsonl_path),
            jsonl_written=self._jsonl_written,
            loki_url=self.loki_url or None,
            loki_enabled=bool(self.loki_enabled and self.loki_url),
            loki_pushed=self._loki_pushed,
            loki_errors=self._loki_errors,
            sinks=self.enabled_sinks,
        )


def get_audit_sink() -> AuditSink:
    return AuditSink()


AUDIT_SINK = get_audit_sink()
