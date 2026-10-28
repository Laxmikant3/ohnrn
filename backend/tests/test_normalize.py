"""Normalisation, validation and deduplication tests."""

from __future__ import annotations

import datetime as dt
import math

from app.domain import NormalizationStats
from app.services.normalize import normalize_actual_records, normalize_forecast_records

UTC = dt.UTC


def actual(**overrides):
    record = {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T00:30:00Z",
        "startTime": "2026-01-01T00:00:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 1,
        "fuelType": "WIND",
        "generation": 13756,
    }
    record.update(overrides)
    return record


def forecast(**overrides):
    record = {
        "dataset": "WINDFOR",
        "publishTime": "2025-12-31T09:30:00Z",
        "startTime": "2026-01-01T00:00:00Z",
        "generation": 19466,
    }
    record.update(overrides)
    return record


def test_actual_parsing_and_unit():
    records, stats = normalize_actual_records([actual()])
    assert stats.valid_records == 1
    assert stats.invalid_records == 0
    record = records[0]
    assert record.delivery_start_utc == dt.datetime(2026, 1, 1, tzinfo=UTC)
    assert record.generation_mw == 13756
    assert record.settlement_period == 1
    assert record.fuel_type == "WIND"


def test_actual_rejects_wrong_fuel_missing_and_malformed():
    records, stats = normalize_actual_records(
        [
            actual(fuelType="NUCLEAR"),
            actual(generation=None),
            actual(generation="not-a-number"),
            actual(startTime=None),
            actual(settlementPeriod=99),
            actual(generation=1e12),
            "not-an-object",
        ]
    )
    assert records == []
    assert stats.invalid_records == 7


def test_actual_duplicate_keeps_latest_publication():
    earlier = actual(generation=100, publishTime="2026-01-01T00:30:00Z")
    later = actual(generation=200, publishTime="2026-01-01T01:00:00Z")
    records, stats = normalize_actual_records([earlier, later])
    assert len(records) == 1
    assert records[0].generation_mw == 200
    assert stats.duplicates_removed == 1
    assert stats.duplicate_conflicts == 0


def test_actual_conflicting_same_publication_is_averaged_and_counted():
    first = actual(generation=100)
    second = actual(generation=200)
    records, stats = normalize_actual_records([first, second])
    assert len(records) == 1
    assert records[0].generation_mw == 150
    assert stats.duplicate_conflicts == 1


def test_forecast_rejects_post_delivery_publication():
    records, stats = normalize_forecast_records(
        [forecast(publishTime="2026-01-01T01:30:00Z")]
    )
    assert records == []
    assert stats.excluded_post_delivery == 1
    assert stats.invalid_records == 0


def test_forecast_requires_publish_time():
    records, stats = normalize_forecast_records([forecast(publishTime=None)])
    assert records == []
    assert stats.invalid_records == 1


def test_forecast_rejects_negative_generation():
    records, stats = normalize_forecast_records([forecast(generation=-1)])
    assert records == []
    assert stats.invalid_records == 1


def test_forecast_duplicate_collapses_same_vintage():
    records, stats = normalize_forecast_records([forecast(), forecast(generation=19000)])
    assert len(records) == 1
    assert records[0].generation_mw == 19233.0
    assert stats.duplicates_removed == 1
    assert stats.duplicate_conflicts == 1


def test_naive_timestamp_is_counted():
    _, stats = normalize_forecast_records(
        [forecast(publishTime="2025-12-31T09:30:00", startTime="2026-01-01T00:00:00")]
    )
    assert stats.naive_timestamps == 1


def test_stats_serialisation_includes_post_delivery_counter():
    stats = NormalizationStats(excluded_post_delivery=4)
    payload = stats.to_dict()
    assert payload["excluded_post_delivery"] == 4
    assert math.isfinite(payload["raw_records"])
