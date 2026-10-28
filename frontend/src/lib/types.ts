export type Metric = {
  value: number | null;
  n: number;
  unit: string;
  excluded?: number | null;
  expected?: number | null;
};

export type DataStatus = {
  mode: string;
  source: string;
  cached: boolean;
  stale: boolean;
  is_synthetic: boolean;
  last_retrieval: string | null;
  cache_age_hours: number | null;
  stale_after_hours: number | null;
  actual_records: number;
  forecast_records: number;
  forecast_delivery_intervals: number;
  forecast_expanded_intervals: number;
  forecast_vintages: number;
  forecast_granularity_minutes: number;
  forecast_expanded_to_half_hourly: boolean;
};

export type Cutoff = {
  time: string;
  days_before: number;
  timezone: string;
  description: string;
  example_delivery_date?: string | null;
  example_cutoff_utc?: string | null;
  assumption: boolean;
};

export type Period = {
  start_date: string;
  end_date: string;
  label: string;
  timezone: string;
  expected_intervals: number;
  mode: string;
};

export type Filters = {
  start_date: string;
  end_date: string;
  cutoff: string;
  cutoff_days_before: number;
  vintage: "decision_cutoff" | "latest_available";
  vintage_label: string;
  lead_time_bucket: string | null;
};

export type Population = {
  expected_intervals: number;
  selected_intervals: number;
  matched_intervals: number;
  missing_forecast: number;
  missing_actual: number;
  excluded_by_lead_time: number;
  mape_excluded?: number | null;
  mape_min_actual_mw?: number | null;
};

export type SeriesPoint = {
  timestamp: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  error_mw: number | null;
  absolute_error_mw: number | null;
  n: number;
};

export type DailyRow = {
  date: string;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  mape: number | null;
  wape: number | null;
  n: number;
  expected: number;
  coverage_pct: number | null;
  overforecast_count: number;
  underforecast_count: number;
};

export type IntervalRow = {
  delivery_interval: string;
  delivery_date: string;
  settlement_period: number;
  interval_label: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  error_mw: number | null;
  absolute_error_mw: number | null;
  percentage_error: number | null;
  publish_time: string | null;
  lead_time_hours: number | null;
  eligibility?: string | null;
  status?: string | null;
};

export type RevisionBucket = {
  key: string;
  label: string;
  min_hours: number;
  max_hours: number | null;
  mean_forecast_mw: number | null;
  mean_decision_mw: number | null;
  mean_delta_vs_decision_mw: number | null;
  mean_abs_revision_mw: number | null;
  mean_lead_time_hours: number | null;
  n: number;
};

export type LatestForecastKpi = {
  value: number | null;
  unit: string;
  delivery_interval: string | null;
  delivery_date: string | null;
  settlement_period: number | null;
  interval_label: string | null;
  publish_time: string | null;
  lead_time_hours: number | null;
  status: string;
  eligibility?: string | null;
};

export type LatestActualKpi = {
  value: number | null;
  unit: string;
  delivery_interval: string | null;
  delivery_date: string | null;
  settlement_period: number | null;
  interval_label: string | null;
  status: string;
};

export type LatestErrorKpi = {
  value: number | null;
  unit: string;
  delivery_interval: string | null;
  delivery_date: string | null;
  settlement_period: number | null;
  percentage_error: number | null;
  direction: string | null;
  status: string;
};

export type Overview = {
  mode: string;
  period: Period;
  cutoff: Cutoff;
  filters: Filters;
  data_status: DataStatus;
  kpis: {
    latest_eligible_forecast: LatestForecastKpi;
    latest_actual: LatestActualKpi;
    latest_error: LatestErrorKpi;
    mae: Metric;
    rmse: Metric;
    coverage: Metric;
    bias: Metric;
  };
  population: Population;
  series: SeriesPoint[];
  series_resolution: string;
  daily: DailyRow[];
  revision_curve: RevisionBucket[];
  top_overforecast: IntervalRow[];
  top_underforecast: IntervalRow[];
  procurement_context: string;
};

export type ForecastRow = {
  delivery_interval: string;
  delivery_date: string;
  settlement_period: number;
  interval_label: string;
  forecast_mw: number | null;
  actual_mw: number | null;
  error_mw: number | null;
  absolute_error_mw: number | null;
  percentage_error: number | null;
  publish_time: string | null;
  lead_time_hours: number | null;
  lead_time_bucket: string | null;
  lead_time_bucket_label: string | null;
  cutoff_time: string | null;
  eligibility: string;
  status: string;
  is_cutoff_compliant: boolean;
};

export type ForecastPage = {
  period: Period;
  cutoff: Cutoff;
  filters: Filters;
  population: Population;
  items: ForecastRow[];
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  };
  sort: { by: string; direction: string };
};

export type Vintage = {
  publish_time: string;
  forecast_mw: number;
  lead_time_hours: number;
  eligible: boolean;
  selected: boolean;
  revision_from_previous_mw: number | null;
  revision_from_decision_mw: number | null;
};

export type VintageDetail = {
  delivery_interval: string;
  delivery_date: string;
  settlement_period: number;
  interval_label: string;
  market_timezone: string;
  cutoff: { time: string; days_before: number; timezone: string; cutoff_utc: string };
  actual_mw: number | null;
  decision_forecast: {
    forecast_mw: number | null;
    publish_time: string | null;
    eligible: boolean;
    error_mw: number | null;
  };
  latest_forecast: { forecast_mw: number | null; publish_time: string | null };
  revision: {
    latest_minus_decision_mw: number | null;
    latest_minus_actual_mw: number | null;
    n_vintages: number;
    n_eligible_vintages: number;
    latest_eligible_publish_time: string | null;
  };
  vintages: Vintage[];
  retrospective_notice: string;
};

export type DistributionBin = {
  bin_start: number;
  bin_end: number;
  label: string;
  count: number;
  direction: "over" | "under" | "straddle";
};

export type Summary = {
  period: Period;
  cutoff: Cutoff;
  filters: Filters;
  population: Population;
  metrics: {
    mae: Metric;
    rmse: Metric;
    bias: Metric;
    mape: Metric;
    wape: Metric;
    coverage: Metric;
  };
  error_stats: {
    mean: number | null;
    median: number | null;
    p95_absolute: number | null;
    min: number | null;
    max: number | null;
  };
  direction: {
    overforecast_count: number;
    underforecast_count: number;
    exact_count: number;
    overforecast_total_mw: number;
    underforecast_total_mw: number;
    overforecast_share_pct: number | null;
  };
  distribution: DistributionBin[];
  top_overforecast: IntervalRow[];
  top_underforecast: IntervalRow[];
  lead_time_buckets: LeadTimeBucket[];
  notes: string[];
};

export type LeadTimeBucket = {
  key: string;
  label: string;
  min_hours: number;
  max_hours: number | null;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  mape: number | null;
  wape: number | null;
  n: number;
};

export type DailyAnalytics = {
  period: Period;
  cutoff: Cutoff;
  filters: Filters;
  population: Population;
  days: DailyRow[];
};

export type HourRow = {
  hour: number;
  label: string;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  mape: number | null;
  n: number;
};

export type HourlyAnalytics = {
  period: Period;
  cutoff: Cutoff;
  filters: Filters;
  population: Population;
  hours: HourRow[];
  heatmap: {
    dates: string[];
    hours: number[];
    cells: { date: string; hour: number; mae: number | null; n: number }[];
    max_mae: number;
  };
};

export type LeadTimeAnalytics = {
  period: Period;
  cutoff: Cutoff;
  filters: Filters;
  population: Population;
  buckets: LeadTimeBucket[];
  revision_curve: RevisionBucket[];
  notes: string[];
};

export type RevisionTop = {
  delivery_interval: string;
  delivery_date: string;
  settlement_period: number;
  interval_label: string;
  decision_forecast_mw: number | null;
  latest_forecast_mw: number | null;
  actual_mw: number | null;
  revision_mw: number | null;
  abs_revision_mw: number | null;
  n_vintages: number;
  latest_publish_time: string | null;
};

export type Revisions = {
  period: Period;
  filters: Filters;
  summary: {
    intervals_with_vintages: number;
    mean_abs_revision_mw: number | null;
    max_abs_revision_mw: number | null;
    unchanged_share_pct: number | null;
  };
  top: RevisionTop[];
  revision_curve: RevisionBucket[];
  retrospective_notice?: string | null;
};

export type DataQuality = {
  mode: string;
  generated_at: string;
  upstream: {
    checked: boolean;
    reachable: boolean | null;
    status_code: number | null;
    latency_ms: number | null;
    checked_at: string | null;
    detail: string;
  };
  cache: {
    present: boolean;
    files: Record<
      string,
      {
        file: string;
        exists: boolean;
        bytes?: number;
        modified_at?: string;
        sha256?: string | null;
        records?: number | null;
      }
    >;
    last_success: Record<string, string>;
    stale: boolean;
    stale_after_hours: number;
  };
  data: DataStatus;
  counts: Record<string, number>;
  actual_stats: Record<string, unknown>;
  forecast_stats: Record<string, unknown>;
  coverage_by_day: {
    date: string;
    expected: number;
    matched: number;
    missing_actual: number;
    missing_forecast: number;
    coverage_pct: number | null;
  }[];
  missing_intervals: {
    delivery_interval: string;
    delivery_date: string;
    settlement_period: number;
    interval_label: string;
    missing: string;
  }[];
  invalid_samples: unknown[];
  retrieval_events: {
    timestamp: string;
    operation: string;
    endpoint: string;
    params: Record<string, unknown>;
    status: string;
    records: number;
    attempts: number;
    duration_seconds: number;
    error: string | null;
  }[];
  notes: string[];
};

export type Health = {
  status: string;
  service: string;
  version: string;
  time_utc: string;
  dataset_loaded: boolean;
  data: DataStatus;
  elexon: {
    checked: boolean;
    reachable: boolean | null;
    status_code: number | null;
    latency_ms: number | null;
    checked_at: string | null;
    detail: string;
  };
  checks: Record<string, boolean>;
};

export type Metadata = {
  product: {
    name: string;
    version: string;
    description: string;
    mode: string;
    timezone: string;
  };
  analysis_period: {
    start_date: string;
    end_date: string;
    label: string;
    focus: string;
    available_start: string | null;
    available_end: string | null;
  };
  cutoff: {
    time: string;
    days_before: number;
    timezone: string;
    assumption: boolean;
    description: string;
  };
  sources: {
    dataset: string;
    name: string;
    endpoint: string;
    documentation_url: string;
    parameters: string[];
    fields_used: Record<string, string>;
    granularity_minutes: number;
    unit: string;
    authentication: string;
    pagination: string;
    rate_limit: string;
  }[];
  data: DataStatus;
  metrics: {
    mape_min_actual_mw: number;
    definitions: {
      key: string;
      label: string;
      unit: string;
      formula: string;
      description: string;
    }[];
    lead_time_buckets: { key: string; label: string; min_hours: number; max_hours: number | null }[];
    coverage_definition: string;
  };
  limitations: string[];
};
