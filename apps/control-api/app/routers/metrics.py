"""Prometheus metrics and summary endpoints."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.finops_service import build_finops_recommendations
from app.fleet_service import fleet_cluster_metrics
from app.inventory import get_capacity_status, get_cost_status
from app.metrics_util import (
    GOVERNANCE_DECISIONS_TOTAL,
    HTTP_REQUEST_LATENCY_MS_TOTAL,
    HTTP_REQUESTS_TOTAL,
    metric_line,
    render_governance_latency_metrics,
)
from app.probes import (
    extract_ollama_models,
    extract_vllm_models,
    get_inventory_drift,
)
from app.secrets_service import build_secrets_status

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    # Resolve probes via app.main so tests can monkeypatch fetch_*.
    from app import main as app_main

    models = app_main.get_model_inventory()
    capacity_status = get_capacity_status(models)
    cost_status = get_cost_status(models)
    ollama_payload, ollama_latency_ms, ollama_error = (
        app_main.fetch_ollama_tags()
    )
    ollama_models = (
        extract_ollama_models(ollama_payload) if ollama_error is None else []
    )
    ollama_up = 1 if ollama_error is None else 0
    vllm_payload, vllm_latency_ms, vllm_error = app_main.fetch_vllm_models()
    vllm_models = (
        extract_vllm_models(vllm_payload) if vllm_error is None else []
    )
    vllm_up = 1 if vllm_error is None else 0
    drift_status = get_inventory_drift()
    secrets_status = build_secrets_status()
    finops_status = build_finops_recommendations(limit=100)

    lines = [
        "# HELP ai_control_http_requests_total Total HTTP requests.",
        "# TYPE ai_control_http_requests_total counter",
    ]

    for (method, path, status), count in sorted(HTTP_REQUESTS_TOTAL.items()):
        lines.append(
            metric_line(
                "ai_control_http_requests_total",
                count,
                method=method,
                path=path,
                status=status,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_governance_decisions_total "
            "Governance verdicts from evaluate.",
            "# TYPE ai_control_governance_decisions_total counter",
        ]
    )
    for (verdict, team, environment), count in sorted(
        GOVERNANCE_DECISIONS_TOTAL.items()
    ):
        lines.append(
            metric_line(
                "ai_control_governance_decisions_total",
                count,
                verdict=verdict,
                team=team,
                environment=environment,
            )
        )

    lines.extend(render_governance_latency_metrics())

    lines.extend(
        [
            "# HELP ai_control_http_request_latency_ms "
            "Request latency in milliseconds.",
            "# TYPE ai_control_http_request_latency_ms summary",
        ]
    )
    for (method, path, status), latency_sum in sorted(
        HTTP_REQUEST_LATENCY_MS_TOTAL.items()
    ):
        count = HTTP_REQUESTS_TOTAL[(method, path, status)]
        lines.append(
            metric_line(
                "ai_control_http_request_latency_ms_sum",
                round(latency_sum, 3),
                method=method,
                path=path,
                status=status,
            )
        )
        lines.append(
            metric_line(
                "ai_control_http_request_latency_ms_count",
                count,
                method=method,
                path=path,
                status=status,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_backend_up Backend health status.",
            "# TYPE ai_control_backend_up gauge",
            metric_line("ai_control_backend_up", ollama_up, backend="ollama"),
            metric_line("ai_control_backend_up", vllm_up, backend="vllm"),
            "# HELP ai_control_backend_latency_ms "
            "Backend probe latency in milliseconds.",
            "# TYPE ai_control_backend_latency_ms gauge",
            metric_line(
                "ai_control_backend_latency_ms",
                ollama_latency_ms,
                backend="ollama",
            ),
            metric_line(
                "ai_control_backend_latency_ms",
                vllm_latency_ms,
                backend="vllm",
            ),
            "# HELP ai_control_model_available Model availability by backend.",
            "# TYPE ai_control_model_available gauge",
        ]
    )

    for model in models:
        lines.append(
            metric_line(
                "ai_control_model_available",
                1 if model.healthy else 0,
                backend=model.backend,
                model=model.name,
            )
        )

    for model in ollama_models:
        lines.append(
            metric_line(
                "ai_control_model_available",
                1,
                backend="ollama",
                model=model.name,
            )
        )

    for model in vllm_models:
        lines.append(
            metric_line(
                "ai_control_model_available",
                1,
                backend="vllm",
                model=model.name,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_capacity_available "
            "Total available model capacity.",
            "# TYPE ai_control_capacity_available gauge",
            metric_line(
                "ai_control_capacity_available",
                capacity_status.total_capacity_tokens_per_second,
                unit="tokens_per_second",
            ),
            "# HELP ai_control_estimated_hourly_cost_usd "
            "Estimated hourly cost.",
            "# TYPE ai_control_estimated_hourly_cost_usd gauge",
            metric_line(
                "ai_control_estimated_hourly_cost_usd",
                cost_status.estimated_hourly_cost,
            ),
            "# HELP ai_control_inventory_in_sync Inventory drift status.",
            "# TYPE ai_control_inventory_in_sync gauge",
            metric_line(
                "ai_control_inventory_in_sync",
                1 if drift_status.in_sync else 0,
            ),
            "# HELP ai_control_inventory_drift Backend inventory drift flag.",
            "# TYPE ai_control_inventory_drift gauge",
        ]
    )

    for backend in drift_status.backends:
        lines.append(
            metric_line(
                "ai_control_inventory_drift",
                0 if backend.in_sync else 1,
                backend=backend.backend,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_secret_configured "
            "Secret reference availability.",
            "# TYPE ai_control_secret_configured gauge",
        ]
    )
    for item in secrets_status.items:
        lines.append(
            metric_line(
                "ai_control_secret_configured",
                1 if item.status == "configured" else 0,
                secret=item.name,
                component=item.component,
            )
        )

    lines.extend(
        [
            "# HELP ai_control_fleet_cluster_up Fleet cluster reachability.",
            "# TYPE ai_control_fleet_cluster_up gauge",
        ]
    )
    for item in fleet_cluster_metrics():
        lines.append(
            metric_line(
                "ai_control_fleet_cluster_up",
                item["up"],
                cluster=item["cluster"],
                cloud=item["cloud"],
                region=item["region"],
            )
        )

    lines.extend(
        [
            "# HELP ai_control_finops_recommendations_total "
            "FinOps recommendations.",
            "# TYPE ai_control_finops_recommendations_total gauge",
        ]
    )
    category_counts: dict[tuple[str, str], int] = {}
    for item in finops_status.recommendations:
        key = (item.category, item.severity)
        category_counts[key] = category_counts.get(key, 0) + 1
    for (category, severity), count in sorted(category_counts.items()):
        lines.append(
            metric_line(
                "ai_control_finops_recommendations_total",
                count,
                category=category,
                severity=severity,
            )
        )

    return "\n".join(lines) + "\n"


@router.get("/summary")
def summary() -> dict[str, int | float | str]:
    from app import main as app_main

    models = app_main.get_model_inventory()
    capacity_status = get_capacity_status(models)
    cost_status = get_cost_status(models)

    return {
        "status": "ready" if capacity_status.healthy_models else "degraded",
        "models": capacity_status.models,
        "healthy_models": capacity_status.healthy_models,
        "total_capacity_tokens_per_second": (
            capacity_status.total_capacity_tokens_per_second
        ),
        "estimated_hourly_cost_usd": cost_status.estimated_hourly_cost,
    }
