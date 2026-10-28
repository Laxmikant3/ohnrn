"""Error metric mathematics."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.services.metrics import (
    bias,
    coverage,
    daily_metrics,
    error_distribution,
    mae,
    mape,
    rmse,
    summary,
    wape,
)


def series(values):
    return pd.Series(values, dtype="float64")


def test_mae_hand_computed():
    errors = series([10, -20, 30])
    result = mae(errors)
    assert result.value == 20.0
    assert result.n == 3


def test_rmse_hand_computed():
    result = rmse(series([10, -20, 30]))
    assert result.value == pytest.approx(math.sqrt(1400 / 3), abs=0.01)
    assert result.n == 3


def test_bias_hand_computed():
    result = bias(series([10, -20, 30]))
    assert result.value == pytest.approx(6.67, abs=0.01)
    assert result.n == 3


def test_mape_and_zero_denominator_exclusion():
    mape_result, excluded = mape(
        series([10, -20, 5, 1]), series([100, 200, 0, 0.5]), min_actual_mw=1.0
    )
    # First two are 10% each; 5/0 and 1/0.5 are excluded.
    assert mape_result.value == pytest.approx(10.0)
    assert mape_result.n == 2
    assert excluded == 2


def test_mape_threshold_is_configurable():
    result, excluded = mape(series([5]), series([10]), min_actual_mw=20.0)
    assert result.value is None
    assert result.n == 0
    assert excluded == 1


def test_wape_hand_computed():
    result = wape(series([10, -20, 30]), series([100, 200, 300]))
    assert result.value == pytest.approx(10.0)
    assert result.n == 3


def test_wape_returns_none_for_zero_total_actual():
    result = wape(series([1, 2]), series([0, 0]))
    assert result.value is None
    assert result.n == 0


def test_coverage():
    result = coverage(90, 96)
    assert result.value == 93.75
    assert result.n == 90
    result = coverage(0, 0)
    assert result.value is None


def test_empty_metrics_are_none_not_zero():
    empty = series([])
    assert mae(empty).value is None
    assert rmse(empty).value is None
    assert bias(empty).value is None
    assert mae(empty).n == 0


def test_summary_population_and_metrics():
    frame = pd.DataFrame(
        {
            "status": ["matched", "matched", "matched", "missing_actual", "missing_forecast"],
            "actual_mw": [100.0, 200.0, 0.0, 50.0, None],
            "forecast_mw": [110.0, 180.0, 5.0, 60.0, None],
            "error_mw": [10.0, -20.0, 5.0, 10.0, None],
            "absolute_error_mw": [10.0, 20.0, 5.0, 10.0, None],
            "percentage_error": [10.0, -10.0, None, 20.0, None],
            "delivery_date": ["2026-01-01"] * 5,
            "delivery_start_utc": pd.to_datetime(
                [
                    "2026-01-01T00:00Z",
                    "2026-01-01T00:30Z",
                    "2026-01-01T01:00Z",
                    "2026-01-01T01:30Z",
                    "2026-01-01T02:00Z",
                ],
                utc=True,
            ),
            "publish_time_utc": pd.NaT,
            "lead_time_hours": [14.5, 14.5, 14.5, 14.5, None],
            "lead_time_bucket": ["12to18"] * 4 + [None],
            "settlement_period": [1, 2, 3, 4, 5],
            "interval_label": ["a", "b", "c", "d", "e"],
            "eligibility": ["eligible"] * 5,
            "is_cutoff_compliant": [True] * 5,
            "cutoff_time_utc": pd.NaT,
            "delivery_end_utc": pd.NaT,
            "local_start": pd.NaT,
            "hour": [0, 0, 1, 1, 2],
        }
    )
    result = summary(frame, expected_count=5, min_actual_mw=1.0)
    assert result["metrics"]["mae"]["value"] == pytest.approx(11.67, abs=0.01)
    assert result["metrics"]["mae"]["n"] == 3
    assert result["metrics"]["coverage"]["value"] == 60.0
    assert result["population"]["matched_intervals"] == 3
    assert result["population"]["missing_forecast"] == 1
    assert result["population"]["missing_actual"] == 1
    assert result["population"]["mape_excluded"] == 1
    assert result["direction"]["overforecast_count"] == 2
    assert result["direction"]["underforecast_count"] == 1


def test_summary_never_uses_unpaired_rows():
    frame = pd.DataFrame(
        {
            "status": ["missing_actual", "missing_forecast"],
            "actual_mw": [100.0, None],
            "forecast_mw": [110.0, 120.0],
            "error_mw": [10.0, None],
            "absolute_error_mw": [10.0, None],
            "percentage_error": [10.0, None],
            "delivery_date": ["2026-01-01", "2026-01-01"],
            "delivery_start_utc": pd.to_datetime(
                ["2026-01-01T00:00Z", "2026-01-01T00:30Z"], utc=True
            ),
            "publish_time_utc": pd.NaT,
            "lead_time_hours": [14.5, None],
            "lead_time_bucket": ["12to18", None],
            "settlement_period": [1, 2],
            "interval_label": ["a", "b"],
            "eligibility": ["eligible", "missing_forecast"],
            "is_cutoff_compliant": [True, False],
            "cutoff_time_utc": pd.NaT,
            "delivery_end_utc": pd.NaT,
            "local_start": pd.NaT,
            "hour": [0, 0],
        }
    )
    result = summary(frame, expected_count=2, min_actual_mw=1.0)
    assert result["metrics"]["mae"]["n"] == 0
    assert result["metrics"]["mae"]["value"] is None
    assert result["n_observations"] == 0


def test_daily_metrics_include_zero_observation_days():
    frame = pd.DataFrame(
        {
            "status": ["matched"],
            "delivery_date": [pd.Timestamp("2026-01-01").date()],
            "actual_mw": [100.0],
            "forecast_mw": [110.0],
            "error_mw": [10.0],
            "absolute_error_mw": [10.0],
            "hour": [0],
        }
    )
    rows = daily_metrics(
        frame,
        {
            pd.Timestamp("2026-01-01").date(): 48,
            pd.Timestamp("2026-01-02").date(): 48,
        },
        1.0,
    )
    assert len(rows) == 2
    assert rows[0]["mae"] == 10.0
    assert rows[1]["mae"] is None
    assert rows[1]["n"] == 0


def test_error_distribution_has_negative_and_positive_bins():
    distribution = error_distribution(series([-600, -100, 0, 300, 900]))
    assert distribution
    assert any(bin["bin_start"] < 0 for bin in distribution)
    assert any(bin["bin_end"] > 0 for bin in distribution)
    assert sum(bin["count"] for bin in distribution) == 5


def test_error_distribution_empty():
    assert error_distribution(series([])) == []
