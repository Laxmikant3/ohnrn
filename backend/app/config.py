"""Application configuration.

All configuration is environment driven. Defaults are safe for local demo use and
are intentionally explicit about the pilot procurement-cutoff assumption.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- Application -----------------------------------------------------
    app_name: str = "WindIQ API"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    # --- Market / analysis ----------------------------------------------
    market_timezone: str = "Europe/London"
    analysis_start: dt.date = dt.date(2026, 1, 1)
    analysis_end: dt.date = dt.date(2026, 1, 31)
    default_cutoff_time: str = "11:00"
    default_cutoff_days_before: int = 1
    mape_min_actual_mw: float = 1.0

    # --- Elexon BMRS ------------------------------------------------------
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    elexon_timeout_seconds: float = 60.0
    elexon_connect_timeout_seconds: float = 10.0
    elexon_max_retries: int = 3
    elexon_backoff_base_seconds: float = 0.8
    elexon_min_interval_ms: int = 250
    elexon_forecast_padding_days_before: int = 8
    elexon_forecast_padding_days_after: int = 3
    elexon_actual_chunk_days: int = 31
    elexon_forecast_chunk_days: int = 12

    # --- Cache ------------------------------------------------------------
    data_dir: Path = Field(default_factory=_default_data_dir)
    cache_stale_after_hours: float = 168.0
    upstream_probe_ttl_seconds: int = 300

    # --- API --------------------------------------------------------------
    cors_origins: str = (
        "http://localhost:5173,http://localhost:4173,http://localhost:3000,http://127.0.0.1:5173"
    )
    default_page_size: int = 50
    max_page_size: int = 500
    allow_refresh: bool = False
    admin_token: str = ""

    # --- Synthetic test/demo data ----------------------------------------
    # Never enabled implicitly. Only the test suite uses synthetic fixtures
    # directly against pure functions; the running service only loads Elexon
    # data from the cache directory.
    allow_synthetic: bool = False

    @field_validator("default_cutoff_time")
    @classmethod
    def _validate_cutoff_time(cls, value: str) -> str:
        try:
            parsed = dt.time.fromisoformat(value)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError("CUTOFF time must be HH:MM") from exc
        if parsed.second or parsed.microsecond:
            raise ValueError("CUTOFF time must be HH:MM")
        return value

    @field_validator("default_cutoff_days_before")
    @classmethod
    def _validate_days_before(cls, value: int) -> int:
        if value < 0 or value > 7:
            raise ValueError("cutoff days-before must be between 0 and 7")
        return value

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.market_timezone)

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def cutoff_time_value(self) -> dt.time:
        return dt.time.fromisoformat(self.default_cutoff_time)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
