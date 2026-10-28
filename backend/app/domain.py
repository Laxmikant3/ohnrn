"""Internal domain models and constants for WindIQ."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Literal

UTC = dt.UTC

SCHEMA_VERSION = 1
SOURCE_ACTUAL = "FUELHH"
SOURCE_FORECAST = "WINDFOR"
FUEL_TYPE = "WIND"

ELIGIBILITY_ELIGIBLE = "eligible"
ELIGIBILITY_MISSING = "missing_forecast"
ELIGIBILITY_RETROSPECTIVE = "retrospective"

STATUS_MATCHED = "matched"
STATUS_MISSING_ACTUAL = "missing_actual"
STATUS_MISSING_FORECAST = "missing_forecast"
STATUS_UNMATCHED = "unmatched"

VINTAGE_CUTOFF = "decision_cutoff"
VINTAGE_LATEST = "latest_available"

LEAD_TIME_BUCKETS: tuple[tuple[str, str, float, float | None], ...] = (
    ("lt6", "< 6h", 0.0, 6.0),
    ("6to12", "6–12h", 6.0, 12.0),
    ("12to18", "12–18h", 12.0, 18.0),
    ("18to24", "18–24h", 18.0, 24.0),
    ("24to36", "24–36h", 24.0, 36.0),
    ("36to48", "36–48h", 36.0, 48.0),
    ("gte48", "48h +", 48.0, None),
)


def lead_time_bucket(hours: float | None) -> str | None:
    if hours is None:
        return None
    for key, _label, low, high in LEAD_TIME_BUCKETS:
        if hours >= low and (high is None or hours < high):
            return key
    return None


def lead_time_bucket_label(key: str | None) -> str | None:
    for bucket_key, label, _low, _high in LEAD_TIME_BUCKETS:
        if bucket_key == key:
            return label
    return None


@dataclass(frozen=True)
class ActualRecord:
    delivery_start_utc: dt.datetime
    publish_time_utc: dt.datetime | None
    settlement_date: dt.date | None
    settlement_period: int | None
    fuel_type: str
    generation_mw: float


@dataclass(frozen=True)
class ForecastRecord:
    delivery_start_utc: dt.datetime
    publish_time_utc: dt.datetime
    generation_mw: float


@dataclass
class NormalizationStats:
    raw_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    duplicates_removed: int = 0
    duplicate_conflicts: int = 0
    naive_timestamps: int = 0
    negative_values: int = 0
    excluded_post_delivery: int = 0
    invalid_samples: list[dict[str, Any]] = field(default_factory=list)

    def add_invalid(self, reason: str, sample: Any) -> None:
        self.invalid_records += 1
        if len(self.invalid_samples) < 50:
            self.invalid_samples.append(
                {"reason": reason, "record": sample if isinstance(sample, dict) else repr(sample)}
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_records": self.raw_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "duplicates_removed": self.duplicates_removed,
            "duplicate_conflicts": self.duplicate_conflicts,
            "naive_timestamps": self.naive_timestamps,
            "negative_values": self.negative_values,
            "excluded_post_delivery": self.excluded_post_delivery,
            "invalid_samples": self.invalid_samples,
        }


MetricValue = float | None
VintageMode = Literal["decision_cutoff", "latest_available"]
