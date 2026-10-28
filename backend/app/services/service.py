"""Application service layer.

Routes stay thin: this module owns dataset validation, cutoff-aware selection,
metrics composition, data-quality reporting and metadata.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import logging
import threading
import time
from collections import OrderedDict
from typing import Any

import pandas as pd

from app.clients.elexon import ElexonClient
from app.config import Settings
from app.domain import (
    LEAD_TIME_BUCKETS,
    SOURCE_ACTUAL,
    SOURCE_FORECAST,
    STATUS_MATCHED,
    STATUS_MISSING_ACTUAL,
    STATUS_MISSING_FORECAST,
    VINTAGE_LATEST,
    lead_time_bucket_label,
)
from app.services import metrics as metrics_lib
from app.services.cache import CacheStore
from app.services.dataset import Dataset, DatasetStore
from app.services.ingestion import ingest_window
from app.services.selection import build_grid, build_selection, cutoffs_for_dates
from app.utils.timeutils import UTC, iso_z, parse_api_timestamp

logger = logging.getLogger("windiq.service")

METRIC_DEFINITIONS: list[dict[str, str]] = [
    {
        "key": "mae",
        "label": "Mean Absolute Error (MAE)",
        "unit": "MW",
        "formula": "mean(|forecast_mw - actual_mw|)",
        "description": "Average magnitude of forecast error in megawatts. Lower is better; not a percentage.",
    },
    {
        "key": "rmse",
        "label": "Root Mean Squared Error (RMSE)",
        "unit": "MW",
        "formula": "sqrt(mean((forecast_mw - actual_mw)^2))",
        "description": "Penalises larger errors more heavily than MAE. Lower is better; not a percentage.",
    },
    {
        "key": "bias",
        "label": "Mean Error (Bias)",
        "unit": "MW",
        "formula": "mean(forecast_mw - actual_mw)",
        "description": "Positive values indicate overforecasting; negative values indicate underforecasting.",
    },
    {
        "key": "mape",
        "label": "Mean Absolute Percentage Error (MAPE)",
        "unit": "%",
        "formula": "mean(|error_mw / actual_mw|) x 100",
        "description": "Calculated only where |actual_mw| >= the configured denominator threshold. Excluded observations are reported.",
    },
    {
        "key": "wape",
        "label": "Weighted Absolute Percentage Error (WAPE)",
        "unit": "%",
        "formula": "sum(|error_mw|) / sum(actual_mw) x 100",
        "description": "Volume-weighted aggregate error; robust to low-generation intervals that distort MAPE.",
    },
    {
        "key": "coverage",
        "label": "Forecast coverage",
        "unit": "%",
        "formula": "matched_intervals / expected_delivery_intervals x 100",
        "description": "Share of expected 30-minute settlement periods with both an eligible forecast and an actual value.",
    },
]


class DataUnavailableError(RuntimeError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class OutOfRangeError(RuntimeError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class NotFoundError(RuntimeError):
    pass


class RefreshDisabledError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class QueryFilters:
    start_date: dt.date
    end_date: dt.date
    cutoff: str
    cutoff_days_before: int
    vintage: str = "decision_cutoff"
    lead_time_bucket: str | None = None


class WindIQService:
    def __init__(
        self,
        settings: Settings,
        cache: CacheStore | None = None,
        dataset_store: DatasetStore | None = None,
        client: ElexonClient | None = None,
    ) -> None:
        self.settings = settings
        self.cache = cache or CacheStore(settings)
        self.datasets = dataset_store or DatasetStore(settings, self.cache)
        self.client = client or ElexonClient(settings)
        self._selection_cache: OrderedDict[tuple[Any, ...], pd.DataFrame] = OrderedDict()
        self._selection_lock = threading.Lock()
        self._probe: dict[str, Any] | None = None
        self._probe_at: float = 0.0
        self._probe_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------
    def dataset(self) -> Dataset:
        return self.datasets.get()

    def available_range(self) -> dict[str, Any]:
        dataset = self.dataset()
        return {
            "actual_start": dataset.actual_dates[0] if dataset.actual_dates else None,
            "actual_end": dataset.actual_dates[1] if dataset.actual_dates else None,
            "forecast_start": dataset.forecast_dates[0] if dataset.forecast_dates else None,
            "forecast_end": dataset.forecast_dates[1] if dataset.forecast_dates else None,
            "configured_start": self.settings.analysis_start,
            "configured_end": self.settings.analysis_end,
        }

    def _validate_range(self, filters: QueryFilters) -> Dataset:
        dataset = self.dataset()
        if dataset.actual.empty:
            raise DataUnavailableError(
                "No actual generation dataset is loaded. Run the documented data-load "
                "command to retrieve FUELHH data for January 2026.",
                {"available": False, "load_error": dataset.load_error},
            )
        if dataset.forecast.empty:
            raise DataUnavailableError(
                "No WINDFOR forecast dataset is loaded. Historical forecast selection "
                "cannot proceed without real Elexon forecast records.",
                {"available": False, "load_error": dataset.load_error},
            )
        if filters.end_date < filters.start_date:
            raise OutOfRangeError("end_date must be on or after start_date")
        actual_start, actual_end = dataset.actual_dates or (None, None)
        if actual_start is None or actual_end is None or filters.start_date < actual_start or filters.end_date > actual_end:
            raise OutOfRangeError(
                "Requested period is outside the loaded January 2026 dataset.",
                {
                    "available_start": actual_start,
                    "available_end": actual_end,
                    "requested_start": filters.start_date,
                    "requested_end": filters.end_date,
                },
            )
        return dataset

    def selection(self, filters: QueryFilters) -> pd.DataFrame:
        dataset = self._validate_range(filters)
        key = (
            dataset.signature,
            filters.start_date,
            filters.end_date,
            filters.cutoff,
            filters.cutoff_days_before,
            filters.vintage,
        )
        with self._selection_lock:
            cached = self._selection_cache.get(key)
            if cached is not None:
                self._selection_cache.move_to_end(key)
                return cached.copy()
        frame = build_selection(
            dataset,
            self.settings,
            filters.start_date,
            filters.end_date,
            filters.cutoff,
            filters.cutoff_days_before,
            filters.vintage,
        )
        with self._selection_lock:
            self._selection_cache[key] = frame
            while len(self._selection_cache) > 24:
                self._selection_cache.popitem(last=False)
        return frame.copy()

    def _filtered(self, frame: pd.DataFrame, bucket: str | None) -> tuple[pd.DataFrame, int]:
        if not bucket:
            return frame, 0
        mask = frame["lead_time_bucket"] == bucket
        excluded = int(((frame["status"] == STATUS_MATCHED) & ~mask).sum())
        return frame[mask].copy(), excluded

    # ------------------------------------------------------------------
    # Shared context
    # ------------------------------------------------------------------
    def cutoff_info(self, filters: QueryFilters) -> dict[str, Any]:
        example = filters.end_date
        example_cutoff = cutoffs_for_dates(
            pd.Series([example]), self.settings, filters.cutoff, filters.cutoff_days_before
        )[example]
        return {
            "time": filters.cutoff,
            "days_before": filters.cutoff_days_before,
            "timezone": self.settings.market_timezone,
            "description": (
                f"Forecasts are eligible only if published at or before {filters.cutoff} "
                f"{self.settings.market_timezone} on the calendar day {filters.cutoff_days_before} "
                "day(s) before delivery. This is a configurable pilot assumption, not a "
                "universal market deadline."
            ),
            "example_delivery_date": example.isoformat(),
            "example_cutoff_utc": iso_z(example_cutoff),
            "assumption": True,
        }

    def period_info(self, filters: QueryFilters, expected: int) -> dict[str, Any]:
        return {
            "start_date": filters.start_date.isoformat(),
            "end_date": filters.end_date.isoformat(),
            "label": _period_label(filters.start_date, filters.end_date),
            "timezone": self.settings.market_timezone,
            "expected_intervals": expected,
            "mode": "historical_analysis",
        }

    def _data_status(self, dataset: Dataset) -> dict[str, Any]:
        retrieved = dataset.retrieved_at
        age_hours = (
            round((dt.datetime.now(UTC) - retrieved).total_seconds() / 3600.0, 2)
            if retrieved
            else None
        )
        stale = bool(
            age_hours is not None and age_hours > self.settings.cache_stale_after_hours
        )
        return {
            "mode": "historical_analysis",
            "source": "Elexon BMRS (cached)",
            "cached": True,
            "stale": stale,
            "is_synthetic": dataset.is_synthetic,
            "last_retrieval": iso_z(retrieved),
            "cache_age_hours": age_hours,
            "stale_after_hours": self.settings.cache_stale_after_hours,
            "actual_records": int(len(dataset.actual)),
            "forecast_records": int(
                len(
                    dataset.forecast.drop_duplicates(
                        ["source_start_utc", "publish_time_utc"]
                    )
                )
            ),
            "forecast_delivery_intervals": int(dataset.forecast["source_start_utc"].nunique())
            if not dataset.forecast.empty
            else 0,
            "forecast_expanded_intervals": int(dataset.forecast["delivery_start_utc"].nunique())
            if not dataset.forecast.empty
            else 0,
            "forecast_vintages": int(dataset.forecast["publish_time_utc"].nunique())
            if not dataset.forecast.empty
            else 0,
            "forecast_granularity_minutes": dataset.forecast_granularity_minutes,
            "forecast_expanded_to_half_hourly": dataset.forecast_granularity_minutes > 30,
        }

    async def probe(self, force: bool = False) -> dict[str, Any]:
        if not force and self._probe is not None and (time.monotonic() - self._probe_at) < self.settings.upstream_probe_ttl_seconds:
            return self._probe
        async with self._probe_lock:
            if not force and self._probe is not None and (time.monotonic() - self._probe_at) < self.settings.upstream_probe_ttl_seconds:
                return self._probe
            result = await self.client.probe()
            self._probe = result
            self._probe_at = time.monotonic()
            return result

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------
    async def health(self, probe: bool = True) -> dict[str, Any]:
        dataset = self.dataset()
        source = await self.probe() if probe else self._probe
        loaded = dataset.loaded
        status = "ok" if loaded else "degraded"
        if source and not source.get("reachable"):
            status = "degraded" if not loaded else status
        return {
            "status": status,
            "service": self.settings.app_name,
            "version": self.settings.app_version,
            "time_utc": iso_z(dt.datetime.now(UTC)),
            "dataset_loaded": loaded,
            "data": self._data_status(dataset),
            "elexon": source
            or {
                "checked": False,
                "reachable": None,
                "status_code": None,
                "latency_ms": None,
                "checked_at": None,
                "detail": "Upstream probe not requested",
            },
            "checks": {
                "actual_dataset": not dataset.actual.empty,
                "forecast_dataset": not dataset.forecast.empty,
                "cache_present": self.cache.exists(),
                "synthetic_data_present": dataset.is_synthetic,
            },
        }

    def metadata(self) -> dict[str, Any]:
        dataset = self.dataset()
        available = self.available_range()
        return {
            "product": {
                "name": "WindIQ — Renewable Forecast Intelligence",
                "version": self.settings.app_version,
                "description": "UK national wind generation forecast intelligence for day-ahead procurement analysis.",
                "mode": "historical_analysis",
                "timezone": self.settings.market_timezone,
            },
            "analysis_period": {
                "start_date": self.settings.analysis_start.isoformat(),
                "end_date": self.settings.analysis_end.isoformat(),
                "label": _period_label(self.settings.analysis_start, self.settings.analysis_end),
                "focus": "January 2026",
                "available_start": available["actual_start"].isoformat() if available["actual_start"] else None,
                "available_end": available["actual_end"].isoformat() if available["actual_end"] else None,
            },
            "cutoff": {
                "time": self.settings.default_cutoff_time,
                "days_before": self.settings.default_cutoff_days_before,
                "timezone": self.settings.market_timezone,
                "assumption": True,
                "description": (
                    "Pilot assumption: the day-ahead procurement decision is taken at "
                    f"{self.settings.default_cutoff_time} {self.settings.market_timezone} on the "
                    "preceding calendar day. Forecasts published after this instant are "
                    "excluded from decision analysis."
                ),
            },
            "sources": [
                {
                    "dataset": SOURCE_ACTUAL,
                    "name": "Half-hourly generation outturn by fuel type",
                    "endpoint": f"{self.settings.elexon_base_url}/datasets/FUELHH/stream",
                    "documentation_url": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream",
                    "parameters": [
                        "fuelType=WIND",
                        "settlementDateFrom",
                        "settlementDateTo",
                    ],
                    "fields_used": {
                        "startTime": "delivery interval start (UTC)",
                        "publishTime": "retrieval/publication timestamp (UTC)",
                        "settlementDate": "market settlement date",
                        "settlementPeriod": "settlement period 1–50",
                        "generation": "actual generation in MW (int64)",
                    },
                    "granularity_minutes": 30,
                    "unit": "MW",
                    "authentication": "None (public API)",
                    "pagination": "None — single JSON array per request",
                    "rate_limit": "HTTP 429 documented; no numeric quota published",
                },
                {
                    "dataset": SOURCE_FORECAST,
                    "name": "Wind generation forecast",
                    "endpoint": f"{self.settings.elexon_base_url}/datasets/WINDFOR/stream",
                    "documentation_url": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream",
                    "parameters": [
                        "publishDateTimeFrom",
                        "publishDateTimeTo",
                    ],
                    "fields_used": {
                        "startTime": "forecast delivery start (UTC, hourly in the observed feed)",
                        "publishTime": "forecast publication timestamp (UTC)",
                        "generation": "forecast generation in MW (int64)",
                    },
                    "granularity_minutes": dataset.forecast_granularity_minutes,
                    "unit": "MW",
                    "authentication": "None (public API)",
                    "pagination": "None — single JSON array per request",
                    "rate_limit": "HTTP 429 documented; no numeric quota published",
                },
            ],
            "data": self._data_status(dataset),
            "metrics": {
                "mape_min_actual_mw": self.settings.mape_min_actual_mw,
                "definitions": METRIC_DEFINITIONS,
                "lead_time_buckets": [
                    {"key": key, "label": label, "min_hours": low, "max_hours": high}
                    for key, label, low, high in LEAD_TIME_BUCKETS
                ],
                "coverage_definition": (
                    "Matched intervals divided by expected 30-minute delivery intervals in the "
                    "selected London date range."
                ),
            },
            "limitations": _limitations(),
        }

    def overview(self, filters: QueryFilters, resolution: str = "1h") -> dict[str, Any]:
        frame = self.selection(filters)
        expected = int(len(frame))
        summary = metrics_lib.summary(
            frame, expected, self.settings.mape_min_actual_mw
        )
        dataset = self.dataset()
        dated = frame.dropna(subset=["delivery_start_utc"]).copy()
        latest_forecast_row = _latest_row(dated, require_forecast=True)
        latest_actual_row = _latest_row(dated, require_actual=True)
        latest_matched_row = _latest_row(
            dated[dated["status"] == STATUS_MATCHED], require_forecast=True
        )
        expected_by_date = (
            frame.groupby("delivery_date").size().to_dict()
        )
        daily = metrics_lib.daily_metrics(
            frame, expected_by_date, self.settings.mape_min_actual_mw
        )
        curve = self._revision_curve(frame)

        return {
            "mode": "historical_analysis",
            "period": self.period_info(filters, expected),
            "cutoff": self.cutoff_info(filters),
            "filters": _filters_dict(filters),
            "data_status": self._data_status(dataset),
            "kpis": {
                "latest_eligible_forecast": _latest_forecast_kpi(latest_forecast_row),
                "latest_actual": _latest_actual_kpi(latest_actual_row),
                "latest_error": _latest_error_kpi(latest_matched_row),
                "mae": summary["metrics"]["mae"],
                "rmse": summary["metrics"]["rmse"],
                "coverage": summary["metrics"]["coverage"],
                "bias": summary["metrics"]["bias"],
            },
            "population": summary["population"],
            "series": metrics_lib.series_from_frame(frame, resolution, self.settings.timezone),
            "series_resolution": resolution,
            "daily": daily,
            "revision_curve": curve,
            "top_overforecast": summary["top_overforecast"],
            "top_underforecast": summary["top_underforecast"],
            "procurement_context": _procurement_context(),
        }

    def forecast_page(
        self,
        filters: QueryFilters,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
        search: str | None,
        status: str | None,
    ) -> dict[str, Any]:
        base = self.selection(filters)
        filtered, excluded = self._filtered(base, filters.lead_time_bucket)
        population = _population(filtered, int(len(base)), excluded)

        working = filtered
        if status and status != "all":
            working = working[working["status"] == status]
        if search:
            needle = search.strip().lower()
            mask = (
                working["delivery_date"].astype(str).str.contains(needle, na=False)
                | working["interval_label"].str.contains(needle, na=False)
                | working["settlement_period"].astype(str).str.contains(needle, na=False)
                | working["delivery_start_utc"].astype(str).str.contains(needle, na=False)
                | working["status"].str.contains(needle, na=False)
            )
            working = working[mask]

        sort_columns = {
            "delivery_interval": "delivery_start_utc",
            "delivery_date": "delivery_start_utc",
            "settlement_period": "settlement_period",
            "forecast_mw": "forecast_mw",
            "actual_mw": "actual_mw",
            "error_mw": "error_mw",
            "absolute_error_mw": "absolute_error_mw",
            "publish_time": "publish_time_utc",
            "lead_time_hours": "lead_time_hours",
            "status": "status",
        }
        column = sort_columns.get(sort_by, "delivery_start_utc")
        ascending = sort_dir != "desc"
        working = working.sort_values(column, ascending=ascending, na_position="last")

        total = int(len(working))
        total_pages = max(1, (total + page_size - 1) // page_size) if total else 0
        page = min(page, total_pages) if total_pages else 1
        start = (page - 1) * page_size
        items = [
            forecast_row(row) for row in working.iloc[start : start + page_size].itertuples()
        ]

        return {
            "period": self.period_info(filters, int(len(base))),
            "cutoff": self.cutoff_info(filters),
            "filters": _filters_dict(filters),
            "population": population,
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1,
            },
            "sort": {"by": sort_by, "direction": "desc" if not ascending else "asc"},
        }

    def vintages(
        self,
        interval_start: dt.datetime,
        cutoff: str,
        cutoff_days_before: int,
    ) -> dict[str, Any]:
        dataset = self.dataset()
        start = parse_api_timestamp(interval_start)
        if start is None:
            raise NotFoundError("Invalid delivery interval")
        grid = build_grid(self.settings, self.settings.analysis_start, self.settings.analysis_end)
        row = grid[grid["delivery_start_utc"] == pd.Timestamp(start)]
        if row.empty:
            raise NotFoundError(
                "Delivery interval is outside the January 2026 analysis period"
            )
        delivery_row = row.iloc[0]
        delivery_date = delivery_row["delivery_date"]
        cutoff_utc = cutoffs_for_dates(
            pd.Series([delivery_date]), self.settings, cutoff, cutoff_days_before
        )[delivery_date]

        actual_value = None
        if not dataset.actual.empty:
            match = dataset.actual[dataset.actual["delivery_start_utc"] == pd.Timestamp(start)]
            if not match.empty:
                actual_value = round(float(match.iloc[0]["actual_mw"]), 2)

        vintages = dataset.forecast[
            dataset.forecast["delivery_start_utc"] == pd.Timestamp(start)
        ][["publish_time_utc", "forecast_mw"]].copy()
        vintages = vintages.sort_values("publish_time_utc").drop_duplicates(
            subset=["publish_time_utc"], keep="last"
        )
        vintages["eligible"] = vintages["publish_time_utc"] <= cutoff_utc
        vintages["lead_time_hours"] = (
            (pd.Timestamp(start) - vintages["publish_time_utc"]).dt.total_seconds() / 3600.0
        ).round(3)
        vintages["revision_mw"] = vintages["forecast_mw"].diff().round(2)
        vintages["revision_from_decision_mw"] = float("nan")
        vintages["is_selected"] = False

        eligible = vintages[vintages["eligible"]]
        decision_publish = None
        decision_value = None
        if not eligible.empty:
            decision_publish = eligible.iloc[-1]["publish_time_utc"]
            decision_value = float(eligible.iloc[-1]["forecast_mw"])
            vintages.loc[eligible.index[-1], "is_selected"] = True
            vintages["revision_from_decision_mw"] = (
                vintages["forecast_mw"] - decision_value
            ).round(2)

        latest_value = (
            float(vintages.iloc[-1]["forecast_mw"]) if not vintages.empty else None
        )
        latest_publish = vintages.iloc[-1]["publish_time_utc"] if not vintages.empty else None
        latest_eligible_publish = decision_publish

        items = []
        for row_item in vintages.itertuples():
            items.append(
                {
                    "publish_time": _iso(row_item.publish_time_utc),
                    "forecast_mw": round(float(row_item.forecast_mw), 2),
                    "lead_time_hours": float(row_item.lead_time_hours),
                    "eligible": bool(row_item.eligible),
                    "selected": bool(row_item.is_selected),
                    "revision_from_previous_mw": (
                        None if pd.isna(row_item.revision_mw) else float(row_item.revision_mw)
                    ),
                    "revision_from_decision_mw": (
                        None
                        if pd.isna(row_item.revision_from_decision_mw)
                        else float(row_item.revision_from_decision_mw)
                    ),
                }
            )

        return {
            "delivery_interval": iso_z(start),
            "delivery_date": delivery_date.isoformat(),
            "settlement_period": int(delivery_row["settlement_period"]),
            "interval_label": delivery_row["interval_label"],
            "market_timezone": self.settings.market_timezone,
            "cutoff": {
                "time": cutoff,
                "days_before": cutoff_days_before,
                "timezone": self.settings.market_timezone,
                "cutoff_utc": iso_z(cutoff_utc),
            },
            "actual_mw": actual_value,
            "decision_forecast": {
                "forecast_mw": decision_value,
                "publish_time": _iso(decision_publish),
                "eligible": decision_value is not None,
                "error_mw": (
                    round(decision_value - actual_value, 2)
                    if decision_value is not None and actual_value is not None
                    else None
                ),
            },
            "latest_forecast": {
                "forecast_mw": latest_value,
                "publish_time": _iso(latest_publish),
            },
            "revision": {
                "latest_minus_decision_mw": (
                    round(latest_value - decision_value, 2)
                    if latest_value is not None and decision_value is not None
                    else None
                ),
                "latest_minus_actual_mw": (
                    round(latest_value - actual_value, 2)
                    if latest_value is not None and actual_value is not None
                    else None
                ),
                "n_vintages": int(len(vintages)),
                "n_eligible_vintages": int(len(eligible)),
                "latest_eligible_publish_time": _iso(latest_eligible_publish),
            },
            "vintages": items,
            "retrospective_notice": (
                "Vintages published after the decision cutoff and the final actual are shown "
                "for retrospective evaluation only. They were not available at the decision time."
            ),
        }

    def summary_analytics(self, filters: QueryFilters) -> dict[str, Any]:
        base = self.selection(filters)
        filtered, excluded = self._filtered(base, filters.lead_time_bucket)
        expected = int(len(base))
        summary = metrics_lib.summary(
            filtered, expected, self.settings.mape_min_actual_mw, excluded_by_lead_time=excluded
        )
        return {
            "period": self.period_info(filters, expected),
            "cutoff": self.cutoff_info(filters),
            "filters": _filters_dict(filters),
            "population": summary["population"],
            "metrics": summary["metrics"],
            "error_stats": summary["error_stats"],
            "direction": summary["direction"],
            "distribution": summary["distribution"],
            "top_overforecast": summary["top_overforecast"],
            "top_underforecast": summary["top_underforecast"],
            "lead_time_buckets": metrics_lib.lead_time_metrics(
                filtered, self.settings.mape_min_actual_mw
            ),
            "notes": [
                "MAE and RMSE are error magnitudes in MW, not accuracy percentages.",
                f"MAPE excludes intervals where |actual| < {self.settings.mape_min_actual_mw:g} MW.",
                "Metrics use paired forecast/actual observations only.",
            ],
        }

    def daily_analytics(self, filters: QueryFilters) -> dict[str, Any]:
        base = self.selection(filters)
        filtered, excluded = self._filtered(base, filters.lead_time_bucket)
        expected_by_date = base.groupby("delivery_date").size().to_dict()
        return {
            "period": self.period_info(filters, int(len(base))),
            "cutoff": self.cutoff_info(filters),
            "filters": _filters_dict(filters),
            "population": _population(filtered, int(len(base)), excluded),
            "days": metrics_lib.daily_metrics(
                filtered, expected_by_date, self.settings.mape_min_actual_mw
            ),
        }

    def hourly_analytics(self, filters: QueryFilters) -> dict[str, Any]:
        base = self.selection(filters)
        filtered, excluded = self._filtered(base, filters.lead_time_bucket)
        dates = sorted(base["delivery_date"].unique().tolist())
        hourly = metrics_lib.hourly_metrics(filtered, dates, self.settings.mape_min_actual_mw)
        return {
            "period": self.period_info(filters, int(len(base))),
            "cutoff": self.cutoff_info(filters),
            "filters": _filters_dict(filters),
            "population": _population(filtered, int(len(base)), excluded),
            **hourly,
        }

    def lead_time_analytics(self, filters: QueryFilters) -> dict[str, Any]:
        base = self.selection(filters)
        filtered, excluded = self._filtered(base, filters.lead_time_bucket)
        return {
            "period": self.period_info(filters, int(len(base))),
            "cutoff": self.cutoff_info(filters),
            "filters": _filters_dict(filters),
            "population": _population(filtered, int(len(base)), excluded),
            "buckets": metrics_lib.lead_time_metrics(filtered, self.settings.mape_min_actual_mw),
            "revision_curve": self._revision_curve(filtered),
            "notes": [
                "Lead time is delivery interval start minus forecast publish time.",
                "In decision-cutoff mode, the eligible vintage for each interval determines "
                "the lead-time bucket; later vintages are excluded from accuracy metrics.",
            ],
        }

    def revisions_analytics(self, filters: QueryFilters, limit: int = 10) -> dict[str, Any]:
        base = self.selection(filters)
        dataset = self.dataset()
        curve = self._revision_curve(base)
        decision = base[base["forecast_mw"].notna()][
            ["delivery_start_utc", "forecast_mw", "actual_mw", "delivery_date", "settlement_period", "interval_label"]
        ].rename(columns={"forecast_mw": "decision_mw"})
        if decision.empty or dataset.forecast.empty:
            return {
                "period": self.period_info(filters, int(len(base))),
                "filters": _filters_dict(filters),
                "summary": {
                    "intervals_with_vintages": 0,
                    "mean_abs_revision_mw": None,
                    "max_abs_revision_mw": None,
                    "unchanged_share_pct": None,
                },
                "top": [],
                "revision_curve": curve,
            }

        forecasts = dataset.forecast[
            dataset.forecast["delivery_start_utc"].isin(decision["delivery_start_utc"])
        ]
        grouped = (
            forecasts.groupby("delivery_start_utc")
            .agg(
                n_vintages=("forecast_mw", "size"),
                latest_publish=("publish_time_utc", "max"),
            )
            .reset_index()
        )
        latest_rows = forecasts.merge(
            grouped[["delivery_start_utc", "latest_publish"]],
            on="delivery_start_utc",
            how="inner",
        )
        latest_rows = latest_rows[
            latest_rows["publish_time_utc"] == latest_rows["latest_publish"]
        ][["delivery_start_utc", "forecast_mw", "publish_time_utc"]].rename(
            columns={"forecast_mw": "latest_mw", "publish_time_utc": "latest_publish_time"}
        )
        merged = decision.merge(grouped, on="delivery_start_utc", how="left").merge(
            latest_rows, on="delivery_start_utc", how="left"
        )
        merged["revision_mw"] = merged["latest_mw"] - merged["decision_mw"]
        merged["abs_revision_mw"] = merged["revision_mw"].abs()
        merged = merged.sort_values("abs_revision_mw", ascending=False, na_position="last")

        top = []
        for item in merged.head(limit).itertuples():
            top.append(
                {
                    "delivery_interval": _iso(item.delivery_start_utc),
                    "delivery_date": _date(item.delivery_date),
                    "settlement_period": int(item.settlement_period),
                    "interval_label": item.interval_label,
                    "decision_forecast_mw": _round(item.decision_mw),
                    "latest_forecast_mw": _round(getattr(item, "latest_mw", None)),
                    "actual_mw": _round(item.actual_mw),
                    "revision_mw": _round(item.revision_mw),
                    "abs_revision_mw": _round(item.abs_revision_mw),
                    "n_vintages": int(getattr(item, "n_vintages", 0) or 0),
                    "latest_publish_time": _iso(getattr(item, "latest_publish_time", None)),
                }
            )

        finite = merged["abs_revision_mw"].dropna()
        unchanged = float((finite <= 0.01).mean() * 100.0) if len(finite) else None
        return {
            "period": self.period_info(filters, int(len(base))),
            "filters": _filters_dict(filters),
            "summary": {
                "intervals_with_vintages": int(len(merged)),
                "mean_abs_revision_mw": round(float(finite.mean()), 2) if len(finite) else None,
                "max_abs_revision_mw": round(float(finite.max()), 2) if len(finite) else None,
                "unchanged_share_pct": round(unchanged, 2) if unchanged is not None else None,
            },
            "top": top,
            "revision_curve": curve,
            "retrospective_notice": (
                "The latest forecast vintage and actual generation are retrospective. "
                "Only the decision-time forecast was available at the cutoff."
            ),
        }

    def data_quality(self, probe_result: dict[str, Any] | None = None) -> dict[str, Any]:
        dataset = self.dataset()
        manifest = dataset.manifest or self.cache.read_manifest()
        actual_stats = dataset.actual_raw.get("stats", {}) or {}
        forecast_stats = dataset.forecast_raw.get("stats", {}) or {}

        grid = build_grid(self.settings, self.settings.analysis_start, self.settings.analysis_end)
        default_filters = QueryFilters(
            start_date=self.settings.analysis_start,
            end_date=self.settings.analysis_end,
            cutoff=self.settings.default_cutoff_time,
            cutoff_days_before=self.settings.default_cutoff_days_before,
        )
        coverage_days: list[dict[str, Any]] = []
        missing_actual = 0
        missing_forecast = 0
        if not dataset.actual.empty and not dataset.forecast.empty:
            frame = self.selection(default_filters)
            missing_actual = int((frame["status"] == STATUS_MISSING_ACTUAL).sum())
            missing_forecast = int((frame["status"] == STATUS_MISSING_FORECAST).sum())
            grouped = frame.groupby("delivery_date")
            for day, group in grouped:
                matched = int((group["status"] == STATUS_MATCHED).sum())
                coverage_days.append(
                    {
                        "date": _date(day),
                        "expected": int(len(group)),
                        "matched": matched,
                        "missing_actual": int((group["status"] == STATUS_MISSING_ACTUAL).sum()),
                        "missing_forecast": int((group["status"] == STATUS_MISSING_FORECAST).sum()),
                        "coverage_pct": round(matched / len(group) * 100.0, 2) if len(group) else None,
                    }
                )
            missing_rows = frame[frame["status"] != STATUS_MATCHED].head(100)
            missing_intervals = [
                {
                    "delivery_interval": _iso(row.delivery_start_utc),
                    "delivery_date": _date(row.delivery_date),
                    "settlement_period": int(row.settlement_period),
                    "interval_label": row.interval_label,
                    "missing": "forecast" if row.status == STATUS_MISSING_FORECAST else "actual",
                }
                for row in missing_rows.itertuples()
            ]
        else:
            missing_intervals = []

        actual_starts = set(dataset.actual["delivery_start_utc"]) if not dataset.actual.empty else set()
        forecast_starts = (
            set(dataset.forecast["delivery_start_utc"]) if not dataset.forecast.empty else set()
        )
        grid_starts = set(grid["delivery_start_utc"])
        unmatched_forecast = len(forecast_starts - grid_starts)
        unmatched_actual = len(actual_starts - grid_starts)
        files = self.cache.file_metadata()
        manifest_files = manifest.get("files", {})
        for key, meta in files.items():
            if key in manifest_files:
                meta.update(
                    {
                        "sha256": manifest_files[key].get("sha256"),
                        "records": manifest_files[key].get("records"),
                    }
                )

        return {
            "mode": "historical_analysis",
            "generated_at": iso_z(dt.datetime.now(UTC)),
            "upstream": probe_result
            or {
                "checked": False,
                "reachable": None,
                "status_code": None,
                "latency_ms": None,
                "checked_at": None,
                "detail": "Connectivity probe not requested",
            },
            "cache": {
                "present": self.cache.exists(),
                "files": files,
                "last_success": manifest.get("last_success", {}),
                "stale": self._data_status(dataset)["stale"],
                "stale_after_hours": self.settings.cache_stale_after_hours,
            },
            "data": self._data_status(dataset),
            "counts": {
                "actual_records": int(len(dataset.actual)),
                "forecast_records": int(
                    len(
                        dataset.forecast.drop_duplicates(
                            ["source_start_utc", "publish_time_utc"]
                        )
                    )
                ),
                "forecast_vintages": int(dataset.forecast["publish_time_utc"].nunique())
                if not dataset.forecast.empty
                else 0,
                "forecast_delivery_intervals": int(dataset.forecast["source_start_utc"].nunique())
                if not dataset.forecast.empty
                else 0,
                "forecast_expanded_intervals": int(dataset.forecast["delivery_start_utc"].nunique())
                if not dataset.forecast.empty
                else 0,
                "expected_intervals": int(len(grid)),
                "missing_actual_intervals": missing_actual,
                "missing_forecast_intervals": missing_forecast,
                "forecast_intervals_outside_analysis_window": unmatched_forecast,
                "actual_intervals_outside_analysis_window": unmatched_actual,
                "duplicates_removed": int(actual_stats.get("duplicates_removed", 0))
                + int(forecast_stats.get("duplicates_removed", 0)),
                "duplicate_conflicts": int(actual_stats.get("duplicate_conflicts", 0))
                + int(forecast_stats.get("duplicate_conflicts", 0)),
                "invalid_records": int(actual_stats.get("invalid_records", 0))
                + int(forecast_stats.get("invalid_records", 0)),
                "excluded_post_delivery_records": int(
                    forecast_stats.get("excluded_post_delivery", 0)
                ),
                "naive_timestamps": int(actual_stats.get("naive_timestamps", 0))
                + int(forecast_stats.get("naive_timestamps", 0)),
            },
            "actual_stats": actual_stats,
            "forecast_stats": forecast_stats,
            "coverage_by_day": coverage_days,
            "missing_intervals": missing_intervals,
            "invalid_samples": list(actual_stats.get("invalid_samples", []))[:25]
            + list(forecast_stats.get("invalid_samples", []))[:25],
            "retrieval_events": list(reversed(manifest.get("retrieval_events", [])))[:50],
            "notes": [
                "All figures are derived from the cached Elexon BMRS response files.",
                "No synthetic records are used in production analytics.",
                "Post-delivery forecast publications are excluded during normalisation.",
                "Hourly WINDFOR values are applied to both 30-minute settlement periods of the hour.",
            ],
        }

    def export_frame(self, filters: QueryFilters, search: str | None, status: str | None) -> pd.DataFrame:
        base = self.selection(filters)
        frame, _ = self._filtered(base, filters.lead_time_bucket)
        if status and status != "all":
            frame = frame[frame["status"] == status]
        if search:
            needle = search.strip().lower()
            mask = (
                frame["delivery_date"].astype(str).str.contains(needle, na=False)
                | frame["interval_label"].str.contains(needle, na=False)
                | frame["settlement_period"].astype(str).str.contains(needle, na=False)
                | frame["status"].str.contains(needle, na=False)
            )
            frame = frame[mask]
        return frame.sort_values("delivery_start_utc").copy()

    async def refresh(self) -> dict[str, Any]:
        if not self.settings.allow_refresh:
            raise RefreshDisabledError(
                "Dataset refresh is disabled. Set ALLOW_REFRESH=true on the backend to "
                "enable the refresh endpoint, or run `python -m app.cli load`."
            )
        result = await ingest_window(
            self.settings,
            self.cache,
            self.settings.analysis_start,
            self.settings.analysis_end,
            client=self.client,
        )
        self.datasets.invalidate()
        with self._selection_lock:
            self._selection_cache.clear()
        return result.to_dict()

    def export_csv(self, filters: QueryFilters, search: str | None, status: str | None) -> tuple[str, str]:
        frame = self.export_frame(filters, search, status)
        local = frame["delivery_start_utc"].dt.tz_convert(self.settings.timezone)
        export = pd.DataFrame(
            {
                "delivery_date": frame["delivery_date"].astype(str),
                "settlement_period": frame["settlement_period"].astype(int),
                "interval_start_london": local.map(lambda value: value.isoformat()),
                "interval_start_utc": frame["delivery_start_utc"].map(
                    lambda value: value.isoformat().replace("+00:00", "Z")
                ),
                "interval_label_london": frame["interval_label"],
                "forecast_mw": frame["forecast_mw"].round(2),
                "actual_mw": frame["actual_mw"].round(2),
                "error_mw": frame["error_mw"].round(2),
                "absolute_error_mw": frame["absolute_error_mw"].round(2),
                "percentage_error": frame["percentage_error"].round(2),
                "forecast_publish_time_utc": frame["publish_time_utc"].map(
                    lambda value: value.isoformat().replace("+00:00", "Z")
                    if pd.notna(value)
                    else ""
                ),
                "lead_time_hours": frame["lead_time_hours"],
                "lead_time_bucket": frame["lead_time_bucket"].fillna(""),
                "decision_cutoff_utc": frame["cutoff_time_utc"].map(
                    lambda value: value.isoformat().replace("+00:00", "Z")
                ),
                "eligibility": frame["eligibility"],
                "status": frame["status"],
                "cutoff_compliant": frame["is_cutoff_compliant"],
                "data_source": "Elexon BMRS FUELHH + WINDFOR",
                "synthetic": False,
            }
        )
        csv_text = export.to_csv(index=False, lineterminator="\n")
        filename = (
            f"windiq_forecasts_{filters.start_date.isoformat()}_{filters.end_date.isoformat()}.csv"
        )
        return filename, csv_text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _revision_curve(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        dataset = self.dataset()
        if dataset.forecast.empty:
            return []
        decision = frame[frame["forecast_mw"].notna()][
            ["delivery_start_utc", "forecast_mw", "actual_mw"]
        ]
        if decision.empty:
            return []
        window_start = frame["delivery_start_utc"].min()
        window_end = frame["delivery_start_utc"].max()
        vintages = dataset.forecast[
            (dataset.forecast["delivery_start_utc"] >= window_start)
            & (dataset.forecast["delivery_start_utc"] <= window_end)
        ][["delivery_start_utc", "publish_time_utc", "forecast_mw"]].copy()
        vintages["lead_time_hours"] = (
            (vintages["delivery_start_utc"] - vintages["publish_time_utc"]).dt.total_seconds()
            / 3600.0
        )
        return metrics_lib.revision_curve(vintages, decision)


# ----------------------------------------------------------------------
# Serialisation helpers
# ----------------------------------------------------------------------
def forecast_row(row: Any) -> dict[str, Any]:
    def value(name: str) -> Any:
        raw = getattr(row, name, None)
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return None
        return raw

    forecast_mw = _round(value("forecast_mw"))
    actual_mw = _round(value("actual_mw"))
    error_mw = _round(value("error_mw"))
    return {
        "delivery_interval": _iso(value("delivery_start_utc")),
        "delivery_date": _date(value("delivery_date")),
        "settlement_period": int(value("settlement_period")),
        "interval_label": value("interval_label"),
        "forecast_mw": forecast_mw,
        "actual_mw": actual_mw,
        "error_mw": error_mw,
        "absolute_error_mw": _round(value("absolute_error_mw")),
        "percentage_error": _round(value("percentage_error")),
        "publish_time": _iso(value("publish_time_utc")),
        "lead_time_hours": _round(value("lead_time_hours")),
        "lead_time_bucket": value("lead_time_bucket"),
        "lead_time_bucket_label": lead_time_bucket_label(value("lead_time_bucket")),
        "cutoff_time": _iso(value("cutoff_time_utc")),
        "eligibility": value("eligibility"),
        "status": value("status"),
        "is_cutoff_compliant": bool(value("is_cutoff_compliant")),
    }


def _latest_row(frame: pd.DataFrame, require_forecast: bool = False, require_actual: bool = False) -> Any:
    working = frame
    if require_forecast:
        working = working[working["forecast_mw"].notna()]
    if require_actual:
        working = working[working["actual_mw"].notna()]
    if working.empty:
        return None
    return working.sort_values("delivery_start_utc").iloc[-1]


def _latest_forecast_kpi(row: Any) -> dict[str, Any]:
    if row is None:
        return {
            "value": None,
            "unit": "MW",
            "delivery_interval": None,
            "publish_time": None,
            "lead_time_hours": None,
            "status": "unavailable",
        }
    return {
        "value": _round(row["forecast_mw"]),
        "unit": "MW",
        "delivery_interval": _iso(row["delivery_start_utc"]),
        "delivery_date": _date(row["delivery_date"]),
        "settlement_period": int(row["settlement_period"]),
        "interval_label": row["interval_label"],
        "publish_time": _iso(row["publish_time_utc"]),
        "lead_time_hours": _round(row["lead_time_hours"]),
        "status": "historical_eligible",
        "eligibility": row["eligibility"],
    }


def _latest_actual_kpi(row: Any) -> dict[str, Any]:
    if row is None:
        return {"value": None, "unit": "MW", "delivery_interval": None, "status": "unavailable"}
    return {
        "value": _round(row["actual_mw"]),
        "unit": "MW",
        "delivery_interval": _iso(row["delivery_start_utc"]),
        "delivery_date": _date(row["delivery_date"]),
        "settlement_period": int(row["settlement_period"]),
        "interval_label": row["interval_label"],
        "status": "actual_observed",
    }


def _latest_error_kpi(row: Any) -> dict[str, Any]:
    if row is None:
        return {"value": None, "unit": "MW", "delivery_interval": None, "status": "unavailable"}
    return {
        "value": _round(row["error_mw"]),
        "unit": "MW",
        "delivery_interval": _iso(row["delivery_start_utc"]),
        "delivery_date": _date(row["delivery_date"]),
        "settlement_period": int(row["settlement_period"]),
        "percentage_error": _round(row["percentage_error"]),
        "direction": (
            "overforecast" if row["error_mw"] > 0 else "underforecast" if row["error_mw"] < 0 else "exact"
        ),
        "status": "matched",
    }


def _population(frame: pd.DataFrame, expected: int, excluded_by_lead_time: int = 0) -> dict[str, Any]:
    return {
        "expected_intervals": int(expected),
        "selected_intervals": int(len(frame)),
        "matched_intervals": int((frame["status"] == STATUS_MATCHED).sum()),
        "missing_forecast": int((frame["status"] == STATUS_MISSING_FORECAST).sum()),
        "missing_actual": int((frame["status"] == STATUS_MISSING_ACTUAL).sum()),
        "excluded_by_lead_time": int(excluded_by_lead_time),
    }


def _filters_dict(filters: QueryFilters) -> dict[str, Any]:
    return {
        "start_date": filters.start_date.isoformat(),
        "end_date": filters.end_date.isoformat(),
        "cutoff": filters.cutoff,
        "cutoff_days_before": filters.cutoff_days_before,
        "vintage": filters.vintage,
        "vintage_label": (
            "Decision cutoff (no look-ahead)"
            if filters.vintage != VINTAGE_LATEST
            else "Latest available (retrospective, may leak post-cutoff information)"
        ),
        "lead_time_bucket": filters.lead_time_bucket,
    }


def _procurement_context() -> str:
    return (
        "Wind forecast error indicates uncertainty in renewable generation and therefore "
        "possible residual procurement requirements. WindIQ cannot calculate the volume that "
        "should actually be purchased: that requires demand, other generation, interconnector "
        "flows, balancing actions and market prices, which are outside this product's scope."
    )


def _limitations() -> list[str]:
    return [
        "January 2026 is analysed retrospectively. Forecasts are as-published; actual generation "
        "is the Elexon outturn and may itself be revised.",
        "The 11:00 Europe/London preceding-day cutoff is a pilot assumption, not a universal "
        "market deadline. It is configurable per request.",
        "Elexon WINDFOR is hourly while FUELHH is half-hourly; each hourly forecast is applied "
        "to both settlement periods it covers. This is an explicit modelling assumption.",
        "Forecast coverage depends on which WINDFOR vintages are available in the cached "
        "publication window; the API does not guarantee a vintage for every interval.",
        "The application does not model demand, prices, interconnectors, other generation or "
        "balancing actions, and must not be used to infer required traded volumes.",
        "Actual outturn values may be revised by Elexon after initial publication.",
    ]


def _period_label(start: dt.date, end: dt.date) -> str:
    if start == end:
        return f"{start.day} {start.strftime('%b %Y')}"
    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {end.strftime('%b %Y')}"
    return f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"


def _iso(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, dt.datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _date(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _round(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return round(number, 2)
