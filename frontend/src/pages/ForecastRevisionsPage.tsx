import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, GitCompareArrows, Info, MoveRight, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useFilters } from "@/features/filters/filters";
import type { RevisionTop } from "@/lib/types";
import { formatDateTime, formatHours, formatMw, formatPct } from "@/lib/format";
import { ChartPanel, PageHeader, QueryState } from "@/components/common";
import { FilterBar } from "@/components/FilterBar";
import { KpiCard } from "@/components/KpiCard";
import { Badge, Button, Panel } from "@/components/ui/primitives";
import { RevisionCurveChart } from "@/components/charts/RevisionCurveChart";
import { IntervalDrawer, type IntervalRef } from "@/components/IntervalDrawer";
import { cn } from "@/lib/utils";

const DIRECTION_TONE = (value: number | null) =>
  (value ?? 0) > 0 ? "text-warning" : (value ?? 0) < 0 ? "text-accent-teal" : "text-slate-400";

export function ForecastRevisionsPage() {
  const { filters, apiFilters } = useFilters();
  const [selected, setSelected] = useState<IntervalRef | null>(null);

  const revisionsQuery = useQuery({
    queryKey: ["revisions", apiFilters, 20],
    queryFn: ({ signal }) => api.revisions(apiFilters, 20, signal),
    staleTime: 2 * 60_000,
  });
  const leadQuery = useQuery({
    queryKey: ["lead-time", apiFilters],
    queryFn: ({ signal }) => api.leadTime(apiFilters, signal),
    staleTime: 2 * 60_000,
  });

  const data = revisionsQuery.data;
  const summary = data?.summary;
  const curve = data?.revision_curve ?? leadQuery.data?.revision_curve ?? [];
  const populated = curve.filter((row) => row.n > 0);

  const openRow = (row: RevisionTop) => {
    setSelected({
      delivery_interval: row.delivery_interval,
      delivery_date: row.delivery_date,
      settlement_period: row.settlement_period,
      interval_label: row.interval_label,
    });
  };

  return (
    <div>
      <PageHeader
        eyebrow="Vintage movement"
        title="Forecast revisions"
        description="How the WINDFOR forecast moved between the decision-cutoff publication and the latest publication before delivery. Revisions are retrospective diagnostics; only the decision vintage was available at the procurement cutoff."
        meta={
          data ? (
            <>
              <Badge tone="violet">Historical analysis</Badge>
              <Badge tone="accent" dot>
                Decision vintage {data.filters.cutoff} Europe/London · D−{data.filters.cutoff_days_before}
              </Badge>
              <Badge tone="neutral">
                {summary?.intervals_with_vintages.toLocaleString("en-GB") ?? 0} intervals with vintages
              </Badge>
            </>
          ) : null
        }
        actions={
          <Button variant="primary" onClick={() => revisionsQuery.refetch()} disabled={revisionsQuery.isFetching}>
            <Activity size={13} className={revisionsQuery.isFetching ? "animate-pulse" : undefined} />
            {revisionsQuery.isFetching ? "Refreshing" : "Refresh revisions"}
          </Button>
        }
      />

      <FilterBar />

      {revisionsQuery.isError ? (
        <Panel>
          <QueryState isLoading={false} error={revisionsQuery.error} onRetry={() => revisionsQuery.refetch()}>
            <span />
          </QueryState>
        </Panel>
      ) : (
        <>
          <section aria-label="Revision headline indicators" className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
            <KpiCard
              label="Intervals with vintages"
              value={(summary?.intervals_with_vintages ?? 0).toLocaleString("en-GB")}
              icon={<GitCompareArrows size={14} />}
              hint="Paired to a decision-cutoff forecast"
              footer={<span>Intervals where a later publication exists</span>}
            />
            <KpiCard
              label="Mean absolute revision"
              value={formatMw(summary?.mean_abs_revision_mw)}
              unit="MW"
              icon={<MoveRight size={14} />}
              hint="Latest vintage − decision vintage"
              footer={<span>Average magnitude of movement</span>}
            />
            <KpiCard
              label="Largest absolute revision"
              value={formatMw(summary?.max_abs_revision_mw)}
              unit="MW"
              tone="warning"
              icon={<RefreshCw size={14} />}
              hint="Across the selected window"
              footer={<span>See table for the specific interval</span>}
            />
            <KpiCard
              label="Unchanged intervals"
              value={formatPct(summary?.unchanged_share_pct)}
              icon={<Info size={14} />}
              hint="Absolute revision ≤ 0.01 MW"
              footer={<span>Share of intervals with no movement</span>}
            />
          </section>

          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-3">
            <ChartPanel
              className="xl:col-span-2"
              title="Revision curve by publication lead time"
              subtitle="Mean signed revision versus the decision vintage, and mean absolute revision"
            >
              <QueryState
                isLoading={revisionsQuery.isLoading}
                error={revisionsQuery.error}
                isEmpty={populated.length === 0}
                onRetry={() => revisionsQuery.refetch()}
                emptyDescription="No pre-delivery vintages were found for this selection."
              >
                <RevisionCurveChart data={curve} height={300} />
              </QueryState>
            </ChartPanel>

            <Panel className="flex flex-col">
              <div className="border-b border-white/[0.06] px-4 py-3">
                <h2 className="panel-title">Vintage totals</h2>
                <p className="panel-subtitle">Mean forecast level and movement within each bucket</p>
              </div>
              <div className="max-h-[330px] flex-1 overflow-auto">
                <table className="table-shell">
                  <thead>
                    <tr>
                      <th>Bucket</th>
                      <th className="text-right">Mean forecast</th>
                      <th className="text-right">vs decision</th>
                      <th className="text-right">Mean |Δ|</th>
                      <th className="text-right">n</th>
                    </tr>
                  </thead>
                  <tbody>
                    {populated.map((row) => (
                      <tr key={row.key}>
                        <td className="text-slate-200">
                          {row.label}
                          <span className="ml-1 text-[10px] text-slate-600">{formatHours(row.mean_lead_time_hours)}</span>
                        </td>
                        <td className="num text-right text-slate-300">{formatMw(row.mean_forecast_mw)}</td>
                        <td className={cn("num text-right", DIRECTION_TONE(row.mean_delta_vs_decision_mw))}>
                          {formatMw(row.mean_delta_vs_decision_mw, { sign: true })}
                        </td>
                        <td className="num text-right text-slate-300">{formatMw(row.mean_abs_revision_mw)}</td>
                        <td className="num text-right text-slate-500">{row.n.toLocaleString("en-GB")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="border-t border-white/[0.05] px-4 py-2.5 text-[10px] leading-4 text-slate-600">
                n counts vintage-interval pairs, so an interval with many publications contributes to multiple buckets.
              </p>
            </Panel>
          </div>

          {data?.retrospective_notice ? (
            <div className="mt-3 flex items-start gap-2 rounded-xl border border-warning/15 bg-warning/[0.04] px-3.5 py-2.5 text-[11px] leading-5 text-warning/85">
              <Info size={14} className="mt-0.5 shrink-0" />
              <span>{data.retrospective_notice}</span>
            </div>
          ) : null}

          <Panel className="mt-3 overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-3">
              <div>
                <h2 className="panel-title">Largest revisions</h2>
                <p className="panel-subtitle">
                  Ranked by absolute movement from the decision vintage. Open a row for the full vintage path.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {revisionsQuery.isFetching && !revisionsQuery.isLoading ? (
                  <span className="text-[10px] text-accent/80">Updating…</span>
                ) : null}
                <Badge tone="neutral">{data?.top.length ?? 0} rows</Badge>
              </div>
            </div>

            <QueryState
              isLoading={revisionsQuery.isLoading}
              error={revisionsQuery.error}
              isEmpty={(data?.top.length ?? 0) === 0}
              onRetry={() => revisionsQuery.refetch()}
              emptyDescription="No intervals with both a decision vintage and a later publication exist in this selection."
            >
              <div className="max-h-[520px] overflow-auto">
                <table className="table-shell">
                  <thead>
                    <tr>
                      <th>Delivery</th>
                      <th className="text-right">Decision MW</th>
                      <th className="text-right">Latest MW</th>
                      <th className="text-right">Revision MW</th>
                      <th className="text-right">|Revision|</th>
                      <th className="text-right">Actual MW</th>
                      <th className="text-right">Latest error</th>
                      <th className="text-right">Vintages</th>
                      <th>Latest published</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.top ?? []).map((row) => (
                      <tr
                        key={row.delivery_interval}
                        data-interactive="true"
                        tabIndex={0}
                        onClick={() => openRow(row)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            openRow(row);
                          }
                        }}
                        aria-label={`Open vintage path for ${row.delivery_date} settlement period ${row.settlement_period}`}
                      >
                        <td>
                          <span className="text-slate-200">{row.delivery_date}</span>
                          <span className="ml-1.5 text-slate-600">SP {row.settlement_period}</span>
                        </td>
                        <td className="num text-right text-slate-400">{formatMw(row.decision_forecast_mw)}</td>
                        <td className="num text-right text-slate-200">{formatMw(row.latest_forecast_mw)}</td>
                        <td className={cn("num text-right font-semibold", DIRECTION_TONE(row.revision_mw))}>
                          {formatMw(row.revision_mw, { sign: true })}
                        </td>
                        <td className="num text-right text-slate-300">{formatMw(row.abs_revision_mw)}</td>
                        <td className="num text-right text-slate-400">{formatMw(row.actual_mw)}</td>
                        <td
                          className={cn(
                            "num text-right",
                            (row.latest_forecast_mw ?? 0) - (row.actual_mw ?? 0) > 0
                              ? "text-warning/80"
                              : "text-accent-teal/80",
                          )}
                        >
                          {formatMw(
                            row.latest_forecast_mw !== null && row.actual_mw !== null
                              ? row.latest_forecast_mw - row.actual_mw
                              : null,
                            { sign: true },
                          )}
                        </td>
                        <td className="num text-right text-slate-500">{row.n_vintages}</td>
                        <td className="num text-[11px] text-slate-400">{formatDateTime(row.latest_publish_time)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </QueryState>
            <p className="border-t border-white/[0.06] px-4 py-2.5 text-[10px] leading-4 text-slate-600">
              Revision = latest pre-delivery publication − decision-cutoff forecast. Positive values mean the forecast was revised upward.
              The latest error column compares the latest pre-delivery forecast with the observed actual and is retrospective.
            </p>
          </Panel>
        </>
      )}

      <IntervalDrawer
        row={selected}
        cutoff={filters.cutoff}
        cutoffDaysBefore={filters.cutoffDaysBefore}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
