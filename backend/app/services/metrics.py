"""Reusable forecast-error analytics.

Metric conventions:
* error_mw        = forecast_mw - actual_mw (positive = overforecast)
* MAE / RMSE      = magnitude of error in MW (never described as accuracy %)
* bias            = mean signed error in MW
* MAPE            = mean(|error| / actual) * 100, excluding |actual| < threshold
* WAPE            = sum(|error|) / sum(actual) * 100
* coverage        = matched intervals / expected delivery intervals * 100

Every metric carries the number of observations used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.domain import LEAD_TIME_BUCKETS, STATUS_MATCHED, lead_time_bucket


@dataclass
class Metric:
    value: float | None
    n: int
    unit: str = "MW"

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "n": self.n, "unit": self.unit}


def _finite(values: pd.Series) -> np.ndarray:
    array = pd.to_numeric(values, errors="coerce").to_numpy(dtype="float64")
    return array[np.isfinite(array)]


def mae(errors: pd.Series) -> Metric:
    values = _finite(errors)
    if values.size == 0:
        return Metric(None, 0)
    return Metric(round(float(np.mean(np.abs(values))), 2), int(values.size))


def rmse(errors: pd.Series) -> Metric:
    values = _finite(errors)
    if values.size == 0:
        return Metric(None, 0)
    return Metric(round(float(np.sqrt(np.mean(np.square(values)))), 2), int(values.size))


def bias(errors: pd.Series) -> Metric:
    values = _finite(errors)
    if values.size == 0:
        return Metric(None, 0)
    return Metric(round(float(np.mean(values)), 2), int(values.size))


def mape(errors: pd.Series, actual: pd.Series, min_actual_mw: float) -> tuple[Metric, int]:
    frame = pd.DataFrame({"e": errors, "a": actual}).dropna()
    frame = frame[np.isfinite(frame["e"]) & np.isfinite(frame["a"])]
    denominator_ok = frame["a"].abs() >= min_actual_mw
    excluded = int((~denominator_ok).sum())
    usable = frame[denominator_ok]
    if usable.empty:
        return Metric(None, 0, "%"), excluded
    values = np.abs(usable["e"].to_numpy()) / np.abs(usable["a"].to_numpy()) * 100.0
    return Metric(round(float(np.mean(values)), 2), int(len(usable)), "%"), excluded


def wape(errors: pd.Series, actual: pd.Series) -> Metric:
    frame = pd.DataFrame({"e": errors, "a": actual}).dropna()
    frame = frame[np.isfinite(frame["e"]) & np.isfinite(frame["a"])]
    if frame.empty:
        return Metric(None, 0, "%")
    denominator = float(frame["a"].abs().sum())
    if denominator <= 0:
        return Metric(None, 0, "%")
    numerator = float(frame["e"].abs().sum())
    return Metric(round(numerator / denominator * 100.0, 2), int(len(frame)), "%")


def coverage(matched_count: int, expected_count: int) -> Metric:
    if expected_count <= 0:
        return Metric(None, 0, "%")
    return Metric(round(matched_count / expected_count * 100.0, 2), matched_count, "%")


def summary(
    frame: pd.DataFrame,
    expected_count: int,
    min_actual_mw: float,
    *,
    excluded_by_lead_time: int = 0,
) -> dict[str, Any]:
    paired = frame[frame["status"] == STATUS_MATCHED]
    errors = paired["error_mw"]
    actual = paired["actual_mw"]
    mae_metric = mae(errors)
    rmse_metric = rmse(errors)
    bias_metric = bias(errors)
    mape_metric, mape_excluded = mape(errors, actual, min_actual_mw)
    wape_metric = wape(errors, actual)
    coverage_metric = coverage(int(len(paired)), int(expected_count))

    finite_errors = _finite(errors)
    if finite_errors.size:
        error_stats = {
            "mean": round(float(np.mean(finite_errors)), 2),
            "median": round(float(np.median(finite_errors)), 2),
            "p95_absolute": round(float(np.percentile(np.abs(finite_errors), 95)), 2),
            "min": round(float(np.min(finite_errors)), 2),
            "max": round(float(np.max(finite_errors)), 2),
        }
    else:
        error_stats = {
            "mean": None,
            "median": None,
            "p95_absolute": None,
            "min": None,
            "max": None,
        }

    over = finite_errors[finite_errors > 0]
    under = finite_errors[finite_errors < 0]
    direction = {
        "overforecast_count": int(over.size),
        "underforecast_count": int(under.size),
        "exact_count": int(finite_errors.size - over.size - under.size),
        "overforecast_total_mw": round(float(over.sum()), 2) if over.size else 0.0,
        "underforecast_total_mw": round(float(under.sum()), 2) if under.size else 0.0,
        "overforecast_share_pct": (
            round(float(over.size) / finite_errors.size * 100.0, 2)
            if finite_errors.size
            else None
        ),
    }

    population = {
        "expected_intervals": int(expected_count),
        "selected_intervals": int(len(frame)),
        "matched_intervals": int(len(paired)),
        "missing_forecast": int((frame["status"] == "missing_forecast").sum()),
        "missing_actual": int((frame["status"] == "missing_actual").sum()),
        "excluded_by_lead_time": int(excluded_by_lead_time),
        "mape_excluded": int(mape_excluded),
        "mape_min_actual_mw": float(min_actual_mw),
    }

    return {
        "metrics": {
            "mae": mae_metric.as_dict(),
            "rmse": rmse_metric.as_dict(),
            "bias": bias_metric.as_dict(),
            "mape": {**mape_metric.as_dict(), "excluded": mape_excluded},
            "wape": wape_metric.as_dict(),
            "coverage": {**coverage_metric.as_dict(), "expected": int(expected_count)},
        },
        "population": population,
        "error_stats": error_stats,
        "direction": direction,
        "distribution": error_distribution(errors),
        "top_overforecast": top_intervals(frame, "over", limit=5),
        "top_underforecast": top_intervals(frame, "under", limit=5),
        "n_observations": int(len(paired)),
    }


def error_distribution(errors: pd.Series, max_bins: int = 28) -> list[dict[str, Any]]:
    values = _finite(errors)
    if values.size == 0:
        return []

    q75, q25 = np.percentile(values, [75, 25])
    iqr = float(q75 - q25)
    if iqr > 0:
        width = 2.0 * iqr / (values.size ** (1.0 / 3.0))
    else:
        width = max(float(np.ptp(values)) / 20.0, 50.0)
    width = float(min(max(round(width / 50.0) * 50.0, 50.0), 2000.0))

    low = math.floor(float(values.min()) / width) * width
    high = math.ceil(float(values.max()) / width) * width
    if low == high:
        high = low + width
    if high - low > width * max_bins:
        width = math.ceil((high - low) / max_bins / 50.0) * 50.0
        low = math.floor(float(values.min()) / width) * width
        high = math.ceil(float(values.max()) / width) * width
    # Keep a bin centred on zero so over/under forecasts are visually separable.
    if low >= 0:
        low = -width
    if high <= 0:
        high = width

    bins = np.arange(low, high + width * 0.5, width)
    counts, edges = np.histogram(values, bins=bins)
    rows: list[dict[str, Any]] = []
    for index, count in enumerate(counts):
        bin_start = float(edges[index])
        bin_end = float(edges[index + 1])
        rows.append(
            {
                "bin_start": round(bin_start, 2),
                "bin_end": round(bin_end, 2),
                "label": f"{bin_start:,.0f} to {bin_end:,.0f}",
                "count": int(count),
                "direction": "over" if bin_start >= 0 else ("under" if bin_end <= 0 else "straddle"),
            }
        )
    return rows


def daily_metrics(
    frame: pd.DataFrame,
    expected_by_date: dict[Any, int],
    min_actual_mw: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paired = frame[frame["status"] == STATUS_MATCHED]
    for day in sorted(expected_by_date):
        subset = paired[paired["delivery_date"] == day]
        expected = expected_by_date[day]
        errors = subset["error_mw"]
        mae_metric = mae(errors)
        rmse_metric = rmse(errors)
        bias_metric = bias(errors)
        mape_metric, _ = mape(errors, subset["actual_mw"], min_actual_mw)
        wape_metric = wape(errors, subset["actual_mw"])
        finite = _finite(errors)
        rows.append(
            {
                "date": day.isoformat() if hasattr(day, "isoformat") else str(day),
                "mae": mae_metric.value,
                "rmse": rmse_metric.value,
                "bias": bias_metric.value,
                "mape": mape_metric.value,
                "wape": wape_metric.value,
                "n": int(len(subset)),
                "expected": int(expected),
                "coverage_pct": (
                    round(len(subset) / expected * 100.0, 2) if expected else None
                ),
                "overforecast_count": int((finite > 0).sum()),
                "underforecast_count": int((finite < 0).sum()),
            }
        )
    return rows


def hourly_metrics(
    frame: pd.DataFrame, dates: list[Any], min_actual_mw: float
) -> dict[str, Any]:
    paired = frame[frame["status"] == STATUS_MATCHED]
    hours: list[dict[str, Any]] = []
    for hour in range(24):
        subset = paired[paired["hour"] == hour]
        errors = subset["error_mw"]
        mae_metric = mae(errors)
        rmse_metric = rmse(errors)
        bias_metric = bias(errors)
        mape_metric, _ = mape(errors, subset["actual_mw"], min_actual_mw)
        hours.append(
            {
                "hour": hour,
                "label": f"{hour:02d}:00",
                "mae": mae_metric.value,
                "rmse": rmse_metric.value,
                "bias": bias_metric.value,
                "mape": mape_metric.value,
                "n": int(len(subset)),
            }
        )

    cells: list[dict[str, Any]] = []
    grouped = (
        paired.groupby(["delivery_date", "hour"])["absolute_error_mw"]
        .agg(mae="mean", n="count")
        .reset_index()
    )
    lookup = {
        (row.delivery_date, int(row.hour)): (float(row.mae), int(row.n))
        for row in grouped.itertuples()
    }
    max_mae = 0.0
    for day in dates:
        for hour in range(24):
            value, count = lookup.get((day, hour), (None, 0))
            if value is not None and value > max_mae:
                max_mae = value
            cells.append(
                {
                    "date": day.isoformat(),
                    "hour": hour,
                    "mae": round(value, 2) if value is not None else None,
                    "n": count,
                }
            )
    return {
        "hours": hours,
        "heatmap": {
            "dates": [day.isoformat() for day in dates],
            "hours": list(range(24)),
            "cells": cells,
            "max_mae": round(max_mae, 2),
        },
    }


def lead_time_metrics(frame: pd.DataFrame, min_actual_mw: float) -> list[dict[str, Any]]:
    paired = frame[frame["status"] == STATUS_MATCHED]
    rows: list[dict[str, Any]] = []
    for key, label, low, high in LEAD_TIME_BUCKETS:
        subset = paired[paired["lead_time_bucket"] == key]
        errors = subset["error_mw"]
        mae_metric = mae(errors)
        rmse_metric = rmse(errors)
        bias_metric = bias(errors)
        mape_metric, _ = mape(errors, subset["actual_mw"], min_actual_mw)
        wape_metric = wape(errors, subset["actual_mw"])
        rows.append(
            {
                "key": key,
                "label": label,
                "min_hours": low,
                "max_hours": high,
                "mae": mae_metric.value,
                "rmse": rmse_metric.value,
                "bias": bias_metric.value,
                "mape": mape_metric.value,
                "wape": wape_metric.value,
                "n": int(len(subset)),
            }
        )
    return rows


def revision_curve(
    vintages: pd.DataFrame,
    decision: pd.DataFrame,
    min_actual_mw: float | None = None,
) -> list[dict[str, Any]]:
    """Mean forecast level and revision vs the decision-time forecast.

    ``vintages`` contains every pre-delivery forecast row for the selected
    intervals; ``decision`` contains one row per interval with the selected
    decision forecast.
    """
    if vintages.empty or decision.empty:
        return []
    base = decision[["delivery_start_utc", "forecast_mw", "actual_mw"]].rename(
        columns={"forecast_mw": "decision_mw", "actual_mw": "actual_mw"}
    )
    merged = vintages.merge(base, on="delivery_start_utc", how="inner")
    if merged.empty:
        return []
    merged["delta_vs_decision"] = merged["forecast_mw"] - merged["decision_mw"]
    merged["abs_delta_vs_decision"] = merged["delta_vs_decision"].abs()
    merged["lead_time_bucket"] = merged["lead_time_hours"].map(lead_time_bucket)

    rows: list[dict[str, Any]] = []
    for key, label, low, high in LEAD_TIME_BUCKETS:
        subset = merged[merged["lead_time_bucket"] == key]
        rows.append(
            {
                "key": key,
                "label": label,
                "min_hours": low,
                "max_hours": high,
                "mean_forecast_mw": (
                    round(float(subset["forecast_mw"].mean()), 2) if len(subset) else None
                ),
                "mean_decision_mw": (
                    round(float(subset["decision_mw"].mean()), 2) if len(subset) else None
                ),
                "mean_delta_vs_decision_mw": (
                    round(float(subset["delta_vs_decision"].mean()), 2) if len(subset) else None
                ),
                "mean_abs_revision_mw": (
                    round(float(subset["abs_delta_vs_decision"].mean()), 2)
                    if len(subset)
                    else None
                ),
                "mean_lead_time_hours": (
                    round(float(subset["lead_time_hours"].mean()), 2) if len(subset) else None
                ),
                "n": int(len(subset)),
            }
        )
    return rows


def top_intervals(frame: pd.DataFrame, direction: str, limit: int = 5) -> list[dict[str, Any]]:
    paired = frame[frame["status"] == STATUS_MATCHED]
    if direction == "over":
        subset = paired[paired["error_mw"] > 0].nlargest(limit, "error_mw")
    else:
        subset = paired[paired["error_mw"] < 0].nsmallest(limit, "error_mw")
    return [interval_record(row) for row in subset.itertuples()]


def interval_record(row: Any) -> dict[str, Any]:
    def clean(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if pd.isna(value):
            return None
        return value

    return {
        "delivery_interval": _iso(getattr(row, "delivery_start_utc", None)),
        "delivery_date": _date(getattr(row, "delivery_date", None)),
        "settlement_period": int(row.settlement_period),
        "interval_label": row.interval_label,
        "forecast_mw": _round(clean(getattr(row, "forecast_mw", None))),
        "actual_mw": _round(clean(getattr(row, "actual_mw", None))),
        "error_mw": _round(clean(getattr(row, "error_mw", None))),
        "absolute_error_mw": _round(clean(getattr(row, "absolute_error_mw", None))),
        "percentage_error": _round(clean(getattr(row, "percentage_error", None))),
        "publish_time": _iso(getattr(row, "publish_time_utc", None)),
        "lead_time_hours": _round(clean(getattr(row, "lead_time_hours", None))),
        "eligibility": getattr(row, "eligibility", None),
        "status": getattr(row, "status", None),
    }


def _round(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, 2)


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        text = value.isoformat()
        return text.replace("+00:00", "Z")
    return str(value)


def _date(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def series_from_frame(
    frame: pd.DataFrame, resolution: str, tz: ZoneInfo
) -> list[dict[str, Any]]:
    """Downsample the selected interval series for chart display.

    Metrics are always computed on full-resolution data; this only affects the
    visualisation payload and is labelled in the UI.
    """
    if frame.empty:
        return []
    working = frame.copy()
    local = working["delivery_start_utc"].dt.tz_convert(tz)
    if resolution == "1d":
        working["bucket"] = local.dt.floor("D")
    elif resolution == "1h":
        working["bucket"] = local.dt.floor("h")
    else:
        working["bucket"] = working["delivery_start_utc"]

    grouped = (
        working.groupby("bucket", sort=True)
        .agg(
            forecast_mw=("forecast_mw", "mean"),
            actual_mw=("actual_mw", "mean"),
            error_mw=("error_mw", "mean"),
            absolute_error_mw=("absolute_error_mw", "mean"),
            n=("delivery_start_utc", "count"),
        )
        .reset_index()
    )
    rows: list[dict[str, Any]] = []
    for row in grouped.itertuples():
        rows.append(
            {
                "timestamp": _iso(row.bucket),
                "forecast_mw": _round(row.forecast_mw) if pd.notna(row.forecast_mw) else None,
                "actual_mw": _round(row.actual_mw) if pd.notna(row.actual_mw) else None,
                "error_mw": _round(row.error_mw) if pd.notna(row.error_mw) else None,
                "absolute_error_mw": (
                    _round(row.absolute_error_mw) if pd.notna(row.absolute_error_mw) else None
                ),
                "n": int(row.n),
            }
        )
    return rows
