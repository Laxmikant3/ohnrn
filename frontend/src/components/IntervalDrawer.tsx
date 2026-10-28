import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowLeftRight, CheckCircle2, Clock3, Info, X } from "lucide-react";
import { api } from "@/lib/api";
import type { ForecastRow } from "@/lib/types";
import { formatDateTime, formatHours, formatMw } from "@/lib/format";
import { Badge, Button, Panel, Skeleton, StateBlock } from "@/components/ui/primitives";
import { KeyValue } from "@/components/common";
import { CHART, ChartTooltip } from "@/components/charts/theme";
import { cn } from "@/lib/utils";

export type IntervalRef = Pick<
  ForecastRow,
  "delivery_interval" | "delivery_date" | "settlement_period" | "interval_label"
>;

export function IntervalDrawer({
  row,
  cutoff,
  cutoffDaysBefore,
  onClose,
}: {
  row: IntervalRef | null;
  cutoff: string;
  cutoffDaysBefore: number;
  onClose: () => void;
}) {
  const open = row !== null;
  const query = useQuery({
    queryKey: ["vintages", row?.delivery_interval, cutoff, cutoffDaysBefore],
    queryFn: ({ signal }) =>
      api.vintages(row!.delivery_interval, cutoff, cutoffDaysBefore, signal),
    enabled: Boolean(row?.delivery_interval),
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;

  const detail = query.data;
  const chartData = detail
    ? [...detail.vintages].sort((a, b) => b.lead_time_hours - a.lead_time_hours)
    : [];

  return (
    <div className="fixed inset-0 z-[70] flex justify-end" role="dialog" aria-modal="true" aria-label="Delivery interval detail">
      <div className="absolute inset-0 bg-ink-950/70 backdrop-blur-sm" onClick={onClose} aria-hidden />
      <div className="relative flex h-full w-full max-w-[560px] animate-fade-in flex-col border-l border-white/[0.08] bg-ink-900 shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-white/[0.07] px-4 py-3.5">
          <div>
            <p className="label-caps text-accent/70">Delivery interval</p>
            <h2 className="mt-0.5 text-[16px] font-semibold tracking-[-0.02em] text-slate-50">
              {row?.delivery_date} · SP {row?.settlement_period}
            </h2>
            <p className="mt-0.5 text-[11px] text-slate-500">
              {row?.interval_label} Europe/London · {formatDateTime(row?.delivery_interval)}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close interval detail">
            <X size={16} />
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {query.isLoading ? (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
              </div>
              <Skeleton className="h-[220px]" />
              <Skeleton className="h-[180px]" />
            </div>
          ) : query.isError ? (
            <StateBlock
              tone="negative"
              title="Vintage history unavailable"
              description={query.error instanceof Error ? query.error.message : "The request failed."}
              action={<Button size="sm" variant="outline" onClick={() => query.refetch()}>Retry</Button>}
            />
          ) : detail ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-2.5">
                  <p className="label-caps">Decision forecast</p>
                  <p className="num mt-1 text-[17px] font-semibold text-accent">{formatMw(detail.decision_forecast.forecast_mw)}</p>
                  <p className="text-[10px] text-slate-500">MW · {detail.decision_forecast.publish_time ? formatDateTime(detail.decision_forecast.publish_time) : "no eligible vintage"}</p>
                </div>
                <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-2.5">
                  <p className="label-caps">Actual outturn</p>
                  <p className="num mt-1 text-[17px] font-semibold text-slate-100">{formatMw(detail.actual_mw)}</p>
                  <p className="text-[10px] text-slate-500">MW · FUELHH</p>
                </div>
                <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-2.5">
                  <p className="label-caps">Decision error</p>
                  <p
                    className={cn(
                      "num mt-1 text-[17px] font-semibold",
                      (detail.decision_forecast.error_mw ?? 0) > 0
                        ? "text-warning"
                        : (detail.decision_forecast.error_mw ?? 0) < 0
                          ? "text-accent-teal"
                          : "text-slate-100",
                    )}
                  >
                    {formatMw(detail.decision_forecast.error_mw, { sign: true })}
                  </p>
                  <p className="text-[10px] text-slate-500">MW · forecast − actual</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/15 bg-warning/[0.04] px-3 py-2 text-[10.5px] leading-4 text-warning/85">
                <Info size={13} className="shrink-0" />
                {detail.retrospective_notice}
              </div>

              <Panel>
                <div className="flex items-center justify-between border-b border-white/[0.06] px-3 py-2">
                  <p className="panel-title">Vintage path</p>
                  <span className="text-[10px] text-slate-500">{detail.revision.n_vintages} publications</span>
                </div>
                <div className="px-1 pb-2 pt-3">
                  <ResponsiveContainer width="100%" height={190}>
                    <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="lead_time_hours"
                        type="number"
                        reversed
                        tickFormatter={(value: number) => `${value.toFixed(0)}h`}
                        tickLine={false}
                        axisLine={{ stroke: CHART.grid }}
                        tickMargin={6}
                      />
                      <YAxis
                        tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
                        width={40}
                        tickLine={false}
                        axisLine={false}
                        domain={["auto", "auto"]}
                      />
                      <Tooltip
                        content={
                          <ChartTooltip
                            unit="MW"
                            formatLabel={(value) => `${Number(value).toFixed(1)} h before delivery`}
                          />
                        }
                      />
                      {detail.actual_mw !== null ? (
                        <ReferenceLine
                          y={detail.actual_mw}
                          stroke={CHART.actual}
                          strokeDasharray="4 3"
                          label={{ value: "Actual", position: "insideTopRight", fill: CHART.actual, fontSize: 9 }}
                        />
                      ) : null}
                      <Line
                        type="stepAfter"
                        dataKey="forecast_mw"
                        name="Forecast MW"
                        stroke={CHART.forecast}
                        strokeWidth={1.8}
                        dot={{ r: 2.6, fill: CHART.forecast, strokeWidth: 0 }}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <p className="px-2 pt-1 text-[10px] text-slate-600">
                    Publication lead time runs right to left: later vintages sit closer to delivery. Decision cutoff{" "}
                    {detail.cutoff.time} {detail.cutoff.timezone} on D−{detail.cutoff.days_before} ({formatDateTime(detail.cutoff.cutoff_utc)}).
                  </p>
                </div>
              </Panel>

              <Panel>
                <div className="flex items-center justify-between border-b border-white/[0.06] px-3 py-2">
                  <p className="panel-title">Vintages at the cutoff</p>
                  <Badge tone="accent">{detail.revision.n_eligible_vintages} eligible</Badge>
                </div>
                <div className="max-h-[240px] overflow-auto">
                  <table className="table-shell">
                    <thead>
                      <tr>
                        <th>Published</th>
                        <th className="text-right">Lead</th>
                        <th className="text-right">Forecast</th>
                        <th className="text-right">Δ decision</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.vintages.map((vintage) => (
                        <tr key={vintage.publish_time} className={vintage.selected ? "bg-accent/[0.06]" : undefined}>
                          <td className="num text-[11px]">{formatDateTime(vintage.publish_time)}</td>
                          <td className="num text-right text-slate-500">{formatHours(vintage.lead_time_hours)}</td>
                          <td className="num text-right font-medium text-slate-100">{formatMw(vintage.forecast_mw)}</td>
                          <td
                            className={cn(
                              "num text-right",
                              (vintage.revision_from_decision_mw ?? 0) > 0
                                ? "text-warning"
                                : (vintage.revision_from_decision_mw ?? 0) < 0
                                  ? "text-accent-teal"
                                  : "text-slate-500",
                            )}
                          >
                            {formatMw(vintage.revision_from_decision_mw, { sign: true })}
                          </td>
                          <td>
                            {vintage.selected ? (
                              <Badge tone="accent">
                                <CheckCircle2 size={10} /> Selected
                              </Badge>
                            ) : vintage.eligible ? (
                              <Badge tone="neutral">Eligible</Badge>
                            ) : (
                              <Badge tone="warning">Post-cutoff</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>

              <Panel className="p-3">
                <div className="mb-1 flex items-center gap-1.5">
                  <ArrowLeftRight size={12} className="text-slate-500" />
                  <p className="panel-title">Revision summary</p>
                </div>
                <dl>
                  <KeyValue label="Latest publication" value={detail.latest_forecast.publish_time ? formatDateTime(detail.latest_forecast.publish_time) : "—"} />
                  <KeyValue label="Latest forecast" value={`${formatMw(detail.latest_forecast.forecast_mw)} MW`} />
                  <KeyValue
                    label="Latest − decision"
                    value={`${formatMw(detail.revision.latest_minus_decision_mw, { sign: true })} MW`}
                  />
                  <KeyValue
                    label="Latest − actual"
                    value={`${formatMw(detail.revision.latest_minus_actual_mw, { sign: true })} MW`}
                  />
                  <KeyValue
                    label="Decision publish time"
                    value={
                      <span className="inline-flex items-center gap-1">
                        <Clock3 size={10} className="text-slate-500" />
                        {detail.revision.latest_eligible_publish_time ? formatDateTime(detail.revision.latest_eligible_publish_time) : "—"}
                      </span>
                    }
                  />
                </dl>
              </Panel>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
