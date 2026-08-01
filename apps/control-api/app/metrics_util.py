"""Prometheus metric formatting helpers and in-process counters."""

from collections import defaultdict

HTTP_REQUESTS_TOTAL: dict[tuple[str, str, int], int] = defaultdict(int)
HTTP_REQUEST_LATENCY_MS_TOTAL: dict[tuple[str, str, int], float] = defaultdict(
    float
)
GOVERNANCE_DECISIONS_TOTAL: dict[tuple[str, str, str], int] = defaultdict(int)


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
