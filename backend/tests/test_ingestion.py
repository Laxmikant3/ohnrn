"""Ingestion pipeline integration tests with a fake upstream client."""

from __future__ import annotations

import asyncio
import datetime as dt

from app.clients.elexon import ElexonUnavailable, FetchResult
from app.services.cache import CacheStore
from app.services.dataset import DatasetStore
from app.services.ingestion import ingest_window
from tests.conftest import build_settings


class FakeClient:
    def __init__(self, fail_forecast: bool = False) -> None:
        self.fail_forecast = fail_forecast
        self.actual_calls = 0
        self.forecast_calls = 0

    async def fetch_actual_wind(self, start, end):
        self.actual_calls += 1
        records = []
        for period in range(1, 49):
            start_hour = (period - 1) // 2
            minute = 0 if period % 2 == 1 else 30
            records.append(
                {
                    "dataset": "FUELHH",
                    "publishTime": f"2026-01-10T{start_hour:02d}:{minute:02d}:00Z",
                    "startTime": f"2026-01-10T{start_hour:02d}:{minute:02d}:00Z",
                    "settlementDate": "2026-01-10",
                    "settlementPeriod": period,
                    "fuelType": "WIND",
                    "generation": 12000 + period,
                }
            )
        return FetchResult(
            records=records, url="fake", params={}, attempts=1, duration_seconds=0.01, fingerprint="a"
        )

    async def fetch_forecast_wind(self, start, end):
        self.forecast_calls += 1
        if self.fail_forecast:
            raise ElexonUnavailable("simulated WINDFOR outage")
        records = []
        for hour in range(24):
            for publish_hour in (9, 11):
                records.append(
                    {
                        "dataset": "WINDFOR",
                        "publishTime": f"2026-01-09T{publish_hour:02d}:30:00Z",
                        "startTime": f"2026-01-10T{hour:02d}:00:00Z",
                        "generation": 12000 + hour * 10 + publish_hour,
                    }
                )
        return FetchResult(
            records=records, url="fake", params={}, attempts=1, duration_seconds=0.01, fingerprint="f"
        )


def test_ingest_writes_cache_and_is_idempotent(tmp_path):
    settings = build_settings(tmp_path, dt.date(2026, 1, 10), dt.date(2026, 1, 10))
    cache = CacheStore(settings)
    client = FakeClient()
    first = asyncio.run(
        ingest_window(settings, cache, dt.date(2026, 1, 10), dt.date(2026, 1, 10), client=client)
    )
    assert first.complete is True
    assert first.actual_records == 48
    assert first.forecast_records == 48
    assert cache.paths()["actual"].exists()
    assert cache.paths()["forecast"].exists()

    dataset = DatasetStore(settings, cache).get(force_reload=True)
    assert len(dataset.actual) == 48
    # 24 hourly values expanded to 48 half-hourly intervals.
    assert len(dataset.forecast) == 96
    assert dataset.forecast_granularity_minutes == 60

    second = asyncio.run(
        ingest_window(settings, cache, dt.date(2026, 1, 10), dt.date(2026, 1, 10), client=client)
    )
    assert second.actual_records == 48
    assert second.forecast_records == 48
    stats = cache.read_forecast()["stats"]
    assert stats["duplicates_removed"] >= 48


def test_ingest_partial_failure_preserves_actuals(tmp_path):
    settings = build_settings(tmp_path, dt.date(2026, 1, 10), dt.date(2026, 1, 10))
    cache = CacheStore(settings)
    result = asyncio.run(
        ingest_window(
            settings,
            cache,
            dt.date(2026, 1, 10),
            dt.date(2026, 1, 10),
            client=FakeClient(fail_forecast=True),
        )
    )
    assert result.complete is False
    assert result.actual_records == 48
    assert result.forecast_records == 0
    assert result.forecast_error
    assert cache.paths()["actual"].exists()
    assert not cache.paths()["forecast"].exists()
    events = cache.read_manifest()["retrieval_events"]
    assert any(event["status"] == "error" for event in events)
    assert any(event["status"] == "success" for event in events)
