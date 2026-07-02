"""Tests for signed model registry API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as app_main

client = TestClient(app_main.app)


def test_registry_models_lists_attested_entries() -> None:
    response = client.get("/registry/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_count"] >= 4
    llama = next(item for item in payload["models"] if item["name"] == "llama3.1:8b")
    assert llama["artifact_digest"].startswith("sha256:")
    assert llama["has_attestation_signature"] is True
    assert llama["attestation_verified"] is True


def test_registry_model_lookup_returns_entry() -> None:
    response = client.get("/registry/models/llama3.1:8b")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "llama3.1:8b"
    assert payload["revision"] == "v1"


def test_governance_blocks_digest_mismatch() -> None:
    response = client.post(
        "/governance/evaluate",
        headers={
            "x-ai-model-digest": "sha256:wrong",
            "x-ai-team": "platform",
        },
        json={
            "team": "platform",
            "namespace": "ai-dev",
            "model": "llama3.1:8b",
            "provider": "ollama",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_verdict"] == "block"
    assert "digest mismatch" in " ".join(payload["reasons"]).lower()


def test_governance_allows_matching_digest() -> None:
    response = client.post(
        "/governance/evaluate",
        headers={
            "x-ai-model-digest": (
                "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            ),
            "x-ai-team": "platform",
        },
        json={
            "team": "platform",
            "namespace": "ai-dev",
            "model": "llama3.1:8b",
            "provider": "ollama",
        },
    )

    assert response.status_code == 200
    assert response.json()["final_verdict"] == "allow"
