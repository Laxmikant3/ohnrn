"""Shared synthetic fixtures for automated tests only.

These records never enter production analytics: every fixture lives in a
pytest-isolated temporary cache directory and is marked ``is_synthetic=True``.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.cache import CacheStore
from app.utils.timeutils import build_delivery_grid, iso_z, localize_wall_time

LONDON = ZoneInfo("Europe/London")


def _forecast_value(hour: int, vintage_index: int) -> float:
    return 12000.0 + (hour % 12) * 180.0 + vintage_index * 60.0


def synthetic_actuals(start: dt.date, end: dt.date) -> list[dict]:
    rows = []
    for interval in build_delivery_grid(start, end, LONDON):
        value = 12000.0 + ((interval.settlement_period * 47) % 1800)
        rows.append(
            {
                "start_time": iso_z(interval.start_utc),
                "publish_time": iso_z(interval.end_utc),
                "settlement_date": interval.delivery_date.isoformat(),
                "settlement_period": interval.settlement_period,
                "fuel_type": "WIND",
                "generation_mw": value,
            }
        )
    return rows


def synthetic_forecasts(start: dt.date, end: dt.date) -> list[dict]:
    """Hourly WINDFOR vintages published at 09:30, 11:30, 15:30 and 22:30 D-1."""
    rows = []
    day = start - dt.timedelta(days=1)
    while day <= end + dt.timedelta(days=1):
        publish_day = day - dt.timedelta(days=1)
        times = [dt.time(9, 30), dt.time(11, 30), dt.time(15, 30), dt.time(22, 30)]
        for hour in range(24):
            delivery = localize_wall_time(day, dt.time(hour, 0), LONDON)
            for index, clock in enumerate(times):
                publish = localize_wall_time(publish_day, clock, LONDON)
                rows.append(
                    {
                        "start_time": iso_z(delivery),
                        "publish_time": iso_z(publish),
                        "generation_mw": _forecast_value(hour, index),
                    }
                )
        day += dt.timedelta(days=1)
    return rows


def build_settings(tmp_path, start: dt.date, end: dt.date) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        analysis_start=start,
        analysis_end=end,
        allow_refresh=False,
        log_level="WARNING",
    )


def seed_cache(settings: Settings) -> CacheStore:
    cache = CacheStore(settings)
    now = dt.datetime.now(dt.UTC)
    actual = synthetic_actuals(settings.analysis_start, settings.analysis_end)
    forecast = synthetic_forecasts(settings.analysis_start, settings.analysis_end)
    cache.write_actual(
        records=actual,
        windows=[
            {
                "from": settings.analysis_start.isoformat(),
                "to": settings.analysis_end.isoformat(),
            }
        ],
        stats={"raw_records": len(actual), "valid_records": len(actual)},
        retrieved_at=now,
        first_retrieved_at=now,
        is_synthetic=True,
    )
    cache.write_forecast(
        records=forecast,
        windows=[{"from": "synthetic", "to": "synthetic"}],
        stats={"raw_records": len(forecast), "valid_records": len(forecast)},
        retrieved_at=now,
        first_retrieved_at=now,
        granularity_minutes=60,
        is_synthetic=True,
    )
    return cache


@pytest.fixture
def analysis_range() -> tuple[dt.date, dt.date]:
    return dt.date(2026, 1, 10), dt.date(2026, 1, 12)


@pytest.fixture
def settings(tmp_path, analysis_range) -> Settings:
    return build_settings(tmp_path, *analysis_range)


@pytest.fixture
def seeded_settings(settings) -> Settings:
    seed_cache(settings)
    return settings


@pytest.fixture
def api_client(seeded_settings):
    app = create_app(seeded_settings)
    with TestClient(app) as client:
        yield client
