"""Normalisation and validation of raw Elexon records.

The output schema is deliberately narrow and unit-explicit:

ActualRecord(delivery_start_utc, publish_time_utc, settlement_date,
             settlement_period, fuel_type, generation_mw)
ForecastRecord(delivery_start_utc, publish_time_utc, generation_mw)

Elexon's FUELHH and WINDFOR schemas both document ``generation`` as int64 MW, so
no unit conversion is applied. Values are validated to be finite and within a
physically plausible envelope; anything else is rejected and counted.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from app.domain import (
    ActualRecord,
    ForecastRecord,
    NormalizationStats,
)
from app.utils.timeutils import is_naive, parse_api_timestamp

MAX_PLAUSIBLE_MW = 100_000.0
MIN_ACTUAL_MW = -500.0


def _coerce_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            number = float(value)
        except ValueError:
            return None
    elif isinstance(value, (int, float)):
        number = float(value)
    else:
        return None
    if not math.isfinite(number):
        return None
    return number


def _parse_settlement_date(value: Any) -> dt.date | None:
    if value is None:
        return None
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def normalize_actual_records(
    raw_records: Iterable[dict[str, Any]], stats: NormalizationStats | None = None
) -> tuple[list[ActualRecord], NormalizationStats]:
    stats = stats or NormalizationStats()
    parsed: list[ActualRecord] = []

    for raw in raw_records:
        stats.raw_records += 1
        if not isinstance(raw, dict):
            stats.add_invalid("record is not an object", raw)
            continue
        fuel_type = str(raw.get("fuelType") or "").upper()
        if fuel_type != "WIND":
            # The upstream filter is server-side, but we never trust it blindly.
            stats.add_invalid(f"unexpected fuelType '{fuel_type}'", raw)
            continue

        start = parse_api_timestamp(raw.get("startTime"))
        if start is None:
            stats.add_invalid("missing or unparseable startTime", raw)
            continue
        if is_naive(raw.get("startTime")):
            stats.naive_timestamps += 1

        publish = parse_api_timestamp(raw.get("publishTime"))
        generation = _coerce_number(raw.get("generation"))
        if generation is None:
            stats.add_invalid("missing or non-numeric generation", raw)
            continue
        if not math.isfinite(generation) or abs(generation) > MAX_PLAUSIBLE_MW:
            stats.add_invalid("generation outside plausible MW envelope", raw)
            continue
        if generation < MIN_ACTUAL_MW:
            stats.add_invalid("implausibly negative actual generation", raw)
            continue
        if generation < 0:
            stats.negative_values += 1

        settlement_period = raw.get("settlementPeriod")
        try:
            settlement_period_int = int(settlement_period) if settlement_period is not None else None
        except (TypeError, ValueError):
            settlement_period_int = None
        if settlement_period_int is not None and not 1 <= settlement_period_int <= 50:
            stats.add_invalid("settlementPeriod outside 1..50", raw)
            continue

        parsed.append(
            ActualRecord(
                delivery_start_utc=start,
                publish_time_utc=publish,
                settlement_date=_parse_settlement_date(raw.get("settlementDate")),
                settlement_period=settlement_period_int,
                fuel_type="WIND",
                generation_mw=generation,
            )
        )

    deduped, removed, conflicts = _dedupe_actual(parsed)
    stats.duplicates_removed += removed
    stats.duplicate_conflicts += conflicts
    stats.valid_records = len(deduped)
    return deduped, stats


def normalize_forecast_records(
    raw_records: Iterable[dict[str, Any]], stats: NormalizationStats | None = None
) -> tuple[list[ForecastRecord], NormalizationStats]:
    stats = stats or NormalizationStats()
    parsed: list[ForecastRecord] = []

    for raw in raw_records:
        stats.raw_records += 1
        if not isinstance(raw, dict):
            stats.add_invalid("record is not an object", raw)
            continue

        start = parse_api_timestamp(raw.get("startTime"))
        if start is None:
            stats.add_invalid("missing or unparseable startTime", raw)
            continue
        publish = parse_api_timestamp(raw.get("publishTime"))
        if publish is None:
            stats.add_invalid("missing or unparseable publishTime (required for vintages)", raw)
            continue
        if is_naive(raw.get("startTime")) or is_naive(raw.get("publishTime")):
            stats.naive_timestamps += 1

        generation = _coerce_number(raw.get("generation"))
        if generation is None:
            stats.add_invalid("missing or non-numeric generation", raw)
            continue
        if not math.isfinite(generation) or abs(generation) > MAX_PLAUSIBLE_MW:
            stats.add_invalid("generation outside plausible MW envelope", raw)
            continue
        if generation < 0:
            stats.add_invalid("negative forecast generation", raw)
            continue
        if publish > start:
            # A record published after the delivery interval started is not a
            # forecast for that interval; it is excluded from all selection and
            # revision analysis (counted separately, never silently used).
            stats.excluded_post_delivery += 1
            continue

        parsed.append(
            ForecastRecord(
                delivery_start_utc=start,
                publish_time_utc=publish,
                generation_mw=generation,
            )
        )

    deduped, removed, conflicts = _dedupe_forecast(parsed)
    stats.duplicates_removed += removed
    stats.duplicate_conflicts += conflicts
    stats.valid_records = len(deduped)
    return deduped, stats


def _dedupe_actual(
    records: list[ActualRecord],
) -> tuple[list[ActualRecord], int, int]:
    """Collapse duplicates keyed by delivery interval.

    The record with the latest publication time wins (it is the most recent
    outturn revision). If a genuine conflict remains at the same publication
    time, values are averaged deterministically and the conflict is counted.
    """
    grouped: dict[dt.datetime, list[ActualRecord]] = defaultdict(list)
    for record in records:
        grouped[record.delivery_start_utc].append(record)

    out: list[ActualRecord] = []
    removed = 0
    conflicts = 0
    for _start, group in grouped.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        removed += len(group) - 1
        latest_publish = max(
            (r.publish_time_utc for r in group if r.publish_time_utc),
            default=None,
        )
        latest = [r for r in group if r.publish_time_utc == latest_publish]
        values = {round(r.generation_mw, 6) for r in latest}
        if len(values) > 1:
            conflicts += 1
        mean_value = sum(r.generation_mw for r in latest) / len(latest)
        base = latest[0]
        out.append(
            ActualRecord(
                delivery_start_utc=base.delivery_start_utc,
                publish_time_utc=base.publish_time_utc,
                settlement_date=base.settlement_date,
                settlement_period=base.settlement_period,
                fuel_type=base.fuel_type,
                generation_mw=mean_value,
            )
        )
    out.sort(key=lambda r: r.delivery_start_utc)
    return out, removed, conflicts


def _dedupe_forecast(
    records: list[ForecastRecord],
) -> tuple[list[ForecastRecord], int, int]:
    grouped: dict[tuple[dt.datetime, dt.datetime], list[ForecastRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.delivery_start_utc, record.publish_time_utc)].append(record)

    out: list[ForecastRecord] = []
    removed = 0
    conflicts = 0
    for (_start, _publish), group in grouped.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        removed += len(group) - 1
        values = {round(r.generation_mw, 6) for r in group}
        if len(values) > 1:
            conflicts += 1
        base = group[0]
        mean_value = sum(r.generation_mw for r in group) / len(group)
        out.append(
            ForecastRecord(
                delivery_start_utc=base.delivery_start_utc,
                publish_time_utc=base.publish_time_utc,
                generation_mw=mean_value,
            )
        )
    out.sort(key=lambda r: (r.delivery_start_utc, r.publish_time_utc))
    return out, removed, conflicts
