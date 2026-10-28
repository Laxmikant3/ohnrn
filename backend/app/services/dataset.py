"""Dataset loading, integrity checks and forecast granularity handling."""

from __future__ import annotations

import datetime as dt
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.config import Settings
from app.services.cache import CacheError, CacheStore
from app.utils.timeutils import UTC, parse_api_timestamp

logger = logging.getLogger("windiq.dataset")

EMPTY_COLUMNS_ACTUAL = ["delivery_start_utc", "publish_time_utc", "actual_mw"]
EMPTY_COLUMNS_FORECAST = [
    "delivery_start_utc",
    "publish_time_utc",
    "forecast_mw",
    "source_start_utc",
    "is_expanded",
]


@dataclass
class Dataset:
    actual: pd.DataFrame
    forecast: pd.DataFrame  # half-hourly-expanded forecast rows
    actual_raw: dict[str, Any] = field(default_factory=dict)
    forecast_raw: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    forecast_granularity_minutes: int = 60
    actual_dates: tuple[dt.date, dt.date] | None = None
    forecast_dates: tuple[dt.date, dt.date] | None = None
    retrieved_at: dt.datetime | None = None
    signature: str = ""
    load_error: str | None = None

    @property
    def loaded(self) -> bool:
        return not self.actual.empty and not self.forecast.empty

    @property
    def actual_loaded(self) -> bool:
        return not self.actual.empty

    @property
    def forecast_loaded(self) -> bool:
        return not self.forecast.empty

    @property
    def is_synthetic(self) -> bool:
        return bool(
            self.actual_raw.get("is_synthetic") or self.forecast_raw.get("is_synthetic")
        )


class DatasetStore:
    def __init__(self, settings: Settings, cache: CacheStore | None = None) -> None:
        self.settings = settings
        self.cache = cache or CacheStore(settings)
        self._lock = threading.RLock()
        self._dataset: Dataset | None = None
        self._signature: str | None = None

    def get(self, force_reload: bool = False) -> Dataset:
        with self._lock:
            signature = self.cache.signature()
            if (
                not force_reload
                and self._dataset is not None
                and self._signature == signature
            ):
                return self._dataset
            try:
                dataset = self._load(signature)
            except CacheError as exc:
                logger.error("dataset_cache_error", extra={"error": str(exc)})
                dataset = _empty_dataset(signature, str(exc))
            self._dataset = dataset
            self._signature = signature
            return dataset

    def invalidate(self) -> None:
        with self._lock:
            self._signature = None

    # ------------------------------------------------------------------
    def _load(self, signature: str) -> Dataset:
        actual_payload = self.cache.read_actual()
        forecast_payload = self.cache.read_forecast()
        manifest = self.cache.read_manifest()

        if actual_payload is None and forecast_payload is None:
            return _empty_dataset(signature, "No cached dataset found")

        actual = _actual_frame(actual_payload)
        forecast_raw = _forecast_frame(forecast_payload)
        granularity = _detect_granularity(forecast_payload)
        forecast = expand_forecasts(forecast_raw, granularity)

        actual_dates = _date_range(actual, self.settings.timezone)
        forecast_dates = _date_range(forecast, self.settings.timezone)
        retrieved_candidates = [
            parse_api_timestamp((actual_payload or {}).get("retrieved_at")),
            parse_api_timestamp((forecast_payload or {}).get("retrieved_at")),
        ]
        retrieved = min(
            [value for value in retrieved_candidates if value is not None], default=None
        )

        return Dataset(
            actual=actual,
            forecast=forecast,
            actual_raw=actual_payload or {},
            forecast_raw=forecast_payload or {},
            manifest=manifest,
            forecast_granularity_minutes=granularity,
            actual_dates=actual_dates,
            forecast_dates=forecast_dates,
            retrieved_at=retrieved,
            signature=signature,
        )


def _empty_dataset(signature: str, reason: str) -> Dataset:
    return Dataset(
        actual=pd.DataFrame({col: pd.Series(dtype="object") for col in EMPTY_COLUMNS_ACTUAL}),
        forecast=pd.DataFrame(
            {col: pd.Series(dtype="object") for col in EMPTY_COLUMNS_FORECAST}
        ),
        signature=signature,
        load_error=reason,
        actual_raw={},
        forecast_raw={},
    )


def _actual_frame(payload: dict[str, Any] | None) -> pd.DataFrame:
    if not payload or not payload.get("records"):
        return pd.DataFrame({col: pd.Series(dtype="object") for col in EMPTY_COLUMNS_ACTUAL})
    frame = pd.DataFrame(payload["records"])
    frame["delivery_start_utc"] = pd.to_datetime(frame["start_time"], utc=True)
    frame["publish_time_utc"] = pd.to_datetime(frame.get("publish_time"), utc=True)
    frame["actual_mw"] = pd.to_numeric(frame["generation_mw"], errors="coerce")
    frame = frame.dropna(subset=["delivery_start_utc", "actual_mw"])
    return frame[["delivery_start_utc", "publish_time_utc", "actual_mw"]].sort_values(
        "delivery_start_utc"
    )


def _forecast_frame(payload: dict[str, Any] | None) -> pd.DataFrame:
    if not payload or not payload.get("records"):
        return pd.DataFrame(
            {col: pd.Series(dtype="object") for col in EMPTY_COLUMNS_FORECAST}
        )
    frame = pd.DataFrame(payload["records"])
    frame["delivery_start_utc"] = pd.to_datetime(frame["start_time"], utc=True)
    frame["publish_time_utc"] = pd.to_datetime(frame["publish_time"], utc=True)
    frame["forecast_mw"] = pd.to_numeric(frame["generation_mw"], errors="coerce")
    frame = frame.dropna(subset=["delivery_start_utc", "publish_time_utc", "forecast_mw"])
    frame["source_start_utc"] = frame["delivery_start_utc"]
    frame["is_expanded"] = False
    return frame[
        ["delivery_start_utc", "publish_time_utc", "forecast_mw", "source_start_utc", "is_expanded"]
    ].sort_values(["delivery_start_utc", "publish_time_utc"])


def _detect_granularity(payload: dict[str, Any] | None) -> int:
    if not payload:
        return 60
    stored = payload.get("granularity_minutes")
    if isinstance(stored, (int, float)) and stored >= 30:
        return int(stored)
    return 60


def expand_forecasts(frame: pd.DataFrame, granularity_minutes: int) -> pd.DataFrame:
    """Expand hourly WINDFOR rows onto 30-minute delivery intervals.

    Elexon WINDFOR publishes an hourly generation forecast. The procured
    settlement period is 30 minutes, so each hourly value is applied to both
    half-hours it covers. This is an explicit, documented assumption; the raw
    hourly delivery start is retained in ``source_start_utc`` and the derived
    rows are flagged with ``is_expanded``.
    """
    if frame.empty:
        return frame
    if granularity_minutes <= 30:
        return frame.copy()

    parts: list[pd.DataFrame] = []
    steps = int(granularity_minutes // 30)
    for step in range(steps):
        part = frame.copy()
        part["delivery_start_utc"] = part["delivery_start_utc"] + pd.to_timedelta(
            30 * step, unit="m"
        )
        part["is_expanded"] = step > 0 or granularity_minutes > 30
        parts.append(part)
    expanded = pd.concat(parts, ignore_index=True)
    expanded = expanded.drop_duplicates(
        subset=["delivery_start_utc", "publish_time_utc"], keep="first"
    )
    return expanded.sort_values(["delivery_start_utc", "publish_time_utc"]).reset_index(
        drop=True
    )


def _date_range(frame: pd.DataFrame, tz: Any) -> tuple[dt.date, dt.date] | None:
    if frame.empty:
        return None
    dates = frame["delivery_start_utc"].dt.tz_convert(tz).dt.date
    return dates.min(), dates.max()


def infer_granularity_from_raw(raw_records: list[dict[str, Any]]) -> int:
    """Infer the number of minutes between forecast delivery timestamps."""
    starts = sorted(
        {
            parsed
            for parsed in (parse_api_timestamp(r.get("startTime")) for r in raw_records)
            if parsed is not None
        }
    )
    if len(starts) < 2:
        return 60
    deltas = [
        int((b - a).total_seconds() // 60) for a, b in zip(starts, starts[1:], strict=False) if b > a
    ]
    if not deltas:
        return 60
    deltas.sort()
    median = deltas[len(deltas) // 2]
    if median <= 30:
        return 30
    if median <= 60:
        return 60
    return 60


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)
