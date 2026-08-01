"""Backend probe helpers for Ollama and vLLM."""

import os
from time import perf_counter

from app import http_client
from app.drift_service import DriftStatus, build_drift_status
from app.models import OllamaModel, VllmModel
from app.probe_cache import get_or_set
from app.settings import get_settings

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_SECONDS = 2.0

VLLM_DEFAULT_BASE_URL = "http://localhost:8000"
VLLM_TIMEOUT_SECONDS = 2.0


def get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL).rstrip("/")


def fetch_ollama_tags() -> tuple[dict, int, str | None]:
    ttl = get_settings().probe_cache_ttl_seconds

    def _fetch() -> tuple[dict, int, str | None]:
        base_url = get_ollama_base_url()
        started_at = perf_counter()
        try:
            response = http_client.get(
                f"{base_url}/api/tags",
                timeout=OLLAMA_TIMEOUT_SECONDS,
            )
            latency_ms = round((perf_counter() - started_at) * 1000)
            response.raise_for_status()
            return response.json(), latency_ms, None
        except Exception as exc:  # noqa: BLE001 - probe failures become signals
            latency_ms = round((perf_counter() - started_at) * 1000)
            return {}, latency_ms, str(exc)

    return get_or_set("ollama_tags", ttl, _fetch)


def extract_ollama_models(payload: dict) -> list[OllamaModel]:
    models = payload.get("models", [])
    if not isinstance(models, list):
        return []

    return [
        OllamaModel(name=model["name"])
        for model in models
        if isinstance(model, dict) and isinstance(model.get("name"), str)
    ]


def get_vllm_base_url() -> str:
    return os.getenv("VLLM_BASE_URL", VLLM_DEFAULT_BASE_URL).rstrip("/")


def fetch_vllm_models() -> tuple[dict, int, str | None]:
    ttl = get_settings().probe_cache_ttl_seconds

    def _fetch() -> tuple[dict, int, str | None]:
        base_url = get_vllm_base_url()
        started_at = perf_counter()
        try:
            response = http_client.get(
                f"{base_url}/v1/models",
                timeout=VLLM_TIMEOUT_SECONDS,
            )
            latency_ms = round((perf_counter() - started_at) * 1000)
            response.raise_for_status()
            return response.json(), latency_ms, None
        except Exception as exc:  # noqa: BLE001 - probe failures become signals
            latency_ms = round((perf_counter() - started_at) * 1000)
            return {}, latency_ms, str(exc)

    return get_or_set("vllm_models", ttl, _fetch)


def extract_vllm_models(payload: dict) -> list[VllmModel]:
    models = payload.get("data", [])
    if not isinstance(models, list):
        return []

    return [
        VllmModel(name=model["id"])
        for model in models
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    ]


def probe_ollama_model_names() -> tuple[list[str], bool, str | None]:
    # Look up fetch via app.main so monkeypatches on app_main.fetch_* apply.
    from app import main as app_main

    payload, _, error = app_main.fetch_ollama_tags()
    if error is not None:
        return [], False, error
    return [model.name for model in extract_ollama_models(payload)], True, None


def probe_vllm_model_names() -> tuple[list[str], bool, str | None]:
    from app import main as app_main

    payload, _, error = app_main.fetch_vllm_models()
    if error is not None:
        return [], False, error
    return [model.name for model in extract_vllm_models(payload)], True, None


def get_inventory_drift() -> DriftStatus:
    # Resolve probe callables via app.main so tests can monkeypatch them.
    from app import main as app_main

    return build_drift_status(
        app_main.get_model_inventory(),
        app_main.probe_ollama_model_names,
        app_main.probe_vllm_model_names,
    )
