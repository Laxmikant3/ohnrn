import type {
  DailyAnalytics,
  DataQuality,
  ForecastPage,
  Health,
  HourlyAnalytics,
  LeadTimeAnalytics,
  Metadata,
  Overview,
  Revisions,
  Summary,
  VintageDetail,
} from "@/lib/types";

const RAW_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
export const API_BASE = (RAW_BASE && RAW_BASE.length > 0 ? RAW_BASE : "/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(message: string, code: string, status: number, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export function buildQuery(params: QueryParams = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function request<T>(path: string, params: QueryParams = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}${buildQuery(params)}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    let code = `HTTP_${response.status}`;
    let message = `Request failed with status ${response.status}.`;
    let details: Record<string, unknown> = {};
    try {
      const payload = await response.json();
      if (payload?.error) {
        code = payload.error.code ?? code;
        message = payload.error.message ?? message;
        details = payload.error.details ?? {};
      }
    } catch {
      // Non-JSON error body: keep the status-based message.
    }
    throw new ApiError(message, code, response.status, details);
  }
  return (await response.json()) as T;
}

export type SearchFilters = {
  start_date: string;
  end_date: string;
  cutoff: string;
  cutoff_days_before: number;
  vintage: "decision_cutoff" | "latest_available";
  lead_time_bucket?: string | null;
};

export function filterParams(filters: SearchFilters): QueryParams {
  return {
    start_date: filters.start_date,
    end_date: filters.end_date,
    cutoff: filters.cutoff,
    cutoff_days_before: filters.cutoff_days_before,
    vintage: filters.vintage,
    lead_time_bucket: filters.lead_time_bucket || undefined,
  };
}

export const api = {
  health: (signal?: AbortSignal) => request<Health>("/health", {}, signal),
  metadata: (signal?: AbortSignal) => request<Metadata>("/metadata", {}, signal),
  overview: (filters: SearchFilters, resolution: string, signal?: AbortSignal) =>
    request<Overview>("/overview", { ...filterParams(filters), resolution }, signal),
  forecasts: (
    filters: SearchFilters,
    options: {
      page: number;
      page_size: number;
      sort_by: string;
      sort_dir: "asc" | "desc";
      search?: string;
      status?: string;
    },
    signal?: AbortSignal,
  ) =>
    request<ForecastPage>(
      "/forecasts",
      {
        ...filterParams(filters),
        page: options.page,
        page_size: options.page_size,
        sort_by: options.sort_by,
        sort_dir: options.sort_dir,
        search: options.search || undefined,
        status: options.status && options.status !== "all" ? options.status : undefined,
      },
      signal,
    ),
  vintages: (deliveryInterval: string, cutoff: string, cutoffDaysBefore: number, signal?: AbortSignal) =>
    request<VintageDetail>(
      `/forecasts/${encodeURIComponent(deliveryInterval)}/vintages`,
      { cutoff, cutoff_days_before: cutoffDaysBefore },
      signal,
    ),
  summary: (filters: SearchFilters, signal?: AbortSignal) =>
    request<Summary>("/analytics/summary", filterParams(filters), signal),
  daily: (filters: SearchFilters, signal?: AbortSignal) =>
    request<DailyAnalytics>("/analytics/daily", filterParams(filters), signal),
  hourly: (filters: SearchFilters, signal?: AbortSignal) =>
    request<HourlyAnalytics>("/analytics/hourly", filterParams(filters), signal),
  leadTime: (filters: SearchFilters, signal?: AbortSignal) =>
    request<LeadTimeAnalytics>("/analytics/lead-time", filterParams(filters), signal),
  revisions: (filters: SearchFilters, limit: number, signal?: AbortSignal) =>
    request<Revisions>("/analytics/revisions", { ...filterParams(filters), limit }, signal),
  dataQuality: (signal?: AbortSignal) => request<DataQuality>("/data-quality", {}, signal),
};

export function exportUrl(
  filters: SearchFilters,
  options: { search?: string; status?: string } = {},
): string {
  return `${API_BASE}/export${buildQuery({
    ...filterParams(filters),
    search: options.search || undefined,
    status: options.status && options.status !== "all" ? options.status : undefined,
  })}`;
}
