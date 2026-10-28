"""Forecast eligibility, cutoff enforcement and vintage selection."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd

from app.domain import VINTAGE_LATEST
from app.services.cache import CacheStore
from app.services.dataset import DatasetStore
from app.services.selection import build_selection
from app.utils.timeutils import build_delivery_grid, iso_z
from tests.conftest import build_settings, synthetic_actuals

LONDON = ZoneInfo("Europe/London")
UTC = dt.UTC


def _service_selection(settings, vintage="decision_cutoff"):
    dataset = DatasetStore(settings, CacheStore(settings)).get()
    return build_selection(
        dataset,
        settings,
        settings.analysis_start,
        settings.analysis_end,
        settings.default_cutoff_time,
        settings.default_cutoff_days_before,
        vintage,
    )


def test_latest_eligible_forecast_is_selected(seeded_settings):
    frame = _service_selection(seeded_settings)
    # For every interval with a forecast, the selected publish must be the max
    # eligible publication: 09:30 Europe/London on the preceding day.
    selected = frame[frame["forecast_mw"].notna()]
    assert not selected.empty
    assert selected["publish_time_utc"].dt.hour.nunique() == 1
    assert selected["publish_time_utc"].dt.hour.iloc[0] == 9
    assert (selected["publish_time_utc"] <= selected["cutoff_time_utc"]).all()
    assert (selected["is_cutoff_compliant"]).all()


def test_zero_cutoff_violations_across_population(seeded_settings):
    frame = _service_selection(seeded_settings)
    leaked = (
        frame["publish_time_utc"].notna()
        & (frame["publish_time_utc"] > frame["cutoff_time_utc"])
        & (frame["eligibility"] == "eligible")
    )
    assert int(leaked.sum()) == 0


def test_cutoff_boundary_is_inclusive(tmp_path):
    settings = build_settings(tmp_path, dt.date(2026, 1, 10), dt.date(2026, 1, 10))
    cache = CacheStore(settings)
    now = dt.datetime.now(UTC)
    cache.write_actual(
        records=synthetic_actuals(dt.date(2026, 1, 10), dt.date(2026, 1, 10)),
        windows=[],
        stats={},
        retrieved_at=now,
        first_retrieved_at=now,
        is_synthetic=True,
    )
    # Publish exactly at the 11:00 London cutoff; only interval 00:00.
    cache.write_forecast(
        records=[
            {
                "start_time": "2026-01-10T00:00:00Z",
                "publish_time": "2026-01-09T11:00:00Z",
                "generation_mw": 12345.0,
            }
        ],
        windows=[],
        stats={},
        retrieved_at=now,
        first_retrieved_at=now,
        granularity_minutes=60,
        is_synthetic=True,
    )
    frame = _service_selection(settings)
    row = frame[frame["delivery_start_utc"] == pd.Timestamp("2026-01-10T00:00:00Z")].iloc[0]
    assert row["eligibility"] == "eligible"
    assert row["is_cutoff_compliant"]
    assert row["forecast_mw"] == 12345.0


def test_post_cutoff_forecast_is_never_used_to_backfill(tmp_path):
    """The critical no-look-ahead invariant.

    The only forecast for the interval was published at 12:00 London, one hour
    after the cutoff. It must not be selected: the interval stays missing.
    """
    settings = build_settings(tmp_path, dt.date(2026, 1, 10), dt.date(2026, 1, 10))
    cache = CacheStore(settings)
    now = dt.datetime.now(UTC)
    cache.write_actual(
        records=synthetic_actuals(dt.date(2026, 1, 10), dt.date(2026, 1, 10)),
        windows=[],
        stats={},
        retrieved_at=now,
        first_retrieved_at=now,
        is_synthetic=True,
    )
    cache.write_forecast(
        records=[
            {
                "start_time": "2026-01-10T00:00:00Z",
                "publish_time": "2026-01-09T12:00:00Z",
                "generation_mw": 9999.0,
            }
        ],
        windows=[],
        stats={},
        retrieved_at=now,
        first_retrieved_at=now,
        granularity_minutes=60,
        is_synthetic=True,
    )
    frame = _service_selection(settings)
    row = frame[frame["delivery_start_utc"] == pd.Timestamp("2026-01-10T00:00:00Z")].iloc[0]
    assert pd.isna(row["forecast_mw"])
    assert row["eligibility"] == "missing_forecast"
    assert row["status"] == "missing_forecast"
    assert row["publish_time_utc"] is pd.NaT or pd.isna(row["publish_time_utc"])


def test_latest_available_mode_is_retrospective(seeded_settings):
    frame = _service_selection(seeded_settings, vintage=VINTAGE_LATEST)
    selected = frame[frame["forecast_mw"].notna()]
    assert (selected["eligibility"] == "retrospective").any()
    assert (~selected["is_cutoff_compliant"]).any()


def test_missing_actual_is_reported(tmp_path):
    settings = build_settings(tmp_path, dt.date(2026, 1, 10), dt.date(2026, 1, 10))
    cache = CacheStore(settings)
    now = dt.datetime.now(UTC)
    cache.write_actual(
        records=synthetic_actuals(dt.date(2026, 1, 10), dt.date(2026, 1, 10))[:2],
        windows=[],
        stats={},
        retrieved_at=now,
        first_retrieved_at=now,
        is_synthetic=True,
    )
    cache.write_forecast(
        records=[
            {
                "start_time": "2026-01-10T00:00:00Z",
                "publish_time": "2026-01-09T09:30:00Z",
                "generation_mw": 12000.0,
            },
            {
                "start_time": "2026-01-10T02:00:00Z",
                "publish_time": "2026-01-09T09:30:00Z",
                "generation_mw": 13000.0,
            },
        ],
        windows=[],
        stats={},
        retrieved_at=now,
        first_retrieved_at=now,
        granularity_minutes=60,
        is_synthetic=True,
    )
    frame = _service_selection(settings)
    statuses = dict(frame["status"].value_counts())
    assert statuses.get("missing_actual") == 2
    assert statuses.get("matched") == 2
    assert (frame["status"] == "missing_forecast").sum() == 44


def test_hourly_forecast_expands_to_both_settlement_periods(seeded_settings):
    frame = _service_selection(seeded_settings)
    first = frame[frame["delivery_start_utc"].isin(
        [pd.Timestamp("2026-01-10T00:00:00Z"), pd.Timestamp("2026-01-10T00:30:00Z")]
    )]
    assert len(first) == 2
    assert first["forecast_mw"].nunique() == 1


def test_lead_time_is_publish_to_delivery(seeded_settings):
    frame = _service_selection(seeded_settings)
    row = frame[frame["delivery_start_utc"] == pd.Timestamp("2026-01-10T00:00:00Z")].iloc[0]
    assert row["lead_time_hours"] == 14.5


def test_selection_has_one_row_per_expected_interval(seeded_settings):
    frame = _service_selection(seeded_settings)
    expected = len(
        build_delivery_grid(
            seeded_settings.analysis_start, seeded_settings.analysis_end, LONDON
        )
    )
    assert len(frame) == expected
    assert frame["delivery_start_utc"].is_unique
    assert iso_z(frame.iloc[0]["delivery_start_utc"]) == "2026-01-10T00:00:00Z"
