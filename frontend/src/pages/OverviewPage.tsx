import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Download,
  Gauge,
  LineChart as LineChartIcon,
  RadioTower,
  Target,
  TrendingUp,
} from "lucide-react";
import { api, exportUrl } from "@/lib/api";
import { useFilters } from "@/features/filters/filters";
import { downloadUrl, formatDateTime, formatMw, formatPct, formatHours } from "@/lib/format";
import { PageHeader, ChartPanel, ChartSkeleton, QueryState } from "@/components/common";
import { FilterBar } from "@/components/FilterBar";
import { KpiCard } from "@/components/KpiCard";
import { Badge, Button, Panel } from "@/components/ui/primitives";
import { ForecastActualChart } from "@/components/charts/ForecastActualChart";
import { ForecastErrorChart } from "@/components/charts/ForecastErrorChart";
import { DailyMaeChart } from "@/components/charts/DailyMaeChart";
import { RevisionCurveChart } from "@/components/charts/RevisionCurveChart";
import { cn } from "@/lib/utils";
import type { IntervalRow } from "@/lib/types";

function ExtremesTable({ rows, direction }: { rows: IntervalRow[]; direction: "over" | "under" }) {
  if (rows.length === 0) {
    return <p className="px-4 py-6 text-center text-[11.5px] text-slate-500">No intervals available.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="table-shell">
        <thead>
          <tr>
            <th>Delivery</th>
            <th className="text-right">Forecast</th>
            <th className="text-right">Actual</th>
            <th className="text-right">{direction === "over" ? "Over" : "Under"} MW</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.delivery_interval}>
              <td>
                <span className="text-slate-300">{row.delivery_date}</span>
                <span className="ml-1.5 text-slate-600">SP {row.settlement_period}</span>
              </td>
              <td className="num text-right text-slate-400">{formatMw(row.forecast_mw)}</td>
              <td className="num text-right text-slate-400">{formatMw(row.actual_mw)}</td>
              <td className={cn("num text-right font-semibold", direction === "over" ? "text-warning" : "text-accent-teal")}>
                {formatMw(row.error_mw, { sign: true })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OverviewPage() {
  const { apiFilters } = useFilters();
  const query = useQuery({
    queryKey: ["overview", apiFilters],
    queryFn: ({ signal }) => api.overview(apiFilters, "1h", signal),
    staleTime: 2 * 60_000,
  });

  const data = query.data;
  const kpis = data?.kpis;

  const latestHint = useMemo(() => {
    const latest = data?.kpis.latest_eligible_forecast;
    if (!latest?.delivery_interval) return "No eligible forecast in selection";
    return `${latest.delivery_date} · SP ${latest.settlement_period} · published ${formatDateTime(latest.publish_time)}`;
  }, [data]);

  return (
    <div>
      <PageHeader
        eyebrow="Day-ahead procurement intelligence"
        title="Wind forecast overview"
        description="Historical decision analysis of Elexon WINDFOR forecasts against FUELHH wind outturn. Every forecast shown was published at or before the configured procurement cutoff."
        meta={
          <>
            <Badge tone="violet">Historical analysis · January 2026</Badge>
            <Badge tone="accent" dot>
              Cutoff {data?.cutoff.time ?? "11:00"} Europe/London · D−{data?.cutoff.days_before ?? 1}
            </Badge>
            {data ? (
              <span className="text-[10.5px] text-slate-500">
                {data.population.expected_intervals.toLocaleString("en-GB")} expected settlement periods · {data.population.matched_intervals.toLocaleString("en-GB")} paired
              </span>
            ) : null}
          </>
        }
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => downloadUrl(exportUrl(apiFilters))}
              disabled={!data}
              title="Download the filtered interval dataset as CSV"
            >
              <Download size={13} /> Export CSV
            </Button>
            <Button variant="primary" onClick={() => query.refetch()} disabled={query.isFetching}>
              <Activity size={13} className={query.isFetching ? "animate-pulse" : undefined} />
              {query.isFetching ? "Refreshing" : "Refresh view"}
            </Button>
          </>
        }
      />

      <FilterBar />

      {query.isLoading ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-[108px] animate-pulse rounded-xl border border-white/[0.06] bg-ink-850/70" />
          ))}
        </div>
      ) : query.isError ? (
        <Panel>
          <QueryState isLoading={false} error={query.error} onRetry={() => query.refetch()}>
            <span />
          </QueryState>
        </Panel>
      ) : data && kpis ? (
        <>
          <section aria-label="Headline indicators" className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
            <KpiCard
              label="Latest eligible forecast"
              value={formatMw(kpis.latest_eligible_forecast.value)}
              unit="MW"
              tone="accent"
              icon={<RadioTower size={14} />}
              hint={latestHint}
              footer={
                <span className="flex items-center justify-between gap-2">
                  <span>Lead {formatHours(kpis.latest_eligible_forecast.lead_time_hours)}</span>
                  <span className="text-accent/80">Decision vintage</span>
                </span>
              }
            />
            <KpiCard
              label="Actual wind generation"
              value={formatMw(kpis.latest_actual.value)}
              unit="MW"
              icon={<TrendingUp size={14} />}
              hint={
                kpis.latest_actual.delivery_interval
                  ? `${kpis.latest_actual.delivery_date} · SP ${kpis.latest_actual.settlement_period} · FUELHH`
                  : "No actuals in selection"
              }
              footer={<span>National wind outturn · 30-minute mean</span>}
            />
            <KpiCard
              label="Current forecast error"
              value={formatMw(kpis.latest_error.value, { sign: true })}
              unit="MW"
              tone={
                (kpis.latest_error.value ?? 0) > 0 ? "warning" : (kpis.latest_error.value ?? 0) < 0 ? "positive" : "neutral"
              }
              icon={
                (kpis.latest_error.value ?? 0) > 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />
              }
              hint={`${kpis.latest_error.direction ?? "—"} · forecast − actual`}
              footer={
                <span>
                  {kpis.latest_error.percentage_error !== null
                    ? `${formatPct(kpis.latest_error.percentage_error)} of actual`
                    : "Percentage unavailable"}
                </span>
              }
            />
            <KpiCard
              label="January MAE"
              value={formatMw(kpis.mae.value)}
              unit="MW"
              icon={<Target size={14} />}
              hint={`${kpis.mae.n.toLocaleString("en-GB")} paired intervals`}
              footer={<span>Mean absolute error · lower is better</span>}
            />
            <KpiCard
              label="January RMSE"
              value={formatMw(kpis.rmse.value)}
              unit="MW"
              icon={<Gauge size={14} />}
              hint={`${kpis.rmse.n.toLocaleString("en-GB")} paired intervals`}
              footer={<span>Penalises large errors · not a % accuracy</span>}
            />
            <KpiCard
              label="Forecast coverage"
              value={formatPct(kpis.coverage.value)}
              tone={(kpis.coverage.value ?? 0) >= 98 ? "positive" : "warning"}
              icon={<CheckCircle2 size={14} />}
              hint={`${kpis.coverage.n.toLocaleString("en-GB")} / ${kpis.coverage.expected?.toLocaleString("en-GB") ?? "—"} expected`}
              footer={<span>Matched forecast + actual intervals</span>}
            />
          </section>

          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-3">
            <ChartPanel
              className="xl:col-span-2"
              title="Forecast versus actual wind generation"
              subtitle="Decision-cutoff forecast and observed outturn, hourly mean, Europe/London"
              right={<Badge tone="violet">Historical</Badge>}
            >
              <QueryState
                isLoading={false}
                error={null}
                isEmpty={data.series.length === 0}
                emptyDescription="No paired intervals exist for this filter selection."
              >
                <ForecastActualChart data={data.series} resolution={data.series_resolution} height={306} />
              </QueryState>
            </ChartPanel>

            <ChartPanel
              title="Forecast revision curve"
              subtitle="How forecasts moved toward delivery, by publication lead time"
            >
              <QueryState
                isLoading={false}
                error={null}
                isEmpty={data.revision_curve.every((row) => row.n === 0)}
                emptyDescription="Revision analysis needs multiple pre-delivery vintages."
              >
                <RevisionCurveChart data={data.revision_curve} height={296} />
              </QueryState>
            </ChartPanel>

            <ChartPanel
              className="xl:col-span-2"
              title="Forecast error over time"
              subtitle="Positive values indicate overforecast; negative values indicate underforecast"
            >
              <ForecastErrorChart data={data.series} resolution={data.series_resolution} height={220} />
            </ChartPanel>

            <ChartPanel title="Daily MAE trend" subtitle="Mean absolute error by London delivery date">
              <DailyMaeChart data={data.daily} height={226} />
            </ChartPanel>

            <Panel className="xl:col-span-2">
              <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
                <div>
                  <h2 className="panel-title">Largest forecast extremes</h2>
                  <p className="panel-subtitle">Largest overforecast and underforecast intervals in the selection</p>
                </div>
                <LineChartIcon size={14} className="text-slate-600" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2">
                <div>
                  <div className="flex items-center justify-between px-4 py-2">
                    <span className="label-caps text-warning/80">Largest overforecast</span>
                    <span className="text-[10px] text-slate-600">Forecast above actual</span>
                  </div>
                  <ExtremesTable rows={data.top_overforecast} direction="over" />
                </div>
                <div className="border-t border-white/[0.05] md:border-l md:border-t-0">
                  <div className="flex items-center justify-between px-4 py-2">
                    <span className="label-caps text-accent-teal/80">Largest underforecast</span>
                    <span className="text-[10px] text-slate-600">Forecast below actual</span>
                  </div>
                  <ExtremesTable rows={data.top_underforecast} direction="under" />
                </div>
              </div>
            </Panel>

            <Panel>
              <div className="border-b border-white/[0.06] px-4 py-3">
                <h2 className="panel-title">Procurement context & data state</h2>
                <p className="panel-subtitle">What this analysis can and cannot tell you</p>
              </div>
              <div className="space-y-3 p-4">
                <p className="text-[11.5px] leading-5 text-slate-400">{data.procurement_context}</p>
                <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5">
                  <dl className="space-y-1.5 text-[10.5px]">
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Source</dt>
                      <dd className="text-slate-300">{data.data_status.source}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Last retrieval</dt>
                      <dd className="num text-slate-300">{formatDateTime(data.data_status.last_retrieval)}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Forecast vintages</dt>
                      <dd className="num text-slate-300">{data.data_status.forecast_vintages}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Vintage mode</dt>
                      <dd className={data.filters.vintage === "decision_cutoff" ? "text-positive" : "text-warning"}>
                        {data.filters.vintage === "decision_cutoff" ? "Decision cutoff" : "Latest available"}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt className="text-slate-500">Lead-time filter</dt>
                      <dd className="text-slate-300">{data.filters.lead_time_bucket ?? "All buckets"}</dd>
                    </div>
                  </dl>
                </div>
                <p className="text-[10px] leading-4 text-slate-600">
                  Cutoff assumption: {data.cutoff.description}
                </p>
              </div>
            </Panel>
          </div>
        </>
      ) : (
        <ChartSkeleton />
      )}
    </div>
  );
}
