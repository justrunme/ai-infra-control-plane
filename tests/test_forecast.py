"""Unit tests for the naive forecasting fallback."""

from __future__ import annotations

from types import ModuleType

import pytest


def test_naive_forecast_extrapolates_linear_trend(forecast_module: ModuleType) -> None:
    # slope = (16 - 10) / 3 = 2, last value = 16
    result = forecast_module.naive_forecast([10.0, 12.0, 14.0, 16.0], 3)
    assert result == [18.0, 20.0, 22.0]


def test_naive_forecast_clamps_to_zero(forecast_module: ModuleType) -> None:
    result = forecast_module.naive_forecast([10.0, 6.0, 2.0, 0.0], 3)
    assert all(value >= 0.0 for value in result)


def test_forecast_naive_backend_is_deterministic(
    forecast_module: ModuleType,
) -> None:
    backend, values = forecast_module.forecast([1.0, 2.0, 3.0, 4.0], 2, "naive")
    assert backend == "naive"
    assert values == [5.0, 6.0]


def test_forecast_rejects_non_positive_horizon(forecast_module: ModuleType) -> None:
    with pytest.raises(ValueError):
        forecast_module.forecast([1.0, 2.0, 3.0, 4.0], 0, "naive")
