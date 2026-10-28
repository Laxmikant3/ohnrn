"""Pydantic response schemas for the versioned API."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class MetricOut(APIModel):
    value: float | None
    n: int
    unit: str
    excluded: int | None = None
    expected: int | None = None


class PopulationOut(APIModel):
    expected_intervals: int
    selected_intervals: int
    matched_intervals: int
    missing_forecast: int
    missing_actual: int
    excluded_by_lead_time: int = 0
    mape_excluded: int | None = None
    mape_min_actual_mw: float | None = None


class DataStatusOut(APIModel):
    mode: str
    source: str
    cached: bool
    stale: bool
    is_synthetic: bool
    last_retrieval: dt.datetime | None = None
    cache_age_hours: float | None = None
    stale_after_hours: float | None = None
    actual_records: int
    forecast_records: int
    forecast_delivery_intervals: int
    forecast_expanded_intervals: int
    forecast_vintages: int
    forecast_granularity_minutes: int
    forecast_expanded_to_half_hourly: bool


class CutoffOut(APIModel):
    time: str
    days_before: int
    timezone: str
    description: str
    example_delivery_date: str | None = None
    example_cutoff_utc: dt.datetime | None = None
    assumption: bool = True


class PeriodOut(APIModel):
    start_date: str
    end_date: str
    label: str
    timezone: str
    expected_intervals: int
    mode: str


class FiltersOut(APIModel):
    start_date: str
    end_date: str
    cutoff: str
    cutoff_days_before: int
    vintage: str
    vintage_label: str
    lead_time_bucket: str | None = None


class SeriesPointOut(APIModel):
    timestamp: dt.datetime
    forecast_mw: float | None = None
    actual_mw: float | None = None
    error_mw: float | None = None
    absolute_error_mw: float | None = None
    n: int


class DailyRowOut(APIModel):
    date: str
    mae: float | None
    rmse: float | None
    bias: float | None
    mape: float | None
    wape: float | None
    n: int
    expected: int
    coverage_pct: float | None
    overforecast_count: int
    underforecast_count: int


class IntervalOut(APIModel):
    delivery_interval: dt.datetime
    delivery_date: str
    settlement_period: int
    interval_label: str
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    absolute_error_mw: float | None
    percentage_error: float | None
    publish_time: dt.datetime | None
    lead_time_hours: float | None
    eligibility: str | None
    status: str | None


class RevisionBucketOut(APIModel):
    key: str
    label: str
    min_hours: float
    max_hours: float | None
    mean_forecast_mw: float | None
    mean_decision_mw: float | None
    mean_delta_vs_decision_mw: float | None
    mean_abs_revision_mw: float | None
    mean_lead_time_hours: float | None
    n: int


class LatestForecastKpi(APIModel):
    value: float | None
    unit: str
    delivery_interval: dt.datetime | None = None
    delivery_date: str | None = None
    settlement_period: int | None = None
    interval_label: str | None = None
    publish_time: dt.datetime | None = None
    lead_time_hours: float | None = None
    status: str
    eligibility: str | None = None


class LatestActualKpi(APIModel):
    value: float | None
    unit: str
    delivery_interval: dt.datetime | None = None
    delivery_date: str | None = None
    settlement_period: int | None = None
    interval_label: str | None = None
    status: str


class LatestErrorKpi(APIModel):
    value: float | None
    unit: str
    delivery_interval: dt.datetime | None = None
    delivery_date: str | None = None
    settlement_period: int | None = None
    percentage_error: float | None = None
    direction: str | None = None
    status: str


class KpisOut(APIModel):
    latest_eligible_forecast: LatestForecastKpi
    latest_actual: LatestActualKpi
    latest_error: LatestErrorKpi
    mae: MetricOut
    rmse: MetricOut
    coverage: MetricOut
    bias: MetricOut


class OverviewOut(APIModel):
    mode: str
    period: PeriodOut
    cutoff: CutoffOut
    filters: FiltersOut
    data_status: DataStatusOut
    kpis: KpisOut
    population: PopulationOut
    series: list[SeriesPointOut]
    series_resolution: str
    daily: list[DailyRowOut]
    revision_curve: list[RevisionBucketOut]
    top_overforecast: list[IntervalOut]
    top_underforecast: list[IntervalOut]
    procurement_context: str


class ForecastRowOut(APIModel):
    delivery_interval: dt.datetime
    delivery_date: str
    settlement_period: int
    interval_label: str
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None
    absolute_error_mw: float | None
    percentage_error: float | None
    publish_time: dt.datetime | None
    lead_time_hours: float | None
    lead_time_bucket: str | None = None
    lead_time_bucket_label: str | None = None
    cutoff_time: dt.datetime | None = None
    eligibility: str
    status: str
    is_cutoff_compliant: bool


class PaginationOut(APIModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class SortOut(APIModel):
    by: str
    direction: str


class ForecastPageOut(APIModel):
    period: PeriodOut
    cutoff: CutoffOut
    filters: FiltersOut
    population: PopulationOut
    items: list[ForecastRowOut]
    pagination: PaginationOut
    sort: SortOut


class VintageOut(APIModel):
    publish_time: dt.datetime
    forecast_mw: float
    lead_time_hours: float
    eligible: bool
    selected: bool
    revision_from_previous_mw: float | None = None
    revision_from_decision_mw: float | None = None


class VintagesOut(APIModel):
    delivery_interval: dt.datetime
    delivery_date: str
    settlement_period: int
    interval_label: str
    market_timezone: str
    cutoff: dict[str, Any]
    actual_mw: float | None
    decision_forecast: dict[str, Any]
    latest_forecast: dict[str, Any]
    revision: dict[str, Any]
    vintages: list[VintageOut]
    retrospective_notice: str


class SummaryOut(APIModel):
    period: PeriodOut
    cutoff: CutoffOut
    filters: FiltersOut
    population: PopulationOut
    metrics: dict[str, MetricOut]
    error_stats: dict[str, float | None]
    direction: dict[str, float | int | None]
    distribution: list[dict[str, Any]]
    top_overforecast: list[IntervalOut]
    top_underforecast: list[IntervalOut]
    lead_time_buckets: list[dict[str, Any]]
    notes: list[str]


class DailyAnalyticsOut(APIModel):
    period: PeriodOut
    cutoff: CutoffOut
    filters: FiltersOut
    population: PopulationOut
    days: list[DailyRowOut]


class HourRowOut(APIModel):
    hour: int
    label: str
    mae: float | None
    rmse: float | None
    bias: float | None
    mape: float | None
    n: int


class HeatmapCellOut(APIModel):
    date: str
    hour: int
    mae: float | None
    n: int


class HeatmapOut(APIModel):
    dates: list[str]
    hours: list[int]
    cells: list[HeatmapCellOut]
    max_mae: float


class HourlyAnalyticsOut(APIModel):
    period: PeriodOut
    cutoff: CutoffOut
    filters: FiltersOut
    population: PopulationOut
    hours: list[HourRowOut]
    heatmap: HeatmapOut


class LeadTimeAnalyticsOut(APIModel):
    period: PeriodOut
    cutoff: CutoffOut
    filters: FiltersOut
    population: PopulationOut
    buckets: list[dict[str, Any]]
    revision_curve: list[RevisionBucketOut]
    notes: list[str]


class RevisionTopOut(APIModel):
    delivery_interval: dt.datetime
    delivery_date: str
    settlement_period: int
    interval_label: str
    decision_forecast_mw: float | None
    latest_forecast_mw: float | None
    actual_mw: float | None
    revision_mw: float | None
    abs_revision_mw: float | None
    n_vintages: int
    latest_publish_time: dt.datetime | None = None


class RevisionsOut(APIModel):
    period: PeriodOut
    filters: FiltersOut
    summary: dict[str, float | int | None]
    top: list[RevisionTopOut]
    revision_curve: list[RevisionBucketOut]
    retrospective_notice: str | None = None


class DataQualityOut(APIModel):
    mode: str
    generated_at: dt.datetime
    upstream: dict[str, Any]
    cache: dict[str, Any]
    data: DataStatusOut
    counts: dict[str, int]
    actual_stats: dict[str, Any]
    forecast_stats: dict[str, Any]
    coverage_by_day: list[dict[str, Any]]
    missing_intervals: list[dict[str, Any]]
    invalid_samples: list[dict[str, Any]]
    retrieval_events: list[dict[str, Any]]
    notes: list[str]


class HealthOut(APIModel):
    status: str
    service: str
    version: str
    time_utc: dt.datetime
    dataset_loaded: bool
    data: dict[str, Any]
    elexon: dict[str, Any]
    checks: dict[str, bool]


class MetadataOut(APIModel):
    product: dict[str, Any]
    analysis_period: dict[str, Any]
    cutoff: dict[str, Any]
    sources: list[dict[str, Any]]
    data: dict[str, Any]
    metrics: dict[str, Any]
    limitations: list[str]


class RefreshOut(APIModel):
    start_date: str
    end_date: str
    actual_records: int
    forecast_records: int
    actual_fetched: int
    forecast_fetched: int
    actual_error: str | None = None
    forecast_error: str | None = None
    errors: list[dict[str, Any]]
    complete: bool
    is_synthetic: bool = False


class ErrorDetail(APIModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(APIModel):
    error: ErrorDetail


class ExportResponse(APIModel):
    filename: str
    row_count: int
    content_type: Literal["text/csv"] = "text/csv"
