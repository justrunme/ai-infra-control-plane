"""In-process metrics for the authoritative decision store."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

DB_OPERATIONS_TOTAL: dict[tuple[str, str], int] = defaultdict(int)
DB_OPERATION_ERRORS_TOTAL: dict[tuple[str, str], int] = defaultdict(int)
DB_OPERATION_LATENCY_MS_SUM: dict[str, float] = defaultdict(float)
DB_OPERATION_LATENCY_MS_COUNT: dict[str, int] = defaultdict(int)
DB_POOL_SIZE: int = 0
DB_POOL_AVAILABLE: int = 0
DB_BACKEND: str = "sqlite"


def set_pool_stats(*, backend: str, size: int, available: int) -> None:
    global DB_POOL_SIZE, DB_POOL_AVAILABLE, DB_BACKEND
    DB_BACKEND = backend
    DB_POOL_SIZE = size
    DB_POOL_AVAILABLE = available


@contextmanager
def observe_db_operation(operation: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
        DB_OPERATIONS_TOTAL[(operation, "ok")] += 1
    except Exception as exc:  # noqa: BLE001
        DB_OPERATIONS_TOTAL[(operation, "error")] += 1
        DB_OPERATION_ERRORS_TOTAL[(operation, type(exc).__name__)] += 1
        raise
    finally:
        elapsed_ms = (perf_counter() - started) * 1000
        DB_OPERATION_LATENCY_MS_SUM[operation] += elapsed_ms
        DB_OPERATION_LATENCY_MS_COUNT[operation] += 1


def render_db_metrics() -> list[str]:
    from app.metrics_util import metric_line

    lines = [
        "# HELP ai_control_db_pool_size Configured DB pool size (0 for SQLite).",
        "# TYPE ai_control_db_pool_size gauge",
        metric_line("ai_control_db_pool_size", DB_POOL_SIZE, backend=DB_BACKEND),
        "# HELP ai_control_db_pool_available Approximate idle pool connections.",
        "# TYPE ai_control_db_pool_available gauge",
        metric_line(
            "ai_control_db_pool_available", DB_POOL_AVAILABLE, backend=DB_BACKEND
        ),
        "# HELP ai_control_db_operations_total Decision-store operations.",
        "# TYPE ai_control_db_operations_total counter",
    ]
    for (operation, result), count in sorted(DB_OPERATIONS_TOTAL.items()):
        lines.append(
            metric_line(
                "ai_control_db_operations_total",
                count,
                operation=operation,
                result=result,
            )
        )
    lines.extend(
        [
            "# HELP ai_control_db_operation_errors_total Decision-store errors.",
            "# TYPE ai_control_db_operation_errors_total counter",
        ]
    )
    for (operation, error), count in sorted(DB_OPERATION_ERRORS_TOTAL.items()):
        lines.append(
            metric_line(
                "ai_control_db_operation_errors_total",
                count,
                operation=operation,
                error=error,
            )
        )
    lines.extend(
        [
            "# HELP ai_control_db_operation_latency_ms Decision-store latency.",
            "# TYPE ai_control_db_operation_latency_ms summary",
        ]
    )
    for operation, total in sorted(DB_OPERATION_LATENCY_MS_SUM.items()):
        count = DB_OPERATION_LATENCY_MS_COUNT[operation]
        lines.append(
            metric_line(
                "ai_control_db_operation_latency_ms_sum",
                round(total, 3),
                operation=operation,
            )
        )
        lines.append(
            metric_line(
                "ai_control_db_operation_latency_ms_count",
                count,
                operation=operation,
            )
        )
    return lines
