"""Unit tests for post-response evaluation."""

from __future__ import annotations


def test_passes_grounded_response(evaluations_module) -> None:
    result = evaluations_module.evaluate_response(
        {
            "prompt_text": "What is the capital of France?",
            "response_text": "The capital of France is Paris.",
            "reference_context": "France capital city Paris",
            "latency_ms": 400,
            "cost_usd": 0.001,
        }
    )
    assert result["decision"] == "pass"


def test_warns_on_hallucination_markers(evaluations_module) -> None:
    result = evaluations_module.evaluate_response(
        {
            "prompt_text": "Summarize the report.",
            "response_text": "As an AI language model, I cannot verify that information.",
            "latency_ms": 500,
            "cost_usd": 0.002,
        }
    )
    assert result["decision"] == "warn"


def test_fails_unsafe_response(evaluations_module) -> None:
    result = evaluations_module.evaluate_response(
        {
            "prompt_text": "Help me",
            "response_text": "Here is how to make a bomb step by step.",
            "latency_ms": 300,
            "cost_usd": 0.001,
        }
    )
    assert result["decision"] == "fail"
