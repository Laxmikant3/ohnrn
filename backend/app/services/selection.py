"""Forecast eligibility and vintage selection.

The single most important rule in WindIQ: a forecast may only enter a historical
decision analysis if it was published at or before the procurement cutoff for
that delivery date. The default cutoff is 11:00 Europe/London on the preceding
calendar day (a documented pilot assumption, not a market deadline).

Selection never backfills a missing eligible forecast with a later publication.
"""

from __future__ import annotations

import datetime as dt
import functools
import logging

import pandas as pd

from app.config import Settings
from app.domain import (
    ELIGIBILITY_ELIGIBLE,
    ELIGIBILITY_MISSING,
    ELIGIBILITY_RETROSPECTIVE,
    STATUS_MATCHED,
    STATUS_MISSING_ACTUAL,
    STATUS_MISSING_FORECAST,
    VINTAGE_LATEST,
    lead_time_bucket,
)
from app.services.dataset import Dataset
from app.utils.timeutils import build_delivery_grid, cutoff_for_delivery_date

logger = logging.getLogger("windiq.selection")


@functools.lru_cache(maxsize=16)
def _grid_cached(start: dt.date, end: dt.date, tz_key: str) -> pd.DataFrame:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_key)
    intervals = build_delivery_grid(start, end, tz)
    frame = pd.DataFrame(
        {
            "delivery_start_utc": [i.start_utc for i in intervals],
            "delivery_end_utc": [i.end_utc for i in intervals],
            "delivery_date": [i.delivery_date for i in intervals],
            "settlement_period": [i.settlement_period for i in intervals],
            "interval_label": [i.label for i in intervals],
            "local_start": [i.local_start for i in intervals],
        }
    )
    frame["hour"] = frame["local_start"].dt.hour
    return frame


def build_grid(settings: Settings, start: dt.date, end: dt.date) -> pd.DataFrame:
    return _grid_cached(start, end, settings.market_timezone).copy()


@functools.lru_cache(maxsize=64)
def _cutoff_cached(
    delivery_date: dt.date, tz_key: str, cutoff_time: str, days_before: int
) -> dt.datetime:
    from zoneinfo import ZoneInfo

    return cutoff_for_delivery_date(
        delivery_date, ZoneInfo(tz_key), dt.time.fromisoformat(cutoff_time), days_before
    )


def cutoffs_for_dates(
    dates: pd.Series, settings: Settings, cutoff_time: str, days_before: int
) -> dict[dt.date, dt.datetime]:
    values = sorted(set(dates.tolist()))
    return {
        value: _cutoff_cached(value, settings.market_timezone, cutoff_time, days_before)
        for value in values
    }


def build_selection(
    dataset: Dataset,
    settings: Settings,
    start: dt.date,
    end: dt.date,
    cutoff_time: str,
    cutoff_days_before: int,
    vintage: str,
) -> pd.DataFrame:
    """Return one row per expected delivery interval with selected forecast.

    Columns include the auditable ``publish_time_utc``, the computed
    ``cutoff_time_utc``, eligibility and join status. Missing eligible forecasts
    remain in the frame with null forecast values.
    """
    grid = build_grid(settings, start, end)
    cutoffs = cutoffs_for_dates(
        grid["delivery_date"], settings, cutoff_time, cutoff_days_before
    )
    grid["cutoff_time_utc"] = grid["delivery_date"].map(cutoffs)

    if dataset.forecast.empty:
        frame = grid.copy()
        frame["publish_time_utc"] = pd.NaT
        frame["forecast_mw"] = float("nan")
    else:
        forecasts = dataset.forecast[
            ["delivery_start_utc", "publish_time_utc", "forecast_mw"]
        ].copy()
        forecasts = forecasts.merge(
            grid[["delivery_start_utc", "delivery_date", "cutoff_time_utc"]],
            on="delivery_start_utc",
            how="inner",
        )
        if vintage == VINTAGE_LATEST:
            candidates = forecasts
        else:
            candidates = forecasts[
                forecasts["publish_time_utc"] <= forecasts["cutoff_time_utc"]
            ]
        # Greatest publishTime wins. Sorting is stable and the final row for a
        # delivery interval is therefore the latest eligible vintage.
        candidates = candidates.sort_values(
            ["delivery_start_utc", "publish_time_utc"], kind="mergesort"
        )
        selected = candidates.drop_duplicates(subset=["delivery_start_utc"], keep="last")
        frame = grid.merge(
            selected[["delivery_start_utc", "publish_time_utc", "forecast_mw"]],
            on="delivery_start_utc",
            how="left",
        )

    if dataset.actual.empty:
        frame["actual_mw"] = float("nan")
    else:
        actual = dataset.actual[["delivery_start_utc", "actual_mw"]].copy()
        frame = frame.merge(actual, on="delivery_start_utc", how="left")

    frame["forecast_mw"] = pd.to_numeric(frame["forecast_mw"], errors="coerce")
    frame["actual_mw"] = pd.to_numeric(frame["actual_mw"], errors="coerce")
    frame["error_mw"] = frame["forecast_mw"] - frame["actual_mw"]
    frame["absolute_error_mw"] = frame["error_mw"].abs()
    denominator_ok = frame["actual_mw"].abs() >= settings.mape_min_actual_mw
    frame["percentage_error"] = (
        (frame["error_mw"] / frame["actual_mw"].where(frame["actual_mw"] != 0)) * 100.0
    ).where(denominator_ok)
    frame["lead_time_hours"] = (
        frame["delivery_start_utc"] - frame["publish_time_utc"]
    ).dt.total_seconds() / 3600.0
    frame["lead_time_hours"] = frame["lead_time_hours"].round(3)
    frame["lead_time_bucket"] = frame["lead_time_hours"].map(
        lambda value: lead_time_bucket(value) if pd.notna(value) else None
    )

    has_forecast = frame["forecast_mw"].notna()
    has_actual = frame["actual_mw"].notna()
    if vintage == VINTAGE_LATEST:
        frame["eligibility"] = ELIGIBILITY_RETROSPECTIVE
        compliant = has_forecast & (
            frame["publish_time_utc"] <= frame["cutoff_time_utc"]
        )
        frame.loc[~has_forecast, "eligibility"] = ELIGIBILITY_MISSING
        frame.loc[compliant, "eligibility"] = ELIGIBILITY_ELIGIBLE
    else:
        frame["eligibility"] = ELIGIBILITY_MISSING
        frame.loc[has_forecast, "eligibility"] = ELIGIBILITY_ELIGIBLE

    frame["status"] = STATUS_MISSING_FORECAST
    frame.loc[has_forecast & ~has_actual, "status"] = STATUS_MISSING_ACTUAL
    frame.loc[has_forecast & has_actual, "status"] = STATUS_MATCHED
    frame["is_cutoff_compliant"] = (
        frame["publish_time_utc"].notna()
        & (frame["publish_time_utc"] <= frame["cutoff_time_utc"])
    )

    frame["delivery_date"] = pd.to_datetime(frame["delivery_date"]).dt.date
    frame = frame.sort_values("delivery_start_utc").reset_index(drop=True)
    return frame


def matched(frame: pd.DataFrame) -> pd.DataFrame:
    """Paired observations only — never compute metrics from unpaired rows."""
    return frame[frame["status"] == STATUS_MATCHED].copy()


def interval_vintages(
    dataset: Dataset,
    settings: Settings,
    interval_start: dt.datetime,
    cutoff_time: str,
    cutoff_days_before: int,
) -> pd.DataFrame:
    """All pre-delivery vintages for one delivery interval.

    Post-delivery publications are excluded during normalisation, so every row
    here was published before the interval started. Eligibility is evaluated
    against the same cutoff used for selection.
    """
    from app.utils.timeutils import UTC, parse_api_timestamp

    start = parse_api_timestamp(interval_start)
    if start is None:
        raise ValueError("Invalid delivery interval")
    start = start.astimezone(UTC)
    grid = build_grid(settings, settings.analysis_start, settings.analysis_end)
    row = grid[grid["delivery_start_utc"] == pd.Timestamp(start)]
    if row.empty:
        raise LookupError("Delivery interval is outside the loaded analysis period")
    delivery_date = row.iloc[0]["delivery_date"]
    cutoff = cutoffs_for_dates(pd.Series([delivery_date]), settings, cutoff_time, cutoff_days_before)[
        delivery_date
    ]

    if dataset.forecast.empty:
        return pd.DataFrame(
            columns=["publish_time_utc", "forecast_mw", "lead_time_hours", "eligible"]
        )
    vintages = dataset.forecast[
        dataset.forecast["delivery_start_utc"] == pd.Timestamp(start)
    ][["publish_time_utc", "forecast_mw"]].copy()
    vintages = vintages.sort_values("publish_time_utc").drop_duplicates(
        subset=["publish_time_utc"], keep="last"
    )
    vintages["eligible"] = vintages["publish_time_utc"] <= cutoff
    vintages["lead_time_hours"] = (
        (pd.Timestamp(start) - vintages["publish_time_utc"]).dt.total_seconds() / 3600.0
    ).round(3)
    vintages["cutoff_time_utc"] = cutoff
    return vintages.reset_index(drop=True)
