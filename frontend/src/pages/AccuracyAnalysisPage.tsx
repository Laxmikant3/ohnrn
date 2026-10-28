import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Download,
  Gauge,
  Percent,
  Scale,
  Target,
} from "lucide-react";
import { api, exportUrl } from "@/lib/api";
import { useFilters } from "@/features/filters/filters";
import { downloadUrl, formatDate, formatDecimal, formatMw, formatPct } from "@/lib/format";
import { ChartPanel, PageHeader, QueryState } from "@/components/common";
import { FilterBar } from "@/components/FilterBar";
import { KpiCard } from "@/components/KpiCard";
import { Badge, Button, Panel } from "@/components/ui/primitives";
import { DailyMaeChart } from "@/components/charts/DailyMaeChart";
import { DistributionChart } from "@/components/charts/DistributionChart";
import { HourlyHeatmap } from "@/components/charts/HourlyHeatmap";
import { HourlyProfileChart } from "@/components/charts/HourlyProfileChart";
import { LeadTimeChart } from "@/components/charts/LeadTimeChart";
import { cn } from "@/lib/utils";

function MetricTable({
  rows,
  firstColumn,
}: {
  rows: {
    key: string;
    label: string;
    mae: number | null;
    rmse: number | null;
    bias: number | null;
    mape: number | null;
    wape: number | null;
    n: number;
  }[];
  firstColumn: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="table-shell">
        <thead>
          <tr>
            <th>{firstColumn}</th>
            <th className="text-right">MAE</th>
            <th className="text-right">RMSE</th>
            <th className="text-right">Bias</th>
            <th className="text-right">MAPE</th>
            <th className="text-right">WAPE</th>
            <th className="text-right">n</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td className="text-slate-200">{row.label}</td>
              <td className="num text-right text-slate-200">{formatMw(row.mae)}</td>
              <td className="num text-right text-slate-400">{formatMw(row.rmse)}</td>
              <td
                className={cn(
                  "num text-right",
                  (row.bias ?? 0) > 0 ? "text-warning" : (row.bias ?? 0) < 0 ? "text-accent-teal" : "text-slate-400",
                )}
              >
                {formatMw(row.bias, { sign: true })}
              </td>
              <td className="num text-right text-slate-400">{formatPct(row.mape)}</td>
              <td className="num text-right text-slate-400">{formatPct(row.wape)}</td>
              <td className="num text-right text-slate-500">{row.n.toLocaleString("en-GB")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AccuracyAnalysisPage() {
  const { apiFilters } = useFilters();

  const summaryQuery = useQuery({
    queryKey: ["summary", apiFilters],
    queryFn: ({ signal }) => api.summary(apiFilters, signal),
    staleTime: 2 * 60_000,
  });
  const dailyQuery = useQuery({
    queryKey: ["daily", apiFilters],
    queryFn: ({ signal }) => api.daily(apiFilters, signal),
    staleTime: 2 * 60_000,
  });
  const hourlyQuery = useQuery({
    queryKey: ["hourly", apiFilters],
    queryFn: ({ signal }) => api.hourly(apiFilters, signal),
    staleTime: 2 * 60_000,
  });
  const leadQuery = useQuery({
    queryKey: ["lead-time", apiFilters],
    queryFn: ({ signal }) => api.leadTime(apiFilters, signal),
    staleTime: 2 * 60_000,
  });

  const summary = summaryQuery.data;
  const metrics = summary?.metrics;

  const highlights = useMemo(() => {
    const days = dailyQuery.data?.days ?? [];
    const hours = hourlyQuery.data?.hours ?? [];
    const buckets = leadQuery.data?.buckets ?? [];
    const out: string[] = [];

    const scoredDays = days.filter((day) => day.mae !== null);
    if (scoredDays.length > 0) {
      const worst = scoredDays.reduce((best, day) => ((day.mae ?? 0) > (best.mae ?? 0) ? day : best));
      const best = scoredDays.reduce((current, day) => ((day.mae ?? 0) < (current.mae ?? 0) ? day : current));
      out.push(
        `Highest daily MAE: ${formatDate(worst.date)} at ${formatMw(worst.mae)} MW across ${worst.n.toLocaleString("en-GB")} paired intervals. Lowest: ${formatDate(best.date)} at ${formatMw(best.mae)} MW.`,
      );
    }

    const scoredHours = hours.filter((hour) => hour.mae !== null && hour.n > 0);
    if (scoredHours.length > 0) {
      const worstHour = scoredHours.reduce((best, hour) => ((hour.mae ?? 0) > (best.mae ?? 0) ? hour : best));
      const bestHour = scoredHours.reduce((current, hour) => ((hour.mae ?? 0) < (current.mae ?? 0) ? hour : current));
      out.push(
        `Hour-of-day spread: ${worstHour.label} carries the highest MAE (${formatMw(worstHour.mae)} MW, n=${worstHour.n.toLocaleString("en-GB")}) and ${bestHour.label} the lowest (${formatMw(bestHour.mae)} MW).`,
      );
    }

    const usableBuckets = buckets.filter((bucket) => bucket.n > 0 && bucket.mae !== null);
    if (usableBuckets.length > 1) {
      const sorted = [...usableBuckets].sort((a, b) => a.min_hours - b.min_hours);
      out.push(
        `Lead-time buckets populated: ${usableBuckets.length} of ${buckets.length}. Error ranges from ${formatMw(sorted[0].mae)} MW at ${sorted[0].label} to ${formatMw(sorted[sorted.length - 1].mae)} MW at ${sorted[sorted.length - 1].label}.`,
      );
    }

    if (summary) {
      out.push(
        `Direction: ${summary.direction.overforecast_count.toLocaleString("en-GB")} overforecast intervals (${formatPct(summary.direction.overforecast_share_pct)} of paired observations) versus ${summary.direction.underforecast_count.toLocaleString("en-GB")} underforecast intervals.`,
      );
    }
    return out;
  }, [dailyQuery.data, hourlyQuery.data, leadQuery.data, summary]);

  const refreshAll = () => {
    void summaryQuery.refetch();
    void dailyQuery.refetch();
    void hourlyQuery.refetch();
    void leadQuery.refetch();
  };

  const refreshing =
    summaryQuery.isFetching || dailyQuery.isFetching || hourlyQuery.isFetching || leadQuery.isFetching;

  return (
    <div>
      <PageHeader
        eyebrow="Error diagnostics"
        title="Accuracy analysis"
        description="How far the decision-cutoff forecast departed from observed wind outturn, decomposed by day, hour of day, error distribution and publication lead time. All metrics use paired forecast and actual intervals only."
        meta={
          summary ? (
            <>
              <Badge tone="violet">Historical analysis</Badge>
              <Badge tone={summary.filters.vintage === "decision_cutoff" ? "positive" : "warning"}>
                {summary.filters.vintage_label}
              </Badge>
              <Badge tone="neutral">{summary.population.matched_intervals.toLocaleString("en-GB")} paired intervals</Badge>
              {summary.population.mape_excluded ? (
                <span className="text-[10.5px] text-slate-500">
                  MAPE excluded {summary.population.mape_excluded.toLocaleString("en-GB")} low-actual intervals
                </span>
              ) : null}
            </>
          ) : null
        }
        actions={
          <>
            <Button variant="secondary" onClick={() => downloadUrl(exportUrl(apiFilters))} disabled={!summary}>
              <Download size={13} /> Export CSV
            </Button>
            <Button variant="primary" onClick={refreshAll} disabled={refreshing}>
              <Activity size={13} className={refreshing ? "animate-pulse" : undefined} />
              {refreshing ? "Refreshing" : "Refresh analysis"}
            </Button>
          </>
        }
      />

      <FilterBar />

      {summaryQuery.isError ? (
        <Panel>
          <QueryState isLoading={false} error={summaryQuery.error} onRetry={() => summaryQuery.refetch()}>
            <span />
          </QueryState>
        </Panel>
      ) : (
        <>
          <section aria-label="Headline error metrics" className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
            <KpiCard
              label="MAE"
              value={formatMw(metrics?.mae.value)}
              unit="MW"
              icon={<Target size={14} />}
              hint={`${(metrics?.mae.n ?? 0).toLocaleString("en-GB")} paired intervals`}
              footer={<span>Mean absolute error</span>}
            />
            <KpiCard
              label="RMSE"
              value={formatMw(metrics?.rmse.value)}
              unit="MW"
              icon={<Gauge size={14} />}
              hint={`${(metrics?.rmse.n ?? 0).toLocaleString("en-GB")} paired intervals`}
              footer={<span>Penalises large misses</span>}
            />
            <KpiCard
              label="Bias"
              value={formatMw(metrics?.bias.value, { sign: true })}
              unit="MW"
              tone={(metrics?.bias.value ?? 0) > 0 ? "warning" : (metrics?.bias.value ?? 0) < 0 ? "positive" : "neutral"}
              icon={(metrics?.bias.value ?? 0) >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
              hint={summary ? `${summary.direction.overforecast_count.toLocaleString("en-GB")} over / ${summary.direction.underforecast_count.toLocaleString("en-GB")} under` : undefined}
              footer={<span>Mean forecast − actual</span>}
            />
            <KpiCard
              label="MAPE"
              value={formatPct(metrics?.mape.value)}
              icon={<Percent size={14} />}
              hint={
                metrics?.mape.excluded
                  ? `${metrics.mape.excluded.toLocaleString("en-GB")} intervals excluded`
                  : "No intervals excluded"
              }
              footer={<span>Denominator ≥ {formatDecimal(summary?.population.mape_min_actual_mw ?? 1, 1)} MW</span>}
            />
            <KpiCard
              label="WAPE"
              value={formatPct(metrics?.wape.value)}
              icon={<Scale size={14} />}
              hint={`${(metrics?.wape.n ?? 0).toLocaleString("en-GB")} paired intervals`}
              footer={<span>Volume-weighted absolute error</span>}
            />
            <KpiCard
              label="Coverage"
              value={formatPct(metrics?.coverage.value)}
              tone={(metrics?.coverage.value ?? 0) >= 98 ? "positive" : "warning"}
              icon={<Target size={14} />}
              hint={`${(metrics?.coverage.n ?? 0).toLocaleString("en-GB")} / ${(metrics?.coverage.expected ?? 0).toLocaleString("en-GB")} expected`}
              footer={<span>Matched forecast + actual</span>}
            />
          </section>

          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-3">
            <ChartPanel
              className="xl:col-span-2"
              title="Daily error trend"
              subtitle="Daily MAE bars against daily RMSE, by London delivery date"
              right={dailyQuery.isFetching ? <Badge tone="accent">Updating</Badge> : null}
            >
              <QueryState
                isLoading={dailyQuery.isLoading}
                error={dailyQuery.error}
                isEmpty={(dailyQuery.data?.days.length ?? 0) === 0}
                onRetry={() => dailyQuery.refetch()}
              >
                <DailyMaeChart data={dailyQuery.data?.days ?? []} height={252} />
              </QueryState>
            </ChartPanel>

            <Panel className="flex flex-col">
              <div className="border-b border-white/[0.06] px-4 py-3">
                <h2 className="panel-title">Direction and spread</h2>
                <p className="panel-subtitle">Whether the forecast ran high or low, and how widely</p>
              </div>
              <div className="flex-1 space-y-3 p-4">
                {summary ? (
                  <>
                    <div>
                      <div className="mb-1 flex items-center justify-between text-[10.5px]">
                        <span className="text-warning">Overforecast {summary.direction.overforecast_count.toLocaleString("en-GB")}</span>
                        <span className="text-accent-teal">Underforecast {summary.direction.underforecast_count.toLocaleString("en-GB")}</span>
                      </div>
                      <div className="flex h-2 overflow-hidden rounded-full bg-white/[0.05]">
                        <div
                          className="h-full bg-warning/70"
                          style={{ width: `${summary.direction.overforecast_share_pct ?? 0}%` }}
                        />
                        <div
                          className="h-full bg-accent-teal/70"
                          style={{ width: `${100 - (summary.direction.overforecast_share_pct ?? 0)}%` }}
                        />
                      </div>
                      <p className="mt-1 text-[10px] text-slate-500">
                        {formatPct(summary.direction.overforecast_share_pct)} of paired intervals were above the actual outturn.
                      </p>
                    </div>

                    <dl className="space-y-1.5 border-t border-white/[0.05] pt-2.5 text-[11px]">
                      <div className="flex justify-between gap-2">
                        <dt className="text-slate-500">Mean error</dt>
                        <dd className="num text-slate-200">{formatMw(summary.error_stats.mean, { sign: true })} MW</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-slate-500">Median error</dt>
                        <dd className="num text-slate-200">{formatMw(summary.error_stats.median, { sign: true })} MW</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-slate-500">95th percentile |error|</dt>
                        <dd className="num text-slate-200">{formatMw(summary.error_stats.p95_absolute)} MW</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-slate-500">Worst underforecast</dt>
                        <dd className="num text-accent-teal">{formatMw(summary.error_stats.min, { sign: true })} MW</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-slate-500">Worst overforecast</dt>
                        <dd className="num text-warning">{formatMw(summary.error_stats.max, { sign: true })} MW</dd>
                      </div>
                    </dl>

                    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5">
                      <p className="label-caps mb-1">Population accounting</p>
                      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10.5px]">
                        <span className="text-slate-500">Expected</span>
                        <span className="num text-right text-slate-300">{summary.population.expected_intervals.toLocaleString("en-GB")}</span>
                        <span className="text-slate-500">Selected</span>
                        <span className="num text-right text-slate-300">{summary.population.selected_intervals.toLocaleString("en-GB")}</span>
                        <span className="text-slate-500">Matched</span>
                        <span className="num text-right text-slate-300">{summary.population.matched_intervals.toLocaleString("en-GB")}</span>
                        <span className="text-slate-500">Missing forecast</span>
                        <span className="num text-right text-slate-300">{summary.population.missing_forecast.toLocaleString("en-GB")}</span>
                        <span className="text-slate-500">Missing actual</span>
                        <span className="num text-right text-slate-300">{summary.population.missing_actual.toLocaleString("en-GB")}</span>
                        <span className="text-slate-500">Excluded by lead time</span>
                        <span className="num text-right text-slate-300">{summary.population.excluded_by_lead_time.toLocaleString("en-GB")}</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="space-y-2">
                    {Array.from({ length: 8 }).map((_, index) => (
                      <div key={index} className="h-3 animate-pulse rounded bg-white/[0.04]" />
                    ))}
                  </div>
                )}
              </div>
            </Panel>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-3">
            <ChartPanel
              className="xl:col-span-2"
              title="Error distribution"
              subtitle="Count of paired intervals by forecast-error bin (MW)"
            >
              <QueryState
                isLoading={summaryQuery.isLoading}
                error={summaryQuery.error}
                isEmpty={(summary?.distribution.length ?? 0) === 0}
                onRetry={() => summaryQuery.refetch()}
              >
                <DistributionChart data={summary?.distribution ?? []} height={248} />
              </QueryState>
            </ChartPanel>

            <ChartPanel title="Hour-of-day profile" subtitle="Mean absolute error by local delivery hour">
              <QueryState
                isLoading={hourlyQuery.isLoading}
                error={hourlyQuery.error}
                isEmpty={(hourlyQuery.data?.hours.length ?? 0) === 0}
                onRetry={() => hourlyQuery.refetch()}
              >
                <HourlyProfileChart data={hourlyQuery.data?.hours ?? []} height={248} />
              </QueryState>
            </ChartPanel>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-3">
            <ChartPanel
              className="xl:col-span-2"
              title="Daily and hourly density"
              subtitle="Date × local hour heatmap of mean absolute error — darker cyan is lower, amber is higher"
            >
              <QueryState
                isLoading={hourlyQuery.isLoading}
                error={hourlyQuery.error}
                isEmpty={(hourlyQuery.data?.heatmap.dates.length ?? 0) === 0}
                onRetry={() => hourlyQuery.refetch()}
              >
                {hourlyQuery.data ? <HourlyHeatmap data={hourlyQuery.data.heatmap} /> : null}
              </QueryState>
            </ChartPanel>

            <ChartPanel title="Accuracy by lead time" subtitle="MAE of the selected vintage by publication lead-time bucket">
              <QueryState
                isLoading={leadQuery.isLoading}
                error={leadQuery.error}
                isEmpty={(leadQuery.data?.buckets.length ?? 0) === 0}
                onRetry={() => leadQuery.refetch()}
              >
                <LeadTimeChart data={leadQuery.data?.buckets ?? []} height={252} />
              </QueryState>
            </ChartPanel>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2">
            <Panel className="overflow-hidden">
              <div className="border-b border-white/[0.06] px-4 py-3">
                <h2 className="panel-title">Daily diagnostics</h2>
                <p className="panel-subtitle">Every London delivery date in the selected window</p>
              </div>
              <div className="max-h-[330px] overflow-auto">
                <table className="table-shell">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th className="text-right">MAE</th>
                      <th className="text-right">Bias</th>
                      <th className="text-right">MAPE</th>
                      <th className="text-right">WAPE</th>
                      <th className="text-right">Paired / expected</th>
                      <th className="text-right">Coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(dailyQuery.data?.days ?? []).map((day) => (
                      <tr key={day.date}>
                        <td className="text-slate-200">{formatDate(day.date)}</td>
                        <td className="num text-right text-slate-200">{formatMw(day.mae)}</td>
                        <td
                          className={cn(
                            "num text-right",
                            (day.bias ?? 0) > 0 ? "text-warning" : (day.bias ?? 0) < 0 ? "text-accent-teal" : "text-slate-400",
                          )}
                        >
                          {formatMw(day.bias, { sign: true })}
                        </td>
                        <td className="num text-right text-slate-400">{formatPct(day.mape)}</td>
                        <td className="num text-right text-slate-400">{formatPct(day.wape)}</td>
                        <td className="num text-right text-slate-400">
                          {day.n.toLocaleString("en-GB")} / {day.expected.toLocaleString("en-GB")}
                        </td>
                        <td className="num text-right text-slate-400">{formatPct(day.coverage_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>

            <div className="space-y-3">
              <Panel className="overflow-hidden">
                <div className="border-b border-white/[0.06] px-4 py-3">
                  <h2 className="panel-title">Lead-time metrics</h2>
                  <p className="panel-subtitle">Only populated buckets are meaningful; empty rows mean no eligible vintage fell in that range</p>
                </div>
                <div className="max-h-[240px] overflow-auto">
                  <MetricTable
                    firstColumn="Lead-time bucket"
                    rows={(leadQuery.data?.buckets ?? []).map((bucket) => ({
                      key: bucket.key,
                      label: bucket.label,
                      mae: bucket.mae,
                      rmse: bucket.rmse,
                      bias: bucket.bias,
                      mape: bucket.mape,
                      wape: bucket.wape,
                      n: bucket.n,
                    }))}
                  />
                </div>
              </Panel>

              <Panel>
                <div className="border-b border-white/[0.06] px-4 py-3">
                  <h2 className="panel-title">What the data shows</h2>
                  <p className="panel-subtitle">Descriptive observations derived from the current filter selection</p>
                </div>
                <ul className="space-y-2 p-4">
                  {highlights.length > 0 ? (
                    highlights.map((text) => (
                      <li key={text} className="flex gap-2 text-[11.5px] leading-5 text-slate-400">
                        <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-accent/70" aria-hidden />
                        <span>{text}</span>
                      </li>
                    ))
                  ) : (
                    <li className="text-[11.5px] text-slate-500">No paired observations in this selection.</li>
                  )}
                </ul>
                <div className="border-t border-white/[0.05] px-4 py-2.5">
                  <p className="text-[10px] leading-4 text-slate-600">
                    {summary?.notes.join(" ") ??
                      "MAE and RMSE are error magnitudes in MW, not accuracy percentages."}
                  </p>
                </div>
              </Panel>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
