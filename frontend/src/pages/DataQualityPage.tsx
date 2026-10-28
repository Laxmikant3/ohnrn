import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ClipboardCopy,
  Clock3,
  Database,
  HardDrive,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  WifiOff,
  XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTime, formatPct, formatDecimal, relativeAge } from "@/lib/format";
import { PageHeader, QueryState, KeyValue } from "@/components/common";
import { Badge, Button, Panel, StateBlock } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

function bytes(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value)) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}

function shortHash(value: string | null | undefined): string {
  if (!value) return "—";
  return `${value.slice(0, 12)}…${value.slice(-8)}`;
}

function StatTile({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "warning" | "negative" }) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
      <p className="label-caps">{label}</p>
      <p
        className={cn(
          "num mt-1 text-[17px] font-semibold leading-none",
          tone === "warning" ? "text-warning" : tone === "negative" ? "text-negative" : "text-slate-100",
        )}
      >
        {value}
      </p>
      {hint ? <p className="mt-1 truncate text-[10px] text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function DataQualityPage() {
  const qualityQuery = useQuery({
    queryKey: ["data-quality"],
    queryFn: ({ signal }) => api.dataQuality(signal),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });
  const metadataQuery = useQuery({
    queryKey: ["metadata"],
    queryFn: ({ signal }) => api.metadata(signal),
    staleTime: 10 * 60_000,
  });

  const data = qualityQuery.data;
  const counts = data?.counts;
  const files = data ? Object.entries(data.cache.files) : [];

  const copyHash = (hash: string) => {
    void navigator.clipboard?.writeText(hash);
  };

  return (
    <div>
      <PageHeader
        eyebrow="Provenance and completeness"
        title="Data quality"
        description="Evidence that the analysis is built on real, cached Elexon BMRS data: upstream reachability, cache file hashes, retrieval audit events, record counts, coverage by settlement day and every excluded or invalid record category."
        meta={
          data ? (
            <>
              <Badge tone={data.data.is_synthetic ? "negative" : "positive"} dot>
                {data.data.is_synthetic ? "Synthetic data detected" : "No synthetic records"}
              </Badge>
              <Badge tone={data.data.cached ? "accent" : "neutral"}>{data.data.source}</Badge>
              <Badge tone={data.cache.stale ? "warning" : "positive"}>
                {data.cache.stale ? "Cache stale" : "Cache fresh"}
              </Badge>
              <span className="text-[10.5px] text-slate-500">Generated {formatDateTime(data.generated_at)}</span>
            </>
          ) : null
        }
        actions={
          <Button variant="primary" onClick={() => qualityQuery.refetch()} disabled={qualityQuery.isFetching}>
            <RefreshCw size={13} className={qualityQuery.isFetching ? "animate-spin" : undefined} />
            {qualityQuery.isFetching ? "Probing" : "Re-check upstream"}
          </Button>
        }
      />

      {qualityQuery.isError ? (
        <Panel>
          <QueryState isLoading={false} error={qualityQuery.error} onRetry={() => qualityQuery.refetch()}>
            <span />
          </QueryState>
        </Panel>
      ) : qualityQuery.isLoading ? (
        <Panel>
          <QueryState isLoading error={null}>
            <span />
          </QueryState>
        </Panel>
      ) : data ? (
        <>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
            <Panel className="p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <ServerCog size={14} className="text-slate-500" />
                  <h2 className="panel-title">Upstream connectivity</h2>
                </div>
                {data.upstream.reachable ? (
                  <Badge tone="positive" dot>
                    Reachable
                  </Badge>
                ) : data.upstream.checked ? (
                  <Badge tone="negative" dot>
                    Unreachable
                  </Badge>
                ) : (
                  <Badge tone="neutral">Not checked</Badge>
                )}
              </div>
              <div className="flex items-start gap-2.5">
                <div
                  className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border",
                    data.upstream.reachable
                      ? "border-positive/20 bg-positive/10 text-positive"
                      : "border-warning/20 bg-warning/10 text-warning",
                  )}
                >
                  {data.upstream.reachable ? <ShieldCheck size={17} /> : <WifiOff size={17} />}
                </div>
                <div className="min-w-0">
                  <p className="text-[11.5px] leading-5 text-slate-300">{data.upstream.detail}</p>
                  <p className="mt-1 text-[10px] text-slate-500">
                    Checked {formatDateTime(data.upstream.checked_at)} · HTTP {data.upstream.status_code ?? "—"} ·{" "}
                    {data.upstream.latency_ms !== null ? `${data.upstream.latency_ms} ms` : "latency unknown"}
                  </p>
                </div>
              </div>
              <dl className="mt-3 border-t border-white/[0.05] pt-2">
                <KeyValue label="Analysis mode" value={data.mode} />
                <KeyValue label="Cache age" value={relativeAge(data.data.last_retrieval)} />
                <KeyValue
                  label="Stale threshold"
                  value={`${formatDecimal(data.cache.stale_after_hours, 0)} h`}
                />
                <KeyValue label="Last retrieval" value={formatDateTime(data.data.last_retrieval)} />
              </dl>
              <p className="mt-2 rounded-md border border-white/[0.06] bg-white/[0.02] px-2.5 py-2 text-[10px] leading-4 text-slate-500">
                Upstream probes are advisory. The historical January 2026 analysis is served entirely from the verified
                cache, so a transient Elexon outage does not change the figures on the other pages.
              </p>
            </Panel>

            <Panel className="p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <HardDrive size={14} className="text-slate-500" />
                  <h2 className="panel-title">Cache integrity</h2>
                </div>
                <Badge tone={data.cache.present ? "positive" : "negative"}>
                  {data.cache.present ? "Present" : "Missing"}
                </Badge>
              </div>
              <div className="space-y-2">
                {files.map(([key, meta]) => (
                  <div key={key} className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11.5px] font-medium text-slate-200">{meta.file}</span>
                      <Badge tone={meta.exists ? "positive" : "negative"}>{meta.exists ? "OK" : "Missing"}</Badge>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px] text-slate-500">
                      <span className="num">{bytes(meta.bytes)}</span>
                      {meta.records !== undefined && meta.records !== null ? (
                        <span className="num">{meta.records.toLocaleString("en-GB")} records</span>
                      ) : null}
                      <span>{formatDateTime(meta.modified_at)}</span>
                    </div>
                    {meta.sha256 ? (
                      <button
                        type="button"
                        onClick={() => copyHash(meta.sha256 ?? "")}
                        title={`Copy SHA-256: ${meta.sha256}`}
                        className="num mt-1 flex w-full items-center gap-1.5 truncate rounded border border-white/[0.05] bg-ink-950/40 px-1.5 py-1 text-left text-[9.5px] text-slate-500 transition-colors hover:text-accent focus-ring"
                      >
                        <ClipboardCopy size={10} className="shrink-0" />
                        <span className="truncate">{shortHash(meta.sha256)}</span>
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
              <dl className="mt-3 border-t border-white/[0.05] pt-2">
                <KeyValue label="Actual last success" value={formatDateTime(data.cache.last_success.actual)} />
                <KeyValue label="Forecast last success" value={formatDateTime(data.cache.last_success.forecast)} />
              </dl>
            </Panel>

            <Panel className="p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <Database size={14} className="text-slate-500" />
                  <h2 className="panel-title">Dataset composition</h2>
                </div>
                <Badge tone="neutral">{data.data.forecast_vintages} vintages</Badge>
              </div>
              <dl>
                <KeyValue label="FUELHH actual records" value={data.data.actual_records.toLocaleString("en-GB")} />
                <KeyValue
                  label="WINDFOR source records (hourly)"
                  value={data.data.forecast_records.toLocaleString("en-GB")}
                />
                <KeyValue
                  label="WINDFOR source delivery intervals"
                  value={data.data.forecast_delivery_intervals.toLocaleString("en-GB")}
                />
                <KeyValue
                  label="Expanded 30-min forecast rows"
                  value={data.data.forecast_expanded_intervals.toLocaleString("en-GB")}
                />
                <KeyValue
                  label="Forecast granularity"
                  value={`${data.data.forecast_granularity_minutes} min → 30 min`}
                />
                <KeyValue label="Post-delivery excluded" value={(counts?.excluded_post_delivery_records ?? 0).toLocaleString("en-GB")} />
                <KeyValue label="Invalid records" value={(counts?.invalid_records ?? 0).toLocaleString("en-GB")} />
                <KeyValue label="Duplicates removed" value={(counts?.duplicates_removed ?? 0).toLocaleString("en-GB")} />
                <KeyValue label="Duplicate conflicts" value={(counts?.duplicate_conflicts ?? 0).toLocaleString("en-GB")} />
                <KeyValue label="Naive timestamps" value={(counts?.naive_timestamps ?? 0).toLocaleString("en-GB")} />
              </dl>
              <p className="mt-2 text-[10px] leading-4 text-slate-500">
                Record counts describe the normalised dataset; the explorer counts settlement intervals. One hourly
                WINDFOR value expands onto two 30-minute delivery intervals and is flagged in the export.
              </p>
            </Panel>
          </div>

          <section aria-label="Record accounting" className="mt-3 grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
            <StatTile label="Expected intervals" value={(counts?.expected_intervals ?? 0).toLocaleString("en-GB")} hint="January 2026 grid" />
            <StatTile
              label="Missing actual"
              value={(counts?.missing_actual_intervals ?? 0).toLocaleString("en-GB")}
              hint="No FUELHH value"
              tone={(counts?.missing_actual_intervals ?? 0) > 0 ? "warning" : undefined}
            />
            <StatTile
              label="Missing forecast"
              value={(counts?.missing_forecast_intervals ?? 0).toLocaleString("en-GB")}
              hint="No eligible vintage"
              tone={(counts?.missing_forecast_intervals ?? 0) > 0 ? "warning" : undefined}
            />
            <StatTile
              label="Forecast outside window"
              value={(counts?.forecast_intervals_outside_analysis_window ?? 0).toLocaleString("en-GB")}
              hint="Source intervals outside Jan 2026"
            />
            <StatTile
              label="Actual outside window"
              value={(counts?.actual_intervals_outside_analysis_window ?? 0).toLocaleString("en-GB")}
              hint="Ignored by the analysis grid"
            />
            <StatTile
              label="Coverage"
              value={formatPct(
                counts && counts.expected_intervals > 0
                  ? ((counts.expected_intervals -
                      (counts.missing_actual_intervals + counts.missing_forecast_intervals)) /
                      counts.expected_intervals) *
                      100
                  : null,
              )}
              hint="Expected intervals with both legs"
            />
          </section>

          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2">
            <Panel className="overflow-hidden">
              <div className="flex items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-3">
                <div>
                  <h2 className="panel-title">Coverage by delivery day</h2>
                  <p className="panel-subtitle">Matched settlement periods against the expected London-day grid</p>
                </div>
                <Badge tone={data.coverage_by_day.every((day) => (day.coverage_pct ?? 0) >= 100) ? "positive" : "warning"}>
                  {data.coverage_by_day.filter((day) => (day.coverage_pct ?? 0) >= 100).length}/{data.coverage_by_day.length} complete
                </Badge>
              </div>
              <div className="max-h-[360px] overflow-auto">
                <table className="table-shell">
                  <thead>
                    <tr>
                      <th>Delivery date</th>
                      <th className="text-right">Expected</th>
                      <th className="text-right">Matched</th>
                      <th className="text-right">Missing actual</th>
                      <th className="text-right">Missing forecast</th>
                      <th className="text-right">Coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.coverage_by_day.map((day) => (
                      <tr key={day.date}>
                        <td className="text-slate-200">{day.date}</td>
                        <td className="num text-right text-slate-400">{day.expected}</td>
                        <td className="num text-right text-slate-200">{day.matched}</td>
                        <td className="num text-right text-slate-400">{day.missing_actual}</td>
                        <td className="num text-right text-slate-400">{day.missing_forecast}</td>
                        <td
                          className={cn(
                            "num text-right font-medium",
                            (day.coverage_pct ?? 0) >= 99.5 ? "text-positive" : "text-warning",
                          )}
                        >
                          {formatPct(day.coverage_pct, 1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>

            <div className="space-y-3">
              <Panel className="overflow-hidden">
                <div className="flex items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-3">
                  <div>
                    <h2 className="panel-title">Missing intervals</h2>
                    <p className="panel-subtitle">Intervals retained in the population but not paired</p>
                  </div>
                  <Badge tone={data.missing_intervals.length === 0 ? "positive" : "warning"}>
                    {data.missing_intervals.length}
                  </Badge>
                </div>
                {data.missing_intervals.length === 0 ? (
                  <div className="flex items-center gap-2 px-4 py-5 text-[11.5px] text-positive">
                    <CheckCircle2 size={15} /> No missing intervals in the default January 2026 analysis.
                  </div>
                ) : (
                  <div className="max-h-[210px] overflow-auto">
                    <table className="table-shell">
                      <thead>
                        <tr>
                          <th>Delivery date</th>
                          <th className="text-right">SP</th>
                          <th>Interval</th>
                          <th>Missing leg</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.missing_intervals.map((row) => (
                          <tr key={`${row.delivery_interval}-${row.missing}`}>
                            <td className="text-slate-300">{row.delivery_date}</td>
                            <td className="num text-right text-slate-400">{row.settlement_period}</td>
                            <td className="text-slate-500">{row.interval_label}</td>
                            <td>
                              <Badge tone={row.missing === "forecast" ? "negative" : "warning"}>{row.missing}</Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>

              <Panel className="overflow-hidden">
                <div className="flex items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-3">
                  <div>
                    <h2 className="panel-title">Invalid samples</h2>
                    <p className="panel-subtitle">Rejected during normalisation, capped at 50 samples</p>
                  </div>
                  <Badge tone={data.invalid_samples.length === 0 ? "positive" : "warning"}>
                    {data.invalid_samples.length}
                  </Badge>
                </div>
                {data.invalid_samples.length === 0 ? (
                  <div className="flex items-center gap-2 px-4 py-5 text-[11.5px] text-positive">
                    <CheckCircle2 size={15} /> No invalid records were rejected in the cached retrieval.
                  </div>
                ) : (
                  <pre className="max-h-[210px] overflow-auto whitespace-pre-wrap px-4 py-3 text-[10.5px] leading-5 text-slate-400">
                    {JSON.stringify(data.invalid_samples, null, 2)}
                  </pre>
                )}
              </Panel>

              <Panel className="p-3">
                <div className="mb-1 flex items-center gap-1.5">
                  <AlertTriangle size={12} className="text-slate-500" />
                  <p className="panel-title">Interpretation notes</p>
                </div>
                <ul className="space-y-1.5">
                  {data.notes.map((note) => (
                    <li key={note} className="flex gap-2 text-[10.5px] leading-4 text-slate-500">
                      <span className="mt-[6px] h-1 w-1 shrink-0 rounded-full bg-slate-600" aria-hidden />
                      {note}
                    </li>
                  ))}
                </ul>
              </Panel>
            </div>
          </div>

          <Panel className="mt-3 overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-3">
              <div>
                <h2 className="panel-title">Retrieval audit trail</h2>
                <p className="panel-subtitle">Every Elexon request recorded in the cache manifest, most recent first</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone="accent">{data.retrieval_events.length} events</Badge>
                <Clock3 size={13} className="text-slate-600" />
              </div>
            </div>
            {data.retrieval_events.length === 0 ? (
              <StateBlock
                icon={<Database size={17} />}
                title="No retrieval events recorded"
                description="The cache manifest does not contain an audit trail. Re-run the ingestion CLI to populate it."
              />
            ) : (
              <div className="max-h-[360px] overflow-auto">
                <table className="table-shell">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Operation</th>
                      <th>Endpoint</th>
                      <th>Parameters</th>
                      <th className="text-right">Records</th>
                      <th className="text-right">Attempts</th>
                      <th className="text-right">Duration</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.retrieval_events.map((event, index) => (
                      <tr key={`${event.timestamp}-${index}`}>
                        <td className="num text-[11px] text-slate-300">{formatDateTime(event.timestamp)}</td>
                        <td className="text-slate-300">{event.operation}</td>
                        <td className="num text-[10.5px] text-slate-500">{event.endpoint}</td>
                        <td className="max-w-[280px] truncate text-[10.5px] text-slate-500" title={JSON.stringify(event.params)}>
                          {Object.entries(event.params)
                            .map(([key, value]) => `${key}=${String(value)}`)
                            .join(" · ")}
                        </td>
                        <td className="num text-right text-slate-300">{event.records.toLocaleString("en-GB")}</td>
                        <td className="num text-right text-slate-500">{event.attempts}</td>
                        <td className="num text-right text-slate-400">{formatDecimal(event.duration_seconds, 2)}s</td>
                        <td>
                          {event.status === "success" ? (
                            <Badge tone="positive">
                              <CheckCircle2 size={10} /> Success
                            </Badge>
                          ) : (
                            <Badge tone="negative">
                              <XCircle size={10} /> {event.status}
                            </Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2">
            <Panel className="p-4">
              <div className="mb-2 flex items-center gap-1.5">
                <Activity size={13} className="text-slate-500" />
                <h2 className="panel-title">Normalisation statistics</h2>
              </div>
              <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
                <div>
                  <p className="label-caps mb-1 text-accent/70">FUELHH actuals</p>
                  <dl>
                    {Object.entries(data.actual_stats)
                      .filter(([key]) => key !== "invalid_samples")
                      .map(([key, value]) => (
                        <KeyValue key={key} label={key.replaceAll("_", " ")} value={String(value)} />
                      ))}
                  </dl>
                </div>
                <div>
                  <p className="label-caps mb-1 text-accent/70">WINDFOR forecasts</p>
                  <dl>
                    {Object.entries(data.forecast_stats)
                      .filter(([key]) => key !== "invalid_samples")
                      .map(([key, value]) => (
                        <KeyValue key={key} label={key.replaceAll("_", " ")} value={String(value)} />
                      ))}
                  </dl>
                </div>
              </div>
            </Panel>

            <Panel className="p-4">
              <div className="mb-2 flex items-center gap-1.5">
                <ShieldCheck size={13} className="text-slate-500" />
                <h2 className="panel-title">Verified source contract</h2>
              </div>
              {metadataQuery.data ? (
                <div className="space-y-2.5">
                  {metadataQuery.data.sources.map((source) => (
                    <div key={source.dataset} className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11.5px] font-medium text-slate-200">
                          {source.dataset} · {source.name}
                        </span>
                        <Badge tone="accent">{source.granularity_minutes} min</Badge>
                      </div>
                      <p className="num mt-1 break-all text-[10px] text-slate-500">{source.endpoint}</p>
                      <p className="mt-1 text-[10px] text-slate-500">
                        Parameters: {source.parameters.join(", ")} · Auth: {source.authentication} · Pagination:{" "}
                        {source.pagination}
                      </p>
                    </div>
                  ))}
                  <p className="text-[10px] leading-4 text-slate-500">
                    The contract was verified against the live Elexon OpenAPI description. WINDFOR supports only
                    publication-window filtering; FUELHH supports settlement-date filtering. The two filter styles are
                    mutually exclusive in the API.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, index) => (
                    <div key={index} className="h-12 animate-pulse rounded bg-white/[0.04]" />
                  ))}
                </div>
              )}
            </Panel>
          </div>
        </>
      ) : null}
    </div>
  );
}
