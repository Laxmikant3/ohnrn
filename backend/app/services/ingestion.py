"""Elexon ingestion pipeline with chunking, retries and cache write-through."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.clients.elexon import ElexonClient, ElexonError
from app.config import Settings
from app.domain import ActualRecord, ForecastRecord, NormalizationStats
from app.services.cache import CacheStore
from app.services.dataset import infer_granularity_from_raw
from app.services.normalize import normalize_actual_records, normalize_forecast_records
from app.utils.timeutils import UTC, iso_z, localize_wall_time

logger = logging.getLogger("windiq.ingest")


@dataclass
class IngestResult:
    start_date: dt.date
    end_date: dt.date
    actual_records: int = 0
    forecast_records: int = 0
    actual_fetched: int = 0
    forecast_fetched: int = 0
    actual_error: str | None = None
    forecast_error: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    complete: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "actual_records": self.actual_records,
            "forecast_records": self.forecast_records,
            "actual_fetched": self.actual_fetched,
            "forecast_fetched": self.forecast_fetched,
            "actual_error": self.actual_error,
            "forecast_error": self.forecast_error,
            "errors": self.errors,
            "complete": self.complete,
            "is_synthetic": False,
        }


def _event(
    operation: str,
    endpoint: str,
    params: dict[str, Any],
    status: str,
    records: int = 0,
    attempts: int = 0,
    duration: float = 0.0,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": iso_z(dt.datetime.now(UTC)),
        "operation": operation,
        "endpoint": endpoint,
        "params": params,
        "status": status,
        "records": records,
        "attempts": attempts,
        "duration_seconds": round(duration, 3),
        "error": error,
    }


def _date_chunks(start: dt.date, end: dt.date, days: int) -> list[tuple[dt.date, dt.date]]:
    chunks: list[tuple[dt.date, dt.date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + dt.timedelta(days=days - 1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + dt.timedelta(days=1)
    return chunks


def _existing_records(store: CacheStore, key: str) -> dict[str, Any]:
    payload = store.read_actual() if key == "actual" else store.read_forecast()
    return payload or {}


def _record_key_actual(record: dict[str, Any]) -> str:
    return str(record.get("start_time"))


def _record_key_forecast(record: dict[str, Any]) -> str:
    return f"{record.get('start_time')}|{record.get('publish_time')}"


async def ingest_window(
    settings: Settings,
    cache: CacheStore,
    start_date: dt.date,
    end_date: dt.date,
    *,
    client: ElexonClient | None = None,
) -> IngestResult:
    """Fetch, normalise and merge actual + forecast data into the file cache.

    Both sources are fetched independently so a WINDFOR outage never discards
    valid FUELHH data. Nothing is written if a source returns no valid records.
    """
    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")
    client = client or ElexonClient(settings)
    result = IngestResult(start_date=start_date, end_date=end_date)
    now = dt.datetime.now(UTC)

    # ---------------- FUELHH actuals ----------------------------------
    actual_payload = _existing_records(cache, "actual")
    actual_records = {
        _record_key_actual(r): r for r in actual_payload.get("records", [])
    }
    actual_stats_payload = dict(actual_payload.get("stats") or {})
    actual_cumulative = NormalizationStats(
        raw_records=int(actual_stats_payload.get("raw_records", 0)),
        invalid_records=int(actual_stats_payload.get("invalid_records", 0)),
        duplicates_removed=int(actual_stats_payload.get("duplicates_removed", 0)),
        duplicate_conflicts=int(actual_stats_payload.get("duplicate_conflicts", 0)),
        naive_timestamps=int(actual_stats_payload.get("naive_timestamps", 0)),
        negative_values=int(actual_stats_payload.get("negative_values", 0)),
        excluded_post_delivery=int(actual_stats_payload.get("excluded_post_delivery", 0)),
        invalid_samples=list(actual_stats_payload.get("invalid_samples", [])),
    )
    windows = list(actual_payload.get("request_windows", []))

    for chunk_start, chunk_end in _date_chunks(
        start_date, end_date, settings.elexon_actual_chunk_days
    ):
        try:
            fetched = await client.fetch_actual_wind(chunk_start, chunk_end)
        except ElexonError as exc:
            result.actual_error = str(exc)
            result.complete = False
            result.errors.append(
                {"source": "actual", "window": [chunk_start.isoformat(), chunk_end.isoformat()], "error": str(exc)}
            )
            result.events.append(
                _event(
                    "actual",
                    "/datasets/FUELHH/stream",
                    {
                        "settlementDateFrom": chunk_start.isoformat(),
                        "settlementDateTo": chunk_end.isoformat(),
                        "fuelType": "WIND",
                    },
                    "error",
                    error=str(exc),
                )
            )
            continue

        result.actual_fetched += len(fetched.records)
        records, stats = normalize_actual_records(fetched.records)
        new_keys = {iso_z(record.delivery_start_utc) for record in records}
        overlap = len(set(actual_records) & new_keys)
        for record in records:
            actual_records[iso_z(record.delivery_start_utc)] = _serialize_actual(record)
        _accumulate(actual_cumulative, stats, overlap)
        windows.append({"from": chunk_start.isoformat(), "to": chunk_end.isoformat()})
        result.events.append(
            _event(
                "actual",
                "/datasets/FUELHH/stream",
                {
                    "settlementDateFrom": chunk_start.isoformat(),
                    "settlementDateTo": chunk_end.isoformat(),
                    "fuelType": "WIND",
                },
                "success",
                records=len(fetched.records),
                attempts=fetched.attempts,
                duration=fetched.duration_seconds,
            )
        )

    if actual_records:
        actual_cumulative.valid_records = len(actual_records)
        first_retrieved = _first_retrieved(actual_payload, now)
        cache.write_actual(
            records=sorted(actual_records.values(), key=lambda r: r["start_time"]),
            windows=_merge_windows(windows),
            stats=actual_cumulative.to_dict(),
            retrieved_at=now,
            first_retrieved_at=first_retrieved,
        )
        result.actual_records = len(actual_records)

    for event in result.events:
        cache.append_event(event)

    # ---------------- WINDFOR forecasts --------------------------------
    forecast_payload = _existing_records(cache, "forecast")
    forecast_records = {
        _record_key_forecast(r): r for r in forecast_payload.get("records", [])
    }
    forecast_stats_payload = dict(forecast_payload.get("stats") or {})
    forecast_cumulative = NormalizationStats(
        raw_records=int(forecast_stats_payload.get("raw_records", 0)),
        invalid_records=int(forecast_stats_payload.get("invalid_records", 0)),
        duplicates_removed=int(forecast_stats_payload.get("duplicates_removed", 0)),
        duplicate_conflicts=int(forecast_stats_payload.get("duplicate_conflicts", 0)),
        naive_timestamps=int(forecast_stats_payload.get("naive_timestamps", 0)),
        negative_values=int(forecast_stats_payload.get("negative_values", 0)),
        excluded_post_delivery=int(forecast_stats_payload.get("excluded_post_delivery", 0)),
        invalid_samples=list(forecast_stats_payload.get("invalid_samples", [])),
    )
    publish_windows = list(forecast_payload.get("request_windows", []))

    publish_from = localize_wall_time(
        start_date - dt.timedelta(days=settings.elexon_forecast_padding_days_before),
        dt.time(0, 0),
        settings.timezone,
    ).astimezone(UTC)
    publish_to = localize_wall_time(
        end_date + dt.timedelta(days=settings.elexon_forecast_padding_days_after),
        dt.time(23, 59, 59),
        settings.timezone,
    ).astimezone(UTC)

    for chunk_start, chunk_end in _datetime_chunks(
        publish_from, publish_to, settings.elexon_forecast_chunk_days
    ):
        try:
            fetched = await client.fetch_forecast_wind(chunk_start, chunk_end)
        except ElexonError as exc:
            result.forecast_error = str(exc)
            result.complete = False
            result.errors.append(
                {
                    "source": "forecast",
                    "window": [iso_z(chunk_start), iso_z(chunk_end)],
                    "error": str(exc),
                }
            )
            result.events.append(
                _event(
                    "forecast",
                    "/datasets/WINDFOR/stream",
                    {
                        "publishDateTimeFrom": iso_z(chunk_start),
                        "publishDateTimeTo": iso_z(chunk_end),
                    },
                    "error",
                    error=str(exc),
                )
            )
            continue

        result.forecast_fetched += len(fetched.records)
        records, stats = normalize_forecast_records(fetched.records)
        overlap = len(
            set(forecast_records)
            & {f"{iso_z(r.delivery_start_utc)}|{iso_z(r.publish_time_utc)}" for r in records}
        )
        for record in records:
            forecast_records[
                f"{iso_z(record.delivery_start_utc)}|{iso_z(record.publish_time_utc)}"
            ] = _serialize_forecast(record)
        _accumulate(forecast_cumulative, stats, overlap)
        publish_windows.append({"from": iso_z(chunk_start), "to": iso_z(chunk_end)})
        result.events.append(
            _event(
                "forecast",
                "/datasets/WINDFOR/stream",
                {
                    "publishDateTimeFrom": iso_z(chunk_start),
                    "publishDateTimeTo": iso_z(chunk_end),
                },
                "success",
                records=len(fetched.records),
                attempts=fetched.attempts,
                duration=fetched.duration_seconds,
            )
        )

    if forecast_records:
        forecast_cumulative.valid_records = len(forecast_records)
        granularity = infer_granularity_from_raw(
            [{"startTime": r["start_time"]} for r in forecast_records.values()]
        )
        cache.write_forecast(
            records=sorted(
                forecast_records.values(), key=lambda r: (r["start_time"], r["publish_time"])
            ),
            windows=_merge_windows(publish_windows),
            stats=forecast_cumulative.to_dict(),
            retrieved_at=now,
            first_retrieved_at=_first_retrieved(forecast_payload, now),
            granularity_minutes=granularity,
        )
        result.forecast_records = len(forecast_records)

    # Append forecast events (the earlier loop only persisted actual events).
    for event in result.events:
        if event["operation"] == "forecast":
            cache.append_event(event)

    logger.info(
        "ingest_complete",
        extra={
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "actual_records": result.actual_records,
            "forecast_records": result.forecast_records,
            "complete": result.complete,
        },
    )
    return result


def _datetime_chunks(
    start: dt.datetime, end: dt.datetime, days: int
) -> list[tuple[dt.datetime, dt.datetime]]:
    chunks: list[tuple[dt.datetime, dt.datetime]] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + dt.timedelta(days=days), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + dt.timedelta(seconds=1)
    return chunks


def _serialize_actual(record: ActualRecord) -> dict[str, Any]:
    return {
        "start_time": iso_z(record.delivery_start_utc),
        "publish_time": iso_z(record.publish_time_utc),
        "settlement_date": record.settlement_date.isoformat() if record.settlement_date else None,
        "settlement_period": record.settlement_period,
        "fuel_type": record.fuel_type,
        "generation_mw": record.generation_mw,
    }


def _serialize_forecast(record: ForecastRecord) -> dict[str, Any]:
    return {
        "start_time": iso_z(record.delivery_start_utc),
        "publish_time": iso_z(record.publish_time_utc),
        "generation_mw": record.generation_mw,
    }


def _accumulate(cumulative: NormalizationStats, latest: NormalizationStats, overlap: int) -> None:
    cumulative.raw_records += latest.raw_records
    cumulative.invalid_records += latest.invalid_records
    cumulative.duplicates_removed += latest.duplicates_removed + overlap
    cumulative.duplicate_conflicts += latest.duplicate_conflicts
    cumulative.naive_timestamps += latest.naive_timestamps
    cumulative.negative_values += latest.negative_values
    cumulative.excluded_post_delivery += latest.excluded_post_delivery
    for sample in latest.invalid_samples:
        if len(cumulative.invalid_samples) < 50:
            cumulative.invalid_samples.append(sample)


def _merge_windows(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for window in windows:
        start = window.get("from")
        end = window.get("to")
        if start and end:
            seen[(str(start), str(end))] = {"from": str(start), "to": str(end)}
    return list(seen.values())


def _first_retrieved(payload: dict[str, Any], fallback: dt.datetime) -> dt.datetime | None:
    from app.utils.timeutils import parse_api_timestamp

    return parse_api_timestamp(payload.get("first_retrieved_at")) or fallback


def dataset_dates(frame: pd.DataFrame, tz: Any) -> tuple[dt.date, dt.date] | None:
    if frame.empty:
        return None
    dates = frame["delivery_start_utc"].dt.tz_convert(tz).dt.date
    return dates.min(), dates.max()


def run_ingest(
    settings: Settings,
    cache: CacheStore,
    start_date: dt.date,
    end_date: dt.date,
) -> IngestResult:
    return asyncio.run(ingest_window(settings, cache, start_date, end_date))
