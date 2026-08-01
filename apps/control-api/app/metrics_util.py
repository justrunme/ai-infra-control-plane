"""Prometheus metric formatting helpers and in-process counters."""

from __future__ import annotations

from collections import defaultdict

HTTP_REQUESTS_TOTAL: dict[tuple[str, str, int], int] = defaultdict(int)
HTTP_REQUEST_LATENCY_MS_TOTAL: dict[tuple[str, str, int], float] = defaultdict(
    float
)
GOVERNANCE_DECISIONS_TOTAL: dict[tuple[str, str, str], int] = defaultdict(int)

# Cumulative histogram buckets for governance evaluate latency (ms).
GOVERNANCE_EVALUATE_LATENCY_BUCKETS_MS: tuple[float, ...] = (
    5,
    10,
    25,
    50,
    100,
    250,
    500,
    1000,
    2500,
)
GOVERNANCE_EVALUATE_LATENCY_BUCKET_COUNTS: dict[str, int] = defaultdict(int)
GOVERNANCE_EVALUATE_LATENCY_MS_SUM: float = 0.0
GOVERNANCE_EVALUATE_LATENCY_MS_COUNT: int = 0
GOVERNANCE_EVALUATE_ERRORS_TOTAL: dict[str, int] = defaultdict(int)


def metric_label_value(value: str | int) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def metric_labels(**labels: str | int) -> str:
    rendered = ",".join(
        f'{key}="{metric_label_value(value)}"'
        for key, value in labels.items()
    )
    return f"{{{rendered}}}" if rendered else ""


def metric_line(name: str, value: int | float, **labels: str | int) -> str:
    return f"{name}{metric_labels(**labels)} {value}"


def observe_governance_latency_ms(latency_ms: float) -> None:
    """Record one governance evaluate sample into the latency histogram."""
    global GOVERNANCE_EVALUATE_LATENCY_MS_SUM, GOVERNANCE_EVALUATE_LATENCY_MS_COUNT
    GOVERNANCE_EVALUATE_LATENCY_MS_SUM += latency_ms
    GOVERNANCE_EVALUATE_LATENCY_MS_COUNT += 1
    for bound in GOVERNANCE_EVALUATE_LATENCY_BUCKETS_MS:
        if latency_ms <= bound:
            GOVERNANCE_EVALUATE_LATENCY_BUCKET_COUNTS[str(bound)] += 1
    GOVERNANCE_EVALUATE_LATENCY_BUCKET_COUNTS["+Inf"] += 1


def inc_governance_eval_errors(reason: str = "store_unavailable") -> None:
    GOVERNANCE_EVALUATE_ERRORS_TOTAL[reason] += 1


def reset_governance_latency_metrics() -> None:
    """Clear histogram state (tests)."""
    global GOVERNANCE_EVALUATE_LATENCY_MS_SUM, GOVERNANCE_EVALUATE_LATENCY_MS_COUNT
    GOVERNANCE_EVALUATE_LATENCY_MS_SUM = 0.0
    GOVERNANCE_EVALUATE_LATENCY_MS_COUNT = 0
    GOVERNANCE_EVALUATE_LATENCY_BUCKET_COUNTS.clear()
    GOVERNANCE_EVALUATE_ERRORS_TOTAL.clear()


def render_governance_latency_metrics() -> list[str]:
    """Render Prometheus exposition lines for governance evaluate latency."""
    lines = [
        "# HELP ai_control_governance_evaluate_latency_ms "
        "Governance evaluate latency in milliseconds.",
        "# TYPE ai_control_governance_evaluate_latency_ms histogram",
    ]
    # observe_governance_latency_ms already increments every matching cumulative bucket.
    for bound in GOVERNANCE_EVALUATE_LATENCY_BUCKETS_MS:
        lines.append(
            metric_line(
                "ai_control_governance_evaluate_latency_ms_bucket",
                GOVERNANCE_EVALUATE_LATENCY_BUCKET_COUNTS.get(str(bound), 0),
                le=str(int(bound) if bound.is_integer() else bound),
            )
        )
    lines.append(
        metric_line(
            "ai_control_governance_evaluate_latency_ms_bucket",
            GOVERNANCE_EVALUATE_LATENCY_BUCKET_COUNTS.get("+Inf", 0),
            le="+Inf",
        )
    )
    lines.append(
        metric_line(
            "ai_control_governance_evaluate_latency_ms_sum",
            round(GOVERNANCE_EVALUATE_LATENCY_MS_SUM, 3),
        )
    )
    lines.append(
        metric_line(
            "ai_control_governance_evaluate_latency_ms_count",
            GOVERNANCE_EVALUATE_LATENCY_MS_COUNT,
        )
    )
    lines.extend(
        [
            "# HELP ai_control_governance_evaluate_errors_total "
            "Governance evaluate failures (authoritative store, etc).",
            "# TYPE ai_control_governance_evaluate_errors_total counter",
        ]
    )
    for reason, count in sorted(GOVERNANCE_EVALUATE_ERRORS_TOTAL.items()):
        lines.append(
            metric_line(
                "ai_control_governance_evaluate_errors_total",
                count,
                reason=reason,
            )
        )
    return lines
