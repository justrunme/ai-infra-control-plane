"""Control API composition root: lifespan, middleware, routers, re-exports."""

from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request

from app import http_client
from app.errors import install_error_handlers
from app.inventory import (  # noqa: F401
    BUILTIN_MODEL_INVENTORY,
    DEFAULT_MODEL_INVENTORY_PATH,
    get_model_inventory,
)
from app.metrics_util import (
    HTTP_REQUEST_LATENCY_MS_TOTAL,
    HTTP_REQUESTS_TOTAL,
)
from app.probes import (  # noqa: F401
    fetch_ollama_tags,
    fetch_vllm_models,
    probe_ollama_model_names,
    probe_vllm_model_names,
)
from app.routers import (
    backends,
    dashboard,
    governance,
    health,
    inventory,
    metrics,
    ops,
    registry,
    topology,
)
from app.routers.approvals import router as approvals_router
from app.settings import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings()
    http_client.get_http_client()
    # Eager-init decision store so /readyz and migrations run at boot.
    try:
        from app.decision_store import get_decision_store

        get_decision_store()
    except Exception:  # noqa: BLE001
        pass
    yield
    http_client.close_http_client()
    from app.decision_store import reset_decision_store

    reset_decision_store(None)


app = FastAPI(
    title="AI Infrastructure Control Plane",
    version="1.3.0",
    description="Control API for private AI inference infrastructure.",
    lifespan=lifespan,
)

install_error_handlers(app)
app.include_router(approvals_router)
app.include_router(dashboard.router)
app.include_router(health.router)
app.include_router(inventory.router)
app.include_router(topology.router)
app.include_router(governance.router)
app.include_router(registry.router)
app.include_router(ops.router)
app.include_router(backends.router)
app.include_router(metrics.router)


@app.middleware("http")
async def record_http_metrics(request: Request, call_next):
    started_at = perf_counter()
    response = await call_next(request)
    latency_ms = (perf_counter() - started_at) * 1000
    metric_key = (request.method, request.url.path, response.status_code)

    HTTP_REQUESTS_TOTAL[metric_key] += 1
    HTTP_REQUEST_LATENCY_MS_TOTAL[metric_key] += latency_ms

    return response
