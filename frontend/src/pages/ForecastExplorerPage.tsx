import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  ChevronFirst,
  ChevronLast,
  ChevronLeft,
  ChevronRight,
  Download,
  Inbox,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { api, exportUrl } from "@/lib/api";
import { useFilters } from "@/features/filters/filters";
import type { ForecastRow } from "@/lib/types";
import {
  downloadUrl,
  formatDateTime,
  formatHours,
  formatMw,
  formatPct,
} from "@/lib/format";
import { useDebounced } from "@/lib/useDebounced";
import { PageHeader, QueryState } from "@/components/common";
import { FilterBar } from "@/components/FilterBar";
import { IntervalDrawer } from "@/components/IntervalDrawer";
import { Badge, Button, Input, Panel, Select } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

const COLUMNS: { key: string; label: string; align?: "right"; sortable?: boolean }[] = [
  { key: "delivery_date", label: "Delivery date", sortable: true },
  { key: "settlement_period", label: "SP / interval", sortable: true },
  { key: "forecast_mw", label: "Forecast MW", align: "right", sortable: true },
  { key: "actual_mw", label: "Actual MW", align: "right", sortable: true },
  { key: "error_mw", label: "Error MW", align: "right", sortable: true },
  { key: "absolute_error_mw", label: "Abs error", align: "right", sortable: true },
  { key: "publish_time", label: "Published (London)", sortable: true },
  { key: "lead_time_hours", label: "Lead time", align: "right", sortable: true },
  { key: "status", label: "Status", sortable: true },
];

const PAGE_SIZES = [25, 50, 100, 200];

function StatusBadge({ row }: { row: ForecastRow }) {
  if (row.status === "matched") {
    return row.is_cutoff_compliant ? (
      <Badge tone="positive">Matched</Badge>
    ) : (
      <Badge tone="warning">Retrospective</Badge>
    );
  }
  if (row.status === "missing_actual") return <Badge tone="warning">Missing actual</Badge>;
  if (row.status === "missing_forecast") return <Badge tone="negative">No eligible forecast</Badge>;
  return <Badge tone="neutral">{row.status}</Badge>;
}

function TableSkeleton({ rows = 12, cols = 9 }: { rows?: number; cols?: number }) {
  return (
    <div className="p-3">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex items-center gap-4 border-b border-white/[0.03] py-2.5">
          {Array.from({ length: cols }).map((__, colIndex) => (
            <div
              key={colIndex}
              className="h-3 animate-pulse rounded bg-white/[0.045]"
              style={{ width: colIndex === 0 ? 90 : colIndex < 6 ? 64 : 80 }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function ForecastExplorerPage() {
  const { filters, apiFilters } = useFilters();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [sortBy, setSortBy] = useState("delivery_interval");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<ForecastRow | null>(null);
  const debouncedSearch = useDebounced(search, 300);

  useEffect(() => {
    setPage(1);
  }, [apiFilters, debouncedSearch, status, pageSize]);

  const query = useQuery({
    queryKey: ["forecasts", apiFilters, page, pageSize, sortBy, sortDir, debouncedSearch, status],
    queryFn: ({ signal }) =>
      api.forecasts(apiFilters,
        { page, page_size: pageSize, sort_by: sortBy, sort_dir: sortDir, search: debouncedSearch, status },
        signal,
      ),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });

  const data = query.data;

  const handleSort = (key: string) => {
    if (sortBy === key) {
      setSortDir((direction) => (direction === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      setSortDir(key === "delivery_date" || key === "settlement_period" ? "asc" : "desc");
    }
    setPage(1);
  };

  const rangeStart = data && data.pagination.total_items > 0 ? (page - 1) * pageSize + 1 : 0;
  const rangeEnd = data ? Math.min(page * pageSize, data.pagination.total_items) : 0;

  return (
    <div>
      <PageHeader
        eyebrow="Interval-level audit"
        title="Forecast explorer"
        description="Every 30-minute settlement period in the selected window, joined to the latest eligible forecast published at or before the decision cutoff. Open a row to inspect all forecast vintages and the observed actual."
        meta={
          data ? (
            <>
              <Badge tone="neutral">{data.pagination.total_items.toLocaleString("en-GB")} rows</Badge>
              <Badge tone="positive">{data.population.matched_intervals.toLocaleString("en-GB")} matched</Badge>
              {data.population.missing_forecast > 0 ? (
                <Badge tone="negative">{data.population.missing_forecast} no eligible forecast</Badge>
              ) : null}
              {data.population.missing_actual > 0 ? (
                <Badge tone="warning">{data.population.missing_actual} missing actual</Badge>
              ) : null}
              <span className="text-[10.5px] text-slate-500">
                Cutoff compliant: {formatPct(
                  (data.population.matched_intervals / Math.max(1, data.population.selected_intervals)) * 100,
                )}
              </span>
            </>
          ) : null
        }
        actions={
          <Button
            variant="secondary"
            onClick={() => downloadUrl(exportUrl(apiFilters, { search: debouncedSearch, status }))}
            disabled={!data}
          >
            <Download size={13} /> Export filtered CSV
          </Button>
        }
      />

      <FilterBar />

      <Panel className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-white/[0.06] px-3 py-2.5">
          <div className="relative">
            <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search date, SP, interval or status…"
              aria-label="Search forecast rows"
              className="w-[260px] pl-8"
            />
          </div>
          <div className="flex items-center gap-1.5">
            <SlidersHorizontal size={12} className="text-slate-500" />
            <Select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter by status" className="w-[150px]">
              <option value="all">All statuses</option>
              <option value="matched">Matched</option>
              <option value="missing_actual">Missing actual</option>
              <option value="missing_forecast">No eligible forecast</option>
            </Select>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-[10px] text-slate-600 sm:inline">Rows</span>
            <Select
              value={String(pageSize)}
              onChange={(event) => setPageSize(Number(event.target.value))}
              aria-label="Rows per page"
              className="w-[72px]"
            >
              {PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </Select>
            {query.isFetching && !query.isLoading ? (
              <span className="text-[10px] text-accent/80">Updating…</span>
            ) : null}
          </div>
        </div>

        {query.isError ? (
          <QueryState isLoading={false} error={query.error} onRetry={() => query.refetch()}>
            <span />
          </QueryState>
        ) : query.isLoading ? (
          <TableSkeleton rows={12} />
        ) : data && data.items.length === 0 ? (
          <div className="py-6">
            <div className="flex flex-col items-center gap-2 text-center">
              <Inbox size={18} className="text-slate-600" />
              <p className="text-[13px] font-medium text-slate-300">No intervals match this selection</p>
              <p className="max-w-md text-[11.5px] text-slate-500">
                {debouncedSearch
                  ? `No rows matched “${debouncedSearch}”. Try a date like 2026-01-14, a settlement period, or a status.`
                  : "Adjust the date range or status filter. Missing forecasts are never backfilled with later publications."}
              </p>
              {debouncedSearch || status !== "all" ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearch("");
                    setStatus("all");
                  }}
                >
                  Clear search and filters
                </Button>
              ) : null}
            </div>
          </div>
        ) : data ? (
          <>
            <div className="max-h-[calc(100vh-330px)] overflow-auto">
              <table className="table-shell">
                <thead>
                  <tr>
                    {COLUMNS.map((column) => (
                      <th key={column.key} className={cn(column.align === "right" && "text-right")}>
                        {column.sortable ? (
                          <button
                            type="button"
                            onClick={() => handleSort(column.key)}
                            className={cn(
                              "inline-flex items-center gap-1 uppercase tracking-[0.1em] transition-colors hover:text-slate-300 focus-ring",
                              sortBy === column.key && "text-accent/90",
                            )}
                            aria-label={`Sort by ${column.label}`}
                          >
                            {column.label}
                            {sortBy === column.key ? (
                              sortDir === "asc" ? (
                                <ArrowUp size={10} />
                              ) : (
                                <ArrowDown size={10} />
                              )
                            ) : null}
                          </button>
                        ) : (
                          column.label
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((row) => (
                    <tr
                      key={row.delivery_interval}
                      data-interactive="true"
                      tabIndex={0}
                      onClick={() => setSelected(row)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelected(row);
                        }
                      }}
                      aria-label={`Open vintages for ${row.delivery_date} settlement period ${row.settlement_period}`}
                    >
                      <td className="text-slate-200">{row.delivery_date}</td>
                      <td>
                        <span className="num text-slate-300">SP {row.settlement_period}</span>
                        <span className="ml-1.5 text-slate-600">{row.interval_label}</span>
                      </td>
                      <td className="num text-right font-medium text-accent-soft">{formatMw(row.forecast_mw)}</td>
                      <td className="num text-right text-slate-300">{formatMw(row.actual_mw)}</td>
                      <td
                        className={cn(
                          "num text-right font-medium",
                          (row.error_mw ?? 0) > 0 ? "text-warning" : (row.error_mw ?? 0) < 0 ? "text-accent-teal" : "text-slate-400",
                        )}
                      >
                        {formatMw(row.error_mw, { sign: true })}
                      </td>
                      <td className="num text-right text-slate-400">{formatMw(row.absolute_error_mw)}</td>
                      <td className="num text-[11px] text-slate-400">{formatDateTime(row.publish_time)}</td>
                      <td className="num text-right text-slate-400">{formatHours(row.lead_time_hours)}</td>
                      <td>
                        <StatusBadge row={row} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.06] px-3 py-2.5">
              <p className="text-[10.5px] text-slate-500">
                Showing <span className="num text-slate-300">{rangeStart.toLocaleString("en-GB")}</span>–
                <span className="num text-slate-300">{rangeEnd.toLocaleString("en-GB")}</span> of{" "}
                <span className="num text-slate-300">{data.pagination.total_items.toLocaleString("en-GB")}</span> intervals
                <span className="ml-2 text-slate-600">· click a row for vintages</span>
              </p>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="icon" onClick={() => setPage(1)} disabled={page <= 1} aria-label="First page">
                  <ChevronFirst size={14} />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1} aria-label="Previous page">
                  <ChevronLeft size={14} />
                </Button>
                <span className="num px-1 text-[10.5px] text-slate-400">
                  {page} / {Math.max(1, data.pagination.total_pages)}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setPage((value) => value + 1)}
                  disabled={!data.pagination.has_next}
                  aria-label="Next page"
                >
                  <ChevronRight size={14} />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setPage(Math.max(1, data.pagination.total_pages))}
                  disabled={!data.pagination.has_next}
                  aria-label="Last page"
                >
                  <ChevronLast size={14} />
                </Button>
              </div>
            </div>
          </>
        ) : null}
      </Panel>

      <p className="mt-2 px-1 text-[10px] leading-4 text-slate-600">
        Eligibility is enforced server-side against the configured cutoff ({data?.cutoff.time ?? filters.cutoff}{" "}
        {data?.cutoff.timezone ?? "Europe/London"} on D−{data?.cutoff.days_before ?? filters.cutoffDaysBefore}). Rows with
        no eligible forecast are retained and labelled; they are never backfilled from later publications.
      </p>

      <IntervalDrawer
        row={selected}
        cutoff={filters.cutoff}
        cutoffDaysBefore={filters.cutoffDaysBefore}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
