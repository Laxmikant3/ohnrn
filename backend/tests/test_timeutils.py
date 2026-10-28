"""Timezone, delivery grid and cutoff tests (including DST transitions)."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from app.utils.timeutils import (
    build_delivery_grid,
    cutoff_for_delivery_date,
    localize_wall_time,
    parse_api_timestamp,
)

LONDON = ZoneInfo("Europe/London")
UTC = dt.UTC


def test_parse_api_timestamp_z_suffix():
    parsed = parse_api_timestamp("2026-01-01T00:00:00Z")
    assert parsed == dt.datetime(2026, 1, 1, tzinfo=UTC)
    assert parsed.tzinfo is not None


def test_parse_api_timestamp_naive_is_utc():
    parsed = parse_api_timestamp("2026-01-01T00:00:00")
    assert parsed == dt.datetime(2026, 1, 1, tzinfo=UTC)


def test_parse_api_timestamp_rejects_garbage():
    assert parse_api_timestamp("not-a-date") is None
    assert parse_api_timestamp("") is None


def test_january_grid_is_48_per_day():
    grid = build_delivery_grid(dt.date(2026, 1, 1), dt.date(2026, 1, 31), LONDON)
    assert len(grid) == 31 * 48
    assert grid[0].settlement_period == 1
    assert grid[47].settlement_period == 48
    assert grid[0].start_utc == dt.datetime(2026, 1, 1, tzinfo=UTC)
    assert grid[0].label == "00:00–00:30"


def test_spring_forward_day_has_46_intervals():
    grid = build_delivery_grid(dt.date(2026, 3, 29), dt.date(2026, 3, 29), LONDON)
    assert len(grid) == 46
    assert grid[-1].settlement_period == 46


def test_fall_back_day_has_50_intervals():
    grid = build_delivery_grid(dt.date(2026, 10, 25), dt.date(2026, 10, 25), LONDON)
    assert len(grid) == 50
    assert grid[-1].settlement_period == 50


def test_cutoff_is_1100_london_preceding_day_in_gmt():
    cutoff = cutoff_for_delivery_date(dt.date(2026, 1, 2), LONDON, dt.time(11, 0), 1)
    assert cutoff == dt.datetime(2026, 1, 1, 11, 0, tzinfo=UTC)


def test_cutoff_respects_british_summer_time():
    cutoff = cutoff_for_delivery_date(dt.date(2026, 6, 2), LONDON, dt.time(11, 0), 1)
    # 11:00 BST == 10:00 UTC
    assert cutoff == dt.datetime(2026, 6, 1, 10, 0, tzinfo=UTC)


def test_cutoff_on_dst_transition_day_is_london_wall_clock():
    # The day before 30 March 2026 is the spring-forward Sunday.
    cutoff = cutoff_for_delivery_date(dt.date(2026, 3, 30), LONDON, dt.time(11, 0), 1)
    assert cutoff == dt.datetime(2026, 3, 29, 10, 0, tzinfo=UTC)


def test_nonexistent_local_time_moves_forward():
    # 01:30 does not exist on the spring-forward date.
    resolved = localize_wall_time(dt.date(2026, 3, 29), dt.time(1, 30), LONDON)
    assert resolved.astimezone(UTC) == dt.datetime(2026, 3, 29, 1, 0, tzinfo=UTC)


def test_cutoff_days_before_zero():
    cutoff = cutoff_for_delivery_date(dt.date(2026, 1, 5), LONDON, dt.time(11, 0), 0)
    assert cutoff == dt.datetime(2026, 1, 5, 11, 0, tzinfo=UTC)


def test_grid_rejects_reversed_range():
    with pytest.raises(ValueError):
        build_delivery_grid(dt.date(2026, 1, 3), dt.date(2026, 1, 2), LONDON)
