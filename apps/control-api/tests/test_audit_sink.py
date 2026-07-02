"""Tests for durable audit sinks."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.audit_service import AuditEvent
from app.audit_sink import AuditSink


def _sample_event() -> AuditEvent:
    return AuditEvent(
        event_id="evt-1",
        timestamp="2026-06-30T12:00:00+00:00",
        subject="alice",
        team="platform",
        owner="alice",
        environment="development",
        namespace="ai-dev",
        model="llama3.1:8b",
        action="chat",
        final_verdict="allow",
    )


def test_jsonl_sink_appends_one_line_per_event(tmp_path, monkeypatch) -> None:
    jsonl_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("AUDIT_JSONL_PATH", str(jsonl_path))
    sink = AuditSink()

    sink.persist(_sample_event())
    sink.persist(_sample_event())

    lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["subject"] == "alice"
    assert first["final_verdict"] == "allow"

    status = sink.status()
    assert status.jsonl_enabled is True
    assert status.jsonl_written == 2
    assert status.sinks == ["jsonl"]


def test_loki_sink_pushes_structured_stream(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_LOKI_ENABLED", "true")
    monkeypatch.setenv("AUDIT_LOKI_URL", "http://loki.test")
    sink = AuditSink()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("app.audit_sink.httpx.post", return_value=mock_response) as mock_post:
        sink.persist(_sample_event())

    mock_post.assert_called_once()
    url = mock_post.call_args[0][0]
    body = mock_post.call_args[1]["json"]
    assert url == "http://loki.test/loki/api/v1/push"
    assert body["streams"][0]["stream"]["team"] == "platform"
    assert body["streams"][0]["stream"]["verdict"] == "allow"

    status = sink.status()
    assert status.loki_enabled is True
    assert status.loki_pushed == 1
    assert status.loki_errors == 0


def test_loki_sink_counts_transport_errors(monkeypatch) -> None:
    monkeypatch.setenv("AUDIT_LOKI_ENABLED", "true")
    monkeypatch.setenv("AUDIT_LOKI_URL", "http://loki.test")
    sink = AuditSink()

    with patch("app.audit_sink.httpx.post", side_effect=OSError("connection refused")):
        sink.persist(_sample_event())

    status = sink.status()
    assert status.loki_pushed == 0
    assert status.loki_errors == 1
