"""Unit tests for the end-to-end governance verdict logic."""

from __future__ import annotations

from types import ModuleType


def cost(decision: str) -> dict:
    return {"decision": decision, "reasons": []}


def risk(level: str) -> dict:
    return {"level": level, "score": 0, "factors": []}


def approval(decision: str) -> dict:
    return {"decision": decision, "reasons": []}


def test_cost_block_wins(pipeline_module: ModuleType) -> None:
    verdict, _ = pipeline_module.final_verdict(
        cost("block"), risk("low"), approval("allow")
    )
    assert verdict == "block"


def test_approval_block_wins(pipeline_module: ModuleType) -> None:
    verdict, _ = pipeline_module.final_verdict(
        cost("allow"), risk("low"), approval("block")
    )
    assert verdict == "block"


def test_critical_risk_requires_approval(pipeline_module: ModuleType) -> None:
    verdict, _ = pipeline_module.final_verdict(
        cost("allow"), risk("critical"), approval("allow")
    )
    assert verdict == "approval_required"


def test_cost_warn_requires_approval(pipeline_module: ModuleType) -> None:
    verdict, _ = pipeline_module.final_verdict(
        cost("warn"), risk("low"), approval("allow")
    )
    assert verdict == "approval_required"


def test_all_clear_allows(pipeline_module: ModuleType) -> None:
    verdict, reasons = pipeline_module.final_verdict(
        cost("allow"), risk("low"), approval("allow")
    )
    assert verdict == "allow"
    assert reasons == ["all governance stages allow the request"]
