"""Timezone-aware delivery-interval and cutoff helpers.

Market-facing dates always use Europe/London via the IANA timezone database
(``zoneinfo``). No manual UTC-offset arithmetic is performed anywhere.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

UTC = dt.UTC
HALF_HOUR = dt.timedelta(minutes=30)


def parse_api_timestamp(value: str | dt.datetime | None) -> dt.datetime | None:
    """Parse an Elexon ISO-8601 timestamp into an aware UTC datetime.

    Elexon timestamps are documented as ``date-time`` and returned with a ``Z``
    suffix. Naive values are interpreted as UTC (and flagged by the normaliser),
    never as local time.
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = dt.datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def is_naive(value: str | dt.datetime | None) -> bool:
    if value is None:
        return False
    if isinstance(value, dt.datetime):
        return value.tzinfo is None
    text = str(value).strip()
    return not (text.endswith("Z") or "+" in text[10:] or "-" in text[10:])


def to_market_date(value: dt.datetime, tz: ZoneInfo) -> dt.date:
    return value.astimezone(tz).date()


def localize_wall_time(day: dt.date, clock: dt.time, tz: ZoneInfo) -> dt.datetime:
    """Return an aware datetime for a London wall-clock time on ``day``.

    DST-safe: if the wall time does not exist (spring-forward gap) we advance in
    one-minute steps to the first valid instant. If it is ambiguous
    (autumn fall-back) Python's ``fold=0`` selects the first occurrence, which is
    documented behaviour for this application.
    """
    naive = dt.datetime.combine(day, clock)
    for offset_minutes in range(0, 181):
        candidate = naive + dt.timedelta(minutes=offset_minutes)
        aware = candidate.replace(tzinfo=tz)
        round_trip = aware.astimezone(UTC).astimezone(tz).replace(tzinfo=None)
        if round_trip == candidate:
            return aware
    raise ValueError(f"Could not localise {naive} in {tz.key}")


def cutoff_for_delivery_date(
    delivery_date: dt.date,
    tz: ZoneInfo,
    cutoff_time: dt.time,
    days_before: int,
) -> dt.datetime:
    """Cutoff instant (UTC) for a London delivery date.

    Default pilot assumption: 11:00 Europe/London on the preceding calendar day.
    """
    cutoff_date = delivery_date - dt.timedelta(days=days_before)
    return localize_wall_time(cutoff_date, cutoff_time, tz).astimezone(UTC)


@dataclass(frozen=True)
class DeliveryInterval:
    start_utc: dt.datetime
    end_utc: dt.datetime
    delivery_date: dt.date
    settlement_period: int
    local_start: dt.datetime

    @property
    def label(self) -> str:
        end_local = self.end_utc.astimezone(self.local_start.tzinfo)
        return f"{self.local_start:%H:%M}–{end_local:%H:%M}"


def london_midnight(day: dt.date, tz: ZoneInfo) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(0, 0), tzinfo=tz)


def build_delivery_grid(start: dt.date, end: dt.date, tz: ZoneInfo) -> list[DeliveryInterval]:
    """Enumerate 30-minute delivery intervals for inclusive London dates.

    Uses local midnights so DST transition days correctly yield 46 or 50
    settlement periods rather than a hard-coded 48.
    """
    if end < start:
        raise ValueError("end date must not be before start date")
    intervals: list[DeliveryInterval] = []
    day = start
    while day <= end:
        # Iterate real 30-minute UTC intervals between successive London
        # midnights. This yields 46 intervals on spring-forward days and 50 on
        # fall-back days instead of a hard-coded 48.
        day_start_utc = london_midnight(day, tz).astimezone(UTC)
        day_end_utc = london_midnight(day + dt.timedelta(days=1), tz).astimezone(UTC)
        cursor = day_start_utc
        period = 1
        while cursor < day_end_utc:
            intervals.append(
                DeliveryInterval(
                    start_utc=cursor,
                    end_utc=cursor + HALF_HOUR,
                    delivery_date=day,
                    settlement_period=period,
                    local_start=cursor.astimezone(tz),
                )
            )
            cursor += HALF_HOUR
            period += 1
        day += dt.timedelta(days=1)
    return intervals


def expected_intervals(start: dt.date, end: dt.date, tz: ZoneInfo) -> int:
    return len(build_delivery_grid(start, end, tz))


def hours_between(later: dt.datetime, earlier: dt.datetime) -> float:
    return round((later - earlier).total_seconds() / 3600.0, 3)


def iso_z(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
